"""SQLite storage. Every extracted item keeps the document it came from (document_id)."""
import sqlite3

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  subject_name TEXT NOT NULL,
  subject_kind TEXT NOT NULL DEFAULT 'person',      -- person | pet
  summary TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS members (
  id INTEGER PRIMARY KEY,
  case_id INTEGER NOT NULL REFERENCES cases(id),
  name TEXT NOT NULL,
  role TEXT,                                         -- patient | spouse | parent | caregiver
  color TEXT
);

CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY,
  case_id INTEGER NOT NULL REFERENCES cases(id),
  doc_type TEXT NOT NULL,                            -- invoice | prescription | study_order | ...
  title TEXT NOT NULL,
  doc_date TEXT,
  issuer TEXT,
  file_path TEXT,
  handwritten INTEGER DEFAULT 0,
  summary TEXT,
  extracted_json TEXT,
  status TEXT DEFAULT 'processed',                   -- processing | processed | needs_review
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS medications (
  id INTEGER PRIMARY KEY,
  case_id INTEGER NOT NULL REFERENCES cases(id),
  document_id INTEGER REFERENCES documents(id),
  name TEXT NOT NULL,
  dose TEXT,
  instructions TEXT,
  every_hours INTEGER,
  first_time TEXT DEFAULT '08:00',
  start_date TEXT,
  end_date TEXT,
  confidence REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS dose_log (
  id INTEGER PRIMARY KEY,
  medication_id INTEGER NOT NULL REFERENCES medications(id),
  scheduled_at TEXT NOT NULL,
  taken_at TEXT DEFAULT CURRENT_TIMESTAMP,
  member_id INTEGER REFERENCES members(id),
  UNIQUE (medication_id, scheduled_at)
);

CREATE TABLE IF NOT EXISTS insurance (
  id INTEGER PRIMARY KEY,
  case_id INTEGER NOT NULL REFERENCES cases(id),
  insurer TEXT NOT NULL,
  nit TEXT,
  coverage_limit REAL,
  claim_days INTEGER                                 -- days to submit an invoice after its date
);

CREATE TABLE IF NOT EXISTS expenses (
  id INTEGER PRIMARY KEY,
  case_id INTEGER NOT NULL REFERENCES cases(id),
  document_id INTEGER REFERENCES documents(id),
  date TEXT NOT NULL,
  amount REAL NOT NULL,
  category TEXT NOT NULL,                            -- hospitalization | medication | nursing | transport | lab_imaging | doctor_fees | therapy | legal | other
  vendor TEXT,
  description TEXT,
  paid_by INTEGER REFERENCES members(id),
  invoice_number TEXT,
  billed_to TEXT,
  billed_to_nit TEXT,
  reimbursable INTEGER DEFAULT 0,
  claim_status TEXT DEFAULT 'to_submit',             -- to_submit | submitted | approved | rejected | paid | not_applicable
  reimbursed_amount REAL
);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY,
  case_id INTEGER NOT NULL REFERENCES cases(id),
  document_id INTEGER REFERENCES documents(id),
  kind TEXT NOT NULL,                                -- accident | admission | surgery | appointment | session | study | hearing | other
  title TEXT NOT NULL,
  date TEXT NOT NULL,
  time TEXT,
  place TEXT,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS contacts (
  id INTEGER PRIMARY KEY,
  case_id INTEGER NOT NULL REFERENCES cases(id),
  document_id INTEGER REFERENCES documents(id),
  name TEXT NOT NULL,
  role TEXT,
  organization TEXT,
  phones TEXT,                                       -- JSON array
  email TEXT,
  address TEXT,
  is_emergency INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY,
  case_id INTEGER NOT NULL REFERENCES cases(id),
  document_id INTEGER REFERENCES documents(id),
  title TEXT NOT NULL,
  kind TEXT,                                         -- study | appointment | claim | legal | other
  status TEXT DEFAULT 'pending',                     -- pending | done
  resolved_document_id INTEGER REFERENCES documents(id)
);

CREATE TABLE IF NOT EXISTS findings (
  id INTEGER PRIMARY KEY,
  case_id INTEGER NOT NULL REFERENCES cases(id),
  document_id INTEGER REFERENCES documents(id),
  related_document_id INTEGER REFERENCES documents(id),
  severity TEXT NOT NULL,                            -- critical | warning | info
  kind TEXT,                                         -- date | body_side | billing | arithmetic | duplicate | pending | other
  title TEXT NOT NULL,
  detail TEXT,
  status TEXT DEFAULT 'open',                        -- open | resolved | dismissed
  source TEXT DEFAULT 'ai'                           -- ai | rule | ai+rule (both agree)
);

CREATE TABLE IF NOT EXISTS questions (
  id INTEGER PRIMARY KEY,
  case_id INTEGER NOT NULL REFERENCES cases(id),
  document_id INTEGER REFERENCES documents(id),
  question TEXT NOT NULL,
  options TEXT,                                      -- JSON array
  answer TEXT,
  status TEXT DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS instructions (
  id INTEGER PRIMARY KEY,
  case_id INTEGER NOT NULL REFERENCES cases(id),
  document_id INTEGER REFERENCES documents(id),
  kind TEXT NOT NULL,                                -- diet | activity | care | medication | other
  polarity TEXT NOT NULL DEFAULT 'do',               -- do | avoid
  text TEXT NOT NULL,
  start_date TEXT,
  until TEXT
);

CREATE TABLE IF NOT EXISTS ai_calls (
  id INTEGER PRIMARY KEY,
  case_id INTEGER REFERENCES cases(id),
  document_id INTEGER REFERENCES documents(id),
  model TEXT,
  purpose TEXT,
  endpoint TEXT,
  latency_ms INTEGER,
  input_tokens INTEGER,
  output_tokens INTEGER,
  ok INTEGER DEFAULT 1,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def connect() -> sqlite3.Connection:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.DB_PATH, timeout=30)  # several uploads can write at once
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init() -> None:
    with connect() as con:
        con.executescript(SCHEMA)
        cols = {r[1] for r in con.execute("PRAGMA table_info(insurance)")}
        if "claim_rule" not in cols:  # 'end_of_month': invoices must be submitted within their own month
            con.execute("ALTER TABLE insurance ADD COLUMN claim_rule TEXT")
        if "replay" not in {r[1] for r in con.execute("PRAGMA table_info(cases)")}:
            # replay = 1: a demo case shown as of DINDO_TODAY / DINDO_TIME; cases the family creates live in real time
            con.execute("ALTER TABLE cases ADD COLUMN replay INTEGER DEFAULT 0")
            con.execute("UPDATE cases SET replay=1 WHERE title != 'Gato Cerafin'")


def claim_due(policy: dict | None, invoice_date: str | None):
    """Last day to submit an invoice to the insurer, or None if the policy sets no deadline."""
    from datetime import date, timedelta
    if not policy or not invoice_date:
        return None
    d = date.fromisoformat(invoice_date)
    if policy.get("claim_rule") == "end_of_month":
        return (d.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    if policy.get("claim_days"):
        return d + timedelta(days=policy["claim_days"])
    return None


def rows(con: sqlite3.Connection, sql: str, *args) -> list[dict]:
    return [dict(r) for r in con.execute(sql, args).fetchall()]


def row(con: sqlite3.Connection, sql: str, *args) -> dict | None:
    r = con.execute(sql, args).fetchone()
    return dict(r) if r else None

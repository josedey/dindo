"""Dindo API.  Run:  python -m uvicorn dindo.servidor.app:app --reload"""
import json
import re
import shutil
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import ai, audit, config, db, paquetes
from .ingest import ingest_item, short_topic

ALLOWED_UPLOADS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}

app = FastAPI(title="Dindo")
db.init()

CASE_PATH = re.compile(r"/api/cases/(\d+)")


@app.middleware("http")
async def case_clock(request, call_next):
    """Demo cases are replayed on DINDO_TODAY / DINDO_TIME; a case the family created runs on the real date and time."""
    m = CASE_PATH.match(request.url.path)
    replay = True
    if m:
        with db.connect() as con:
            row = db.row(con, "SELECT replay FROM cases WHERE id=?", int(m.group(1)))
        replay = bool(row and row["replay"])
    token = config.replaying(replay)
    try:
        return await call_next(request)
    finally:
        config.reset_replay(token)

LINKED = ("expenses", "medications", "events", "contacts", "tasks", "findings", "questions", "instructions")

CONTACT_GROUPS = [  # (group, words in role/name/organization)
    ("emergency", ("emerg", "ambulan", "sos")),
    ("legal", ("abog", "fiscal", "juez", "juzg", "concilia", "legal", "secretario")),
    ("pharmacy", ("farmac",)),
    ("doctor", ("dr", "dra", "medic", "cirujan", "traumat", "fisioter", "lic.", "especial", "radiolog", "veterin", "m.v.")),
    ("clinic", ("clinic", "clínic", "centro", "laborat", "hospital", "rehab", "caja")),
]


def _day(d: str | None) -> date:
    return date.fromisoformat(d) if d else config.today()


def _contact_group(c: dict) -> str:
    if c.get("is_emergency"):
        return "emergency"
    text = " ".join(str(c.get(k) or "") for k in ("role", "name", "organization")).lower()
    for group, words in CONTACT_GROUPS:
        if any(re.search(rf"(^|\W){re.escape(w)}", text) for w in words):
            return group
    return "other"


def _norm_word(s: str) -> str:
    s = re.sub(r"[^a-záéíóúñ ]", " ", (s or "").lower())
    words = [w for w in s.split() if len(w) >= 4 and w not in ("ilegible", "comprimido", "ampolla", "tabletas")]
    return words[0][:6] if words else ""


def _to_buy(con, case_id: int, today: date) -> list[dict]:
    """Prescribed medications with no later invoice or receipt that mentions them (last 45 days)."""
    since = (today - timedelta(days=45)).isoformat()
    meds = db.rows(con, """SELECT m.id, m.name, m.dose, m.start_date, m.document_id, d.title AS document_title FROM medications m
                           JOIN documents d ON d.id=m.document_id WHERE m.case_id=? AND d.doc_type NOT IN ('invoice','receipt')
                           AND (m.every_hours IS NOT NULL OR m.end_date IS NOT NULL)
                           AND m.start_date BETWEEN ? AND ? ORDER BY m.start_date DESC""", case_id, since, today.isoformat())
    bought = db.rows(con, """SELECT doc_date, extracted_json FROM documents WHERE case_id=? AND doc_type IN ('invoice','receipt')""", case_id)
    out = []
    for m in meds:
        key = _norm_word(m["name"])
        if not key or db.row(con, "SELECT 1 FROM dose_log WHERE medication_id=? LIMIT 1", m["id"]):
            continue  # someone is already taking it, so it was bought
        found = any((b["doc_date"] or "") >= (m["start_date"] or "") and key in json.dumps(json.loads(b["extracted_json"] or "{}").get("line_items") or [],
                                                                                            ensure_ascii=False).lower() for b in bought)
        if not found:
            out.append(m)
    return out


def _doses(con, case_id: int, day: date) -> list[dict]:
    """Scheduled doses for one day, from each active medication's interval."""
    out = []
    iso = day.isoformat()
    meds = db.rows(con, """SELECT * FROM medications WHERE case_id=? AND every_hours IS NOT NULL
                           AND (start_date IS NULL OR start_date<=?) AND (end_date IS NULL OR end_date>=?)""",
                   case_id, iso, iso)
    for m in meds:
        if not m["end_date"] and m["start_date"] and (day - date.fromisoformat(m["start_date"])).days > 30:
            continue  # no end date written: only schedule it for the first month
        t = datetime.combine(day, datetime.strptime(m["first_time"] or "08:00", "%H:%M").time())
        day_no = (day - date.fromisoformat(m["start_date"])).days + 1 if m["start_date"] else None
        total = ((date.fromisoformat(m["end_date"]) - date.fromisoformat(m["start_date"])).days + 1
                 if m["start_date"] and m["end_date"] else None)
        while t.date() == day:
            at = t.strftime("%Y-%m-%dT%H:%M")
            taken = db.row(con, """SELECT l.taken_at, mb.name AS by_name FROM dose_log l LEFT JOIN members mb ON mb.id=l.member_id
                                   WHERE l.medication_id=? AND l.scheduled_at=?""", m["id"], at)
            out.append({"medication_id": m["id"], "name": m["name"], "dose": m["dose"], "instructions": m["instructions"],
                        "scheduled_at": at, "time": t.strftime("%H:%M"), "taken": bool(taken), "taken_by": (taken or {}).get("by_name"),
                        "day_no": day_no, "days_total": total, "document_id": m["document_id"]})
            t += timedelta(hours=m["every_hours"])
    return sorted(out, key=lambda d: d["scheduled_at"])


QTY = re.compile(r"(?:[x×#]\s*(\d{1,3}))|(?:(\d{1,3})\s*(?:comp|caps|cáps|tab|amp|unid|sobres))", re.I)


def _adherence(con, case_id: int, day: date, days: int = 7) -> dict:
    expected = taken = 0
    per_day, by_member = [], {}
    for i in range(days - 1, -1, -1):
        d = day - timedelta(days=i)
        ds = _doses(con, case_id, d)
        if d == config.today():
            ds = [x for x in ds if x["time"] <= config.now_hm()]  # only doses already due today
        tk = [x for x in ds if x["taken"]]
        expected += len(ds)
        taken += len(tk)
        for x in tk:
            k = x["taken_by"] or ""
            by_member[k] = by_member.get(k, 0) + 1
        per_day.append({"date": d.isoformat(), "expected": len(ds), "taken": len(tk)})
    streak = 0
    for p in reversed(per_day[:-1] if per_day and per_day[-1]["expected"] > per_day[-1]["taken"] else per_day):
        if p["expected"] and p["taken"] == p["expected"]:
            streak += 1
        elif p["expected"]:
            break
    return {"days": days, "expected": expected, "taken": taken, "pct": round(100 * taken / expected) if expected else None,
            "streak": streak, "per_day": per_day, "by_member": by_member}


def _notices(con, case_id: int, d: date) -> list[dict]:
    """Things worth doing before they become a problem."""
    out, iso = [], d.isoformat()
    for e in db.rows(con, "SELECT * FROM events WHERE case_id=? AND kind='hearing' AND date>=? AND date<=?", case_id, iso, (d + timedelta(days=14)).isoformat()):
        out.append({"level": "warn", "kind": "hearing", "days": (date.fromisoformat(e["date"]) - d).days, "text": e["title"], "date": e["date"], "route": "juicio"})
    for e in db.rows(con, "SELECT * FROM events WHERE case_id=? AND kind IN ('appointment','study') AND date>? AND date<=?", case_id, iso, (d + timedelta(days=3)).isoformat()):
        out.append({"level": "info", "kind": "visit", "days": (date.fromisoformat(e["date"]) - d).days, "text": e["title"], "date": e["date"], "route": "calendario"})
    for m in _to_buy(con, case_id, d):
        age = (d - date.fromisoformat(m["start_date"])).days
        out.append({"level": "warn" if age >= 1 else "info", "kind": "buy", "days": age, "text": m["name"], "document_id": m["document_id"], "route": "hoy"})
    # medication that runs out soon: bought quantity / doses per day
    bought = db.rows(con, "SELECT doc_date, extracted_json FROM documents WHERE case_id=? AND doc_type IN ('invoice','receipt') AND doc_date<=?", case_id, iso)
    for m in db.rows(con, "SELECT * FROM medications WHERE case_id=? AND every_hours IS NOT NULL AND start_date<=? AND (end_date IS NULL OR end_date>=?)", case_id, iso, iso):
        key = _norm_word(m["name"])
        for b in bought:
            for li in json.loads(b["extracted_json"] or "{}").get("line_items") or []:
                desc = (li.get("description") or "").lower()
                q = QTY.search(desc)
                if key and key in desc and q:
                    qty = int(q.group(1) or q.group(2))
                    runout = date.fromisoformat(b["doc_date"]) + timedelta(days=int(qty / (24 / m["every_hours"])))
                    left = (runout - d).days
                    if 0 <= left <= 5:
                        out.append({"level": "warn", "kind": "runout", "days": left, "text": m["name"], "date": runout.isoformat(), "route": "tratamiento"})
    policy = db.row(con, "SELECT * FROM insurance WHERE case_id=?", case_id)
    pending = db.rows(con, "SELECT date, amount FROM expenses WHERE case_id=? AND reimbursable=1 AND claim_status='to_submit'", case_id)
    left = [((db.claim_due(policy, e["date"]) - d).days if db.claim_due(policy, e["date"]) else None, e["amount"]) for e in pending]
    soon = [(n, a) for n, a in left if n is not None and 0 <= n <= 10]
    if soon:
        out.append({"level": "warn", "kind": "claim", "days": min(n for n, _ in soon), "count": len(soon), "amount": sum(a for _, a in soon), "route": "seguro"})
    late = [(n, a) for n, a in left if n is not None and n < 0]
    if late:
        out.append({"level": "warn", "kind": "claim_late", "count": len(late), "amount": sum(a for _, a in late), "route": "seguro"})
    if policy and policy["coverage_limit"]:
        used = db.row(con, "SELECT COALESCE(SUM(COALESCE(reimbursed_amount, amount)),0) n FROM expenses WHERE case_id=? AND claim_status IN ('submitted','approved','paid')", case_id)["n"]
        if used >= 0.8 * policy["coverage_limit"]:
            out.append({"level": "warn", "kind": "coverage", "pct": round(100 * used / policy["coverage_limit"]), "route": "seguro"})
    order = {"warn": 0, "info": 1}
    return sorted(out, key=lambda n: (order.get(n["level"], 2), n.get("days", 99)))


@app.get("/api/cases/{case_id}/adherence")
def adherence(case_id: int, days: int = 7, day: str | None = None):
    with db.connect() as con:
        return _adherence(con, case_id, _day(day), max(1, min(days, 60)))


@app.get("/api/config")
def get_config():
    return {"today": config.today().isoformat(), "now": config.now_hm(),"ai_connected": bool(config.AMD_API_KEY and config.AMD_API_BASE_URL),
            "vision_model": config.AMD_VISION_MODEL, "vision_fallback": config.AMD_VISION_FALLBACK, "text_model": config.AMD_TEXT_MODEL}


@app.get("/api/cases")
def list_cases():
    with db.connect() as con:
        cases = db.rows(con, "SELECT * FROM cases ORDER BY id")
    for c in cases:  # each case's own "today" and clock (demo cases are replayed)
        c["today"], c["now"] = config.today(bool(c.get("replay"))).isoformat(), config.now_hm(bool(c.get("replay")))
    return cases


@app.post("/api/cases")
def create_case(data: dict = Body(...)):
    """A new, empty case: a person or a pet, with the family members who will use it."""
    title = (data.get("title") or "").strip()[:80]
    subject = (data.get("subject_name") or title).strip()[:80]
    kind = data.get("subject_kind") if data.get("subject_kind") in ("person", "pet") else "person"
    if not title:
        raise HTTPException(400, "The case needs a name")
    members = [m.strip()[:40] for m in (data.get("members") or "").split(",") if m.strip()][:6] or ["Familia"]
    colors = ["#167D8D", "#3E8FB0", "#B08530", "#8A6E9E", "#7A8A3E", "#9C5B3B"]
    with db.connect() as con:
        case_id = con.execute("INSERT INTO cases (title, subject_name, subject_kind, summary) VALUES (?,?,?,?)",
                              (title, subject, kind, (data.get("summary") or "").strip()[:300])).lastrowid
        con.executemany("INSERT INTO members (case_id, name, role, color) VALUES (?,?,?,?)",
                        [(case_id, m, "family", colors[i % len(colors)]) for i, m in enumerate(members)])
        return db.row(con, "SELECT * FROM cases WHERE id=?", case_id)


@app.get("/api/cases/{case_id}/summary")
def summary(case_id: int, day: str | None = None):
    d = _day(day)
    iso = d.isoformat()
    with db.connect() as con:
        case = db.row(con, "SELECT * FROM cases WHERE id=?", case_id)
        if not case:
            raise HTTPException(404, "Case not found")
        spend = db.rows(con, "SELECT category, SUM(amount) AS amount FROM expenses WHERE case_id=? AND date=? GROUP BY category ORDER BY amount DESC", case_id, iso)
        first = db.row(con, "SELECT MIN(date) AS d FROM events WHERE case_id=? AND kind='accident'", case_id)
        claim = db.row(con, "SELECT COUNT(*) AS n, COALESCE(SUM(amount),0) AS amount FROM expenses WHERE case_id=? AND reimbursable=1 AND claim_status='to_submit'", case_id)
        return {
            "case": case,
            "members": db.rows(con, "SELECT * FROM members WHERE case_id=?", case_id),
            "today": iso,
            "case_day": (d - date.fromisoformat(first["d"])).days + 1 if first and first["d"] else None,
            "doses": _doses(con, case_id, d),
            "events": db.rows(con, "SELECT * FROM events WHERE case_id=? AND date=? ORDER BY time", case_id, iso),
            "spend": {"total": sum(s["amount"] for s in spend), "by_category": spend},
            "claim_pending": claim,
            "findings": db.rows(con, """SELECT * FROM findings WHERE case_id=? AND status='open' AND severity!='info'
                                        ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END, id""", case_id),
            "tasks_pending": db.row(con, "SELECT COUNT(*) AS n FROM tasks WHERE case_id=? AND status='pending'", case_id)["n"],
            "questions": db.rows(con, "SELECT * FROM questions WHERE case_id=? AND status='open'", case_id),
            "next_events": db.rows(con, "SELECT * FROM events WHERE case_id=? AND date>? ORDER BY date, time LIMIT 5", case_id, iso),
            "to_buy": _to_buy(con, case_id, d),
            "instructions": db.rows(con, """SELECT i.*, d.title AS document_title FROM instructions i LEFT JOIN documents d ON d.id=i.document_id
                                            WHERE i.case_id=? AND (i.start_date IS NULL OR i.start_date<=?) AND (i.until IS NULL OR i.until>=?)
                                            ORDER BY i.polarity DESC, i.start_date DESC""", case_id, iso, iso),
            "notices": _notices(con, case_id, d),
            "adherence": _adherence(con, case_id, d),
            "key_contacts": sorted([c for c in contacts(case_id) if c["phones"] and c["group"] in ("emergency", "doctor", "clinic")],
                                   key=lambda c: ("emergency", "doctor", "clinic").index(c["group"]))[:6],
        }


@app.get("/api/cases/{case_id}/doses")
def doses_range(case_id: int, start: str | None = None, days: int = 7):
    """Doses for several consecutive days (weekly treatment grid)."""
    first = _day(start)
    with db.connect() as con:
        return {"start": first.isoformat(),
                "days": [{"date": (first + timedelta(days=i)).isoformat(), "doses": _doses(con, case_id, first + timedelta(days=i))}
                         for i in range(max(1, min(days, 31)))]}


@app.get("/api/cases/{case_id}/calendar")
def calendar(case_id: int, month: str | None = None):
    """Everything dated in one month: events, treatment courses, expenses and documents per day."""
    first = date.fromisoformat((month or config.today().isoformat()[:7]) + "-01")
    last = (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    a, b = first.isoformat(), last.isoformat()
    with db.connect() as con:
        meds = db.rows(con, """SELECT id, name, dose, every_hours, start_date, end_date, document_id FROM medications
                               WHERE case_id=? AND start_date IS NOT NULL AND start_date<=? AND (end_date IS NULL OR end_date>=?)
                               AND (end_date IS NOT NULL OR start_date>=?)""", case_id, b, a, (first - timedelta(days=30)).isoformat())
        for m in meds:  # a course without an end date is drawn for 30 days
            m["open_ended"] = m["end_date"] is None
            if m["open_ended"]:
                m["end_date"] = (date.fromisoformat(m["start_date"]) + timedelta(days=29)).isoformat()
        events = db.rows(con, "SELECT * FROM events WHERE case_id=? AND date BETWEEN ? AND ? ORDER BY date, time", case_id, a, b)
        # A visit often only shows up as an invoice: add it as an event when that day has none of that kind.
        kind_of = {"doctor_fees": "appointment", "lab_imaging": "study", "therapy": "session", "hospitalization": "surgery"}
        for e in db.rows(con, """SELECT date, category, vendor, description, document_id FROM expenses
                                 WHERE case_id=? AND date BETWEEN ? AND ?""", case_id, a, b):
            k = kind_of.get(e["category"])
            if k and not any(x["date"] == e["date"] and x["kind"] == k for x in events):
                label = short_topic((e["description"] or "").split(";")[0], 30) or e["vendor"]
                events.append({"date": e["date"], "time": None, "kind": k, "title": f"{label} · {e['vendor'] or ''}".strip(" ·"),
                               "place": e["vendor"], "document_id": e["document_id"], "from_invoice": True})
        events.sort(key=lambda x: (x["date"], x.get("time") or ""))
        return {
            "month": a[:7], "today": config.today().isoformat(),
            "events": events,
            "courses": [m for m in meds if m["end_date"] >= a],
            "expenses": db.rows(con, """SELECT date, SUM(amount) AS amount, COUNT(*) AS n, GROUP_CONCAT(vendor, ' · ') AS vendors FROM expenses
                                        WHERE case_id=? AND date BETWEEN ? AND ? GROUP BY date""", case_id, a, b),
            "documents": db.rows(con, "SELECT id, doc_type, title, doc_date FROM documents WHERE case_id=? AND doc_date BETWEEN ? AND ?", case_id, a, b),
            "tasks": db.rows(con, """SELECT t.*, d.doc_date FROM tasks t LEFT JOIN documents d ON d.id=t.document_id
                                     WHERE t.case_id=? AND t.status='pending' AND d.doc_date BETWEEN ? AND ?""", case_id, a, b),
        }


@app.get("/api/cases/{case_id}/evolution")
def evolution(case_id: int):
    """The case history in date order: events, medication courses, instructions and clinical documents, each linked to its source."""
    items = []
    with db.connect() as con:
        events = db.rows(con, "SELECT * FROM events WHERE case_id=? ORDER BY date, time", case_id)
        sessions = [e for e in events if e["kind"] == "session"]
        for e in events:
            if e["kind"] != "session":
                group = "legal" if e["kind"] == "hearing" else "study" if e["kind"] == "study" else "clinical"
                items.append({"date": e["date"], "time": e["time"], "group": group, "kind": e["kind"], "title": e["title"],
                              "detail": e["notes"], "document_id": e["document_id"]})
        # physiotherapy sessions: one entry per run of sessions less than 15 days apart
        run = []
        for s in sessions + [None]:
            if run and (s is None or (date.fromisoformat(s["date"]) - date.fromisoformat(run[-1]["date"])).days > 15):
                items.append({"date": run[0]["date"], "group": "clinical", "kind": "session", "count": len(run),
                              "title": run[0]["title"], "until": run[-1]["date"], "document_id": run[0]["document_id"]})
                run = []
            if s:
                run.append(s)
        for m in db.rows(con, "SELECT * FROM medications WHERE case_id=? AND start_date IS NOT NULL", case_id):
            items.append({"date": m["start_date"], "group": "medication", "kind": "med_start", "title": m["name"], "dose": m["dose"],
                          "every_hours": m["every_hours"], "until": m["end_date"], "detail": m["instructions"], "document_id": m["document_id"]})
        for i in db.rows(con, "SELECT * FROM instructions WHERE case_id=? AND start_date IS NOT NULL", case_id):
            items.append({"date": i["start_date"], "group": "clinical", "kind": "instruction", "polarity": i["polarity"], "title": i["text"],
                          "until": i["until"], "document_id": i["document_id"]})
        linked = {x["document_id"] for x in items if x.get("document_id")}
        for d in db.rows(con, """SELECT id, doc_type, title, doc_date, issuer, summary, extracted_json, file_path FROM documents WHERE case_id=?
                                 AND doc_date IS NOT NULL AND doc_type IN ('medical_report','study_result','imaging','photo','referral','legal')""", case_id):
            x = json.loads(d["extracted_json"] or "{}")
            if d["id"] in linked and d["doc_type"] not in ("imaging", "photo", "study_result"):
                continue
            items.append({"date": d["doc_date"], "group": "legal" if d["doc_type"] == "legal" else "study" if d["doc_type"] in ("study_result", "imaging") else "clinical",
                          "kind": "doc_" + d["doc_type"], "title": d["title"], "detail": x.get("diagnosis_text") or (d["summary"] or "")[:200],
                          "document_id": d["id"], "thumb": d["doc_type"] in ("imaging", "photo") and bool(re.search(r"\.(jpe?g|png|webp)$", d["file_path"] or "", re.I))})
    items.sort(key=lambda x: (x["date"], x.get("time") or ""))
    return items


@app.get("/api/cases/{case_id}/instructions")
def instructions(case_id: int):
    with db.connect() as con:
        return db.rows(con, """SELECT i.*, d.title AS document_title FROM instructions i LEFT JOIN documents d ON d.id=i.document_id
                               WHERE i.case_id=? ORDER BY i.start_date DESC, i.kind""", case_id)


# Products people compare prices for; anything else is grouped by who offered it.
QUOTE_PRODUCTS = [
    ("Silla de ruedas", r"silla|wheelchair|sedia a rotelle"),
    ("Cama o colchón", r"cama|colch[oó]n|antiescara"),
    ("Muletas y bastones", r"muleta|bast[oó]n|andador|crutch"),
    ("Bacín u orinal", r"bac[ií]n|orinal|chata|c[oó]modo|cu[ñn]a"),
    ("Colcha o protector", r"colcha|protector|sabanilla"),
    ("Tensiómetro", r"tensi[oó]metro"),
]
QUOTE_NOISE = re.compile(r"informaci[oó]n de contacto|captura de pantalla|costo de env[ií]o|delivery|^oferta de", re.I)


def _quote_product(*texts: str) -> str | None:
    for label, pat in QUOTE_PRODUCTS:
        if any(t and re.search(pat, t, re.I) for t in texts):
            return label
    return None


@app.get("/api/cases/{case_id}/quotes")
def quotes(case_id: int):
    """Price quotes and product offers, grouped by product, with the purchase that followed (if any)."""
    with db.connect() as con:
        docs = db.rows(con, "SELECT id, title, doc_date, issuer, extracted_json FROM documents WHERE case_id=? AND doc_type='quote' ORDER BY doc_date", case_id)
        bought = db.rows(con, "SELECT date, vendor, amount, description, document_id FROM expenses WHERE case_id=?", case_id)
    groups: dict[str, dict] = {}
    for d in docs:
        x = json.loads(d["extracted_json"] or "{}")
        items = x.get("line_items") or [{"description": d["title"], "amount": x.get("total")}]
        phones = [p for c in x.get("contacts") or [] for p in c.get("phones") or []]
        for li in items:
            desc = li.get("description") or ""
            noise = bool(QUOTE_NOISE.search(desc))
            product = _quote_product(desc) or (_quote_product(d["title"], d["issuer"]) if noise or len(items) == 1 else None)
            if not product and noise:
                continue  # a delivery fee or a contact card on its own is not an offer
            key = product or f"{d['issuer'] or d['title']}"
            g = groups.setdefault(key, {"product": key, "options": [], "purchase": None})
            price = li.get("amount") or None  # a missing price is read as 0 by the model
            g["options"].append({"document_id": d["id"], "date": d["doc_date"], "seller": d["issuer"],
                                 "item": d["issuer"] if noise else desc, "price": price, "phone": phones[0] if phones else None})
    for key, g in groups.items():
        pat = next((p for label, p in QUOTE_PRODUCTS if label == key), None)
        hit = pat and next((b for b in bought if re.search(pat, b["description"] or "", re.I)), None)
        if hit:
            g["purchase"] = hit
    return sorted(groups.values(), key=lambda g: (g["purchase"] is None, -len(g["options"])))


@app.get("/api/cases/{case_id}/diagnoses")
def diagnoses(case_id: int):
    """Every diagnosis written on a medical paper, as written, with who wrote it and when."""
    with db.connect() as con:
        docs = db.rows(con, """SELECT id, doc_date, doc_type, title, issuer, extracted_json FROM documents WHERE case_id=?
                               AND doc_type NOT IN ('legal','invoice','receipt','quote') ORDER BY doc_date IS NULL, doc_date""", case_id)
    out = []
    for d in docs:
        x = json.loads(d["extracted_json"] or "{}")
        text = (x.get("diagnosis_text") or "").strip()
        if text:
            doc = x.get("doctor") or {}
            out.append({"document_id": d["id"], "date": d["doc_date"], "title": d["title"], "doc_type": d["doc_type"],
                        "diagnosis": text, "doctor": doc.get("name"), "specialty": doc.get("specialty"), "issuer": d["issuer"]})
    return out


@app.get("/api/cases/{case_id}/study-orders")
def study_orders(case_id: int):
    """Medical tests that were ordered, grouped by the paper that ordered them, with whether they are done."""
    with db.connect() as con:
        tasks = db.rows(con, """SELECT t.id, t.title, t.status, t.document_id, d.doc_date, d.title AS doc_title, d.issuer, d.extracted_json
                                FROM tasks t JOIN documents d ON d.id=t.document_id WHERE t.case_id=? AND t.kind='study'
                                ORDER BY d.doc_date IS NULL, d.doc_date DESC, t.id""", case_id)
    orders: dict[int, dict] = {}
    for t in tasks:
        x = json.loads(t.pop("extracted_json") or "{}")
        o = orders.setdefault(t["document_id"], {"document_id": t["document_id"], "date": t["doc_date"], "title": t["doc_title"],
                                                 "issuer": t["issuer"], "doctor": (x.get("doctor") or {}).get("name"),
                                                 "reason": next((s.get("reason") for s in x.get("studies_requested") or [] if s.get("reason")), None),
                                                 "studies": []})
        o["studies"].append({"id": t["id"], "name": t["title"], "status": t["status"]})
    return list(orders.values())


@app.get("/api/cases/{case_id}/to-buy")
def to_buy(case_id: int):
    with db.connect() as con:
        return _to_buy(con, case_id, config.today())


@app.get("/api/cases/{case_id}/expenses")
def expenses(case_id: int):
    with db.connect() as con:
        items = db.rows(con, """SELECT e.*, d.title AS document_title, d.extracted_json, m.name AS paid_by_name FROM expenses e
                                LEFT JOIN documents d ON d.id=e.document_id LEFT JOIN members m ON m.id=e.paid_by
                                WHERE e.case_id=? ORDER BY e.date DESC, e.id DESC""", case_id)
        for i in items:  # what each expense was for: the invoice lines and any open problem on its document
            i["line_items"] = (json.loads(i.pop("extracted_json") or "{}") or {}).get("line_items") or []
            i["problems"] = [f["detail"] for f in db.rows(con, """SELECT detail FROM findings WHERE document_id=? AND status='open'
                                                                   AND severity!='info'""", i["document_id"])] if i["document_id"] else []
            note = db.row(con, "SELECT detail FROM findings WHERE document_id=? AND kind='not_medical'", i["document_id"]) if i["document_id"] else None
            i["note"] = note["detail"] if note else None
        return {
            "total": sum(i["amount"] for i in items),
            "reimbursable": sum(i["amount"] for i in items if i["reimbursable"]),
            "by_category": db.rows(con, "SELECT category, SUM(amount) AS amount, COUNT(*) AS n FROM expenses WHERE case_id=? GROUP BY category ORDER BY amount DESC", case_id),
            "by_day": db.rows(con, "SELECT date, SUM(amount) AS amount FROM expenses WHERE case_id=? GROUP BY date ORDER BY date", case_id),
            "by_member": db.rows(con, """SELECT COALESCE(m.name,'') AS name, SUM(e.amount) AS amount FROM expenses e
                                         LEFT JOIN members m ON m.id=e.paid_by WHERE e.case_id=? GROUP BY e.paid_by""", case_id),
            "items": items,
        }


@app.patch("/api/expenses/{expense_id}")
def update_expense(expense_id: int, data: dict = Body(...)):
    allowed = {k: v for k, v in data.items() if k in ("paid_by", "claim_status", "category", "reimbursed_amount", "reimbursable")}
    if not allowed:
        raise HTTPException(400, "Nothing to update")
    with db.connect() as con:
        con.execute(f"UPDATE expenses SET {', '.join(k + '=?' for k in allowed)} WHERE id=?", (*allowed.values(), expense_id))
        return db.row(con, "SELECT * FROM expenses WHERE id=?", expense_id)


@app.get("/api/cases/{case_id}/documents")
def documents(case_id: int):
    with db.connect() as con:
        return db.rows(con, """SELECT id, doc_type, title, doc_date, issuer, handwritten, status, file_path FROM documents
                               WHERE case_id=? ORDER BY doc_date IS NULL, doc_date DESC, id DESC""", case_id)


@app.get("/api/documents/{doc_id}")
def document(doc_id: int):
    """A document plus everything that was extracted from it (traceability)."""
    with db.connect() as con:
        doc = db.row(con, "SELECT * FROM documents WHERE id=?", doc_id)
        if not doc:
            raise HTTPException(404, "Document not found")
        doc["extracted"] = json.loads(doc.pop("extracted_json") or "null")
        doc["linked"] = {t: db.rows(con, f"SELECT * FROM {t} WHERE document_id=?", doc_id) for t in LINKED}
        return doc


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: int):
    """Remove a document and everything extracted from it (the stored file is kept on disk)."""
    with db.connect() as con:
        doc = db.row(con, "SELECT case_id FROM documents WHERE id=?", doc_id)
        if not doc:
            raise HTTPException(404, "Document not found")
        con.execute("DELETE FROM dose_log WHERE medication_id IN (SELECT id FROM medications WHERE document_id=?)", (doc_id,))
        for t in (*LINKED, "questions"):
            con.execute(f"DELETE FROM {t} WHERE document_id=?", (doc_id,))
        con.execute("UPDATE ai_calls SET document_id=NULL WHERE document_id=?", (doc_id,))  # keep the call history
        con.execute("UPDATE findings SET related_document_id=NULL WHERE related_document_id=?", (doc_id,))
        con.execute("UPDATE tasks SET resolved_document_id=NULL WHERE resolved_document_id=?", (doc_id,))
        con.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        audit.audit_case(con, doc["case_id"])
    return {"ok": True}


@app.get("/api/documents/{doc_id}/file")
def document_file(doc_id: int):
    with db.connect() as con:
        doc = db.row(con, "SELECT file_path FROM documents WHERE id=?", doc_id)
    path = (config.ROOT / doc["file_path"]).resolve() if doc and doc["file_path"] else None
    roots = {config.ROOT.resolve(), config.DATA_DIR.resolve()}
    if not path or not path.is_file() or not roots & set(path.parents):
        raise HTTPException(404, "File not found")
    return FileResponse(path)


@app.post("/api/cases/{case_id}/documents")
def upload_document(case_id: int, file: UploadFile = File(...)):
    """Save a photo/PDF, read it with the AMD vision model, store what it says and audit it."""
    if not ai.connected():
        raise HTTPException(503, "AMD AI is not connected")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_UPLOADS:
        raise HTTPException(400, f"Unsupported file type {ext or '(none)'}: use JPG, PNG, WEBP or PDF")
    with db.connect() as con:
        case = db.row(con, "SELECT * FROM cases WHERE id=?", case_id)
        insurer = db.row(con, "SELECT insurer, nit FROM insurance WHERE case_id=?", case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    dest = config.UPLOAD_DIR / f"case{case_id}" / f"{uuid.uuid4().hex}{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    stored = str(dest.relative_to(config.ROOT)) if config.ROOT in dest.parents else str(dest)
    with db.connect() as con:
        doc_id = con.execute("INSERT INTO documents (case_id, doc_type, title, file_path, status) VALUES (?,?,?,?,'processing')",
                             (case_id, "other", file.filename, stored)).lastrowid
    try:
        extracted = ai.extract_document(dest, case, insurer, case_id=case_id, document_id=doc_id)
    except Exception as e:
        with db.connect() as con:
            con.execute("UPDATE documents SET status='error', summary=? WHERE id=?", (str(e)[:500], doc_id))
        raise HTTPException(502, f"The AMD model could not read the document: {e}")
    with db.connect() as con:
        ingest_item(con, case_id, extracted, stored, doc_id)
        audit.audit_case(con, case_id)  # a new document can change what the rules see (e.g. the case's body side)
    return document(doc_id)


@app.post("/api/cases/{case_id}/ask")
def ask_case(case_id: int, data: dict = Body(...)):
    if not ai.connected():
        raise HTTPException(503, "AMD AI is not connected")
    question = (data.get("question") or "").strip()
    if not question:
        raise HTTPException(400, "Empty question")
    try:
        return {"answer": ai.ask(case_id, question, data.get("lang", "es"))}
    except Exception as e:
        raise HTTPException(502, f"The AMD model could not answer: {e}")


@app.get("/api/cases/{case_id}/medications")
def medications(case_id: int, day: str | None = None):
    with db.connect() as con:
        return {"items": db.rows(con, "SELECT * FROM medications WHERE case_id=? ORDER BY start_date DESC", case_id),
                "doses": _doses(con, case_id, _day(day))}


@app.post("/api/cases/{case_id}/medications")
def add_medication(case_id: int, data: dict = Body(...)):
    """A medication entered by hand (what the doctor said out loud, or a missing prescription)."""
    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "Name is required")
    start = data.get("start_date") or config.today().isoformat()
    days = int(data.get("days") or 0)
    end = (date.fromisoformat(start) + timedelta(days=days - 1)).isoformat() if days > 0 else None
    hours = int(data.get("every_hours") or 0) or None
    with db.connect() as con:
        con.execute("""INSERT INTO medications (case_id, name, dose, instructions, every_hours, first_time, start_date, end_date)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (case_id, name, data.get("dose"), data.get("instructions"), hours, data.get("first_time") or "08:00", start, end))
    return {"ok": True}


@app.post("/api/medications/{med_id}/doses")
def take_dose(med_id: int, data: dict = Body(...)):
    with db.connect() as con:
        con.execute("INSERT OR IGNORE INTO dose_log (medication_id, scheduled_at, member_id) VALUES (?,?,?)",
                    (med_id, data["scheduled_at"], data.get("member_id")))
    return {"ok": True}


@app.delete("/api/medications/{med_id}/doses")
def untake_dose(med_id: int, scheduled_at: str):
    with db.connect() as con:
        con.execute("DELETE FROM dose_log WHERE medication_id=? AND scheduled_at=?", (med_id, scheduled_at))
    return {"ok": True}


@app.get("/api/cases/{case_id}/timeline")
def timeline(case_id: int):
    with db.connect() as con:
        return db.rows(con, """SELECT date, time, kind, title, place, document_id, 'event' AS source FROM events WHERE case_id=?
                               UNION ALL
                               SELECT doc_date, NULL, doc_type, title, issuer, id, 'document' FROM documents
                               WHERE case_id=? AND doc_date IS NOT NULL AND doc_type NOT IN ('photo','screenshot')
                               ORDER BY 1, 2""", case_id, case_id)


@app.get("/api/cases/{case_id}/contacts")
def contacts(case_id: int):
    with db.connect() as con:
        items = db.rows(con, "SELECT * FROM contacts WHERE case_id=? ORDER BY is_emergency DESC, name", case_id)
    for c in items:
        c["phones"] = json.loads(c["phones"] or "[]")
        c["group"] = _contact_group(c)
    return items


@app.post("/api/cases/{case_id}/contacts")
def add_contact(case_id: int, data: dict = Body(...)):
    name, phone = (data.get("name") or "").strip(), (data.get("phone") or "").strip()
    if not name:
        raise HTTPException(400, "Name is required")
    with db.connect() as con:
        con.execute("INSERT INTO contacts (case_id, name, role, phones, is_emergency) VALUES (?,?,?,?,?)",
                    (case_id, name, data.get("role"), json.dumps([phone] if phone else []), 1 if data.get("is_emergency") else 0))
    return {"ok": True}


@app.get("/api/cases/{case_id}/tasks")
def tasks(case_id: int):
    with db.connect() as con:
        return db.rows(con, """SELECT t.*, d.title AS document_title, d.doc_date FROM tasks t
                               LEFT JOIN documents d ON d.id=t.document_id WHERE t.case_id=? ORDER BY t.status, d.doc_date""", case_id)


@app.get("/api/cases/{case_id}/findings")
def findings(case_id: int):
    with db.connect() as con:
        return db.rows(con, """SELECT f.*, d.doc_date FROM findings f LEFT JOIN documents d ON d.id=f.document_id
                               WHERE f.case_id=? ORDER BY f.status, CASE f.severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END""", case_id)


@app.post("/api/questions/{qid}/answer")
def answer_question(qid: int, data: dict = Body(...)):
    """Store a person's answer. An answered illegible drug name replaces the '(ilegible)' placeholder."""
    answer = (data.get("answer") or "").strip()
    if not answer:
        raise HTTPException(400, "Empty answer")
    with db.connect() as con:
        q = db.row(con, "SELECT * FROM questions WHERE id=?", qid)
        if not q:
            raise HTTPException(404, "Question not found")
        con.execute("UPDATE questions SET answer=?, status='answered' WHERE id=?", (answer, qid))
        if q["document_id"] and re.search(r"medicament|f[aá]rmaco|droga|nombre del", q["question"], re.I):
            con.execute("UPDATE medications SET name=?, confidence=1.0 WHERE document_id=? AND name LIKE '%ilegible%'",
                        (answer, q["document_id"]))
    return {"ok": True}


@app.patch("/api/{table}/{item_id}")
def set_status(table: str, item_id: int, data: dict = Body(...)):
    if table not in ("tasks", "findings", "questions") or "status" not in data:
        raise HTTPException(400, "Unsupported update")
    with db.connect() as con:
        con.execute(f"UPDATE {table} SET status=? WHERE id=?", (data["status"], item_id))
    return {"ok": True}


@app.get("/api/cases/{case_id}/insurance")
def insurance(case_id: int):
    with db.connect() as con:
        policy = db.row(con, "SELECT * FROM insurance WHERE case_id=?", case_id)
        items = db.rows(con, "SELECT * FROM expenses WHERE case_id=? AND reimbursable=1 ORDER BY date", case_id)
    recovered = sum(i["reimbursed_amount"] or 0 for i in items if i["claim_status"] in ("approved", "paid"))
    by_status: dict[str, dict] = {}
    for i in items:
        s = by_status.setdefault(i["claim_status"], {"n": 0, "amount": 0.0})
        s["n"] += 1
        s["amount"] += i["amount"]
    return {"policy": policy, "recovered": recovered,
            "remaining": (policy["coverage_limit"] - recovered) if policy and policy["coverage_limit"] else None,
            "by_status": by_status, "items": items}


@app.get("/api/cases/{case_id}/packages/{kind}")
def package_preview(case_id: int, kind: str):
    if kind == "insurance":
        return paquetes.insurance_preview(case_id)
    if kind == "legal":
        return paquetes.legal_preview(case_id)
    raise HTTPException(404, "Unknown package")


@app.post("/api/cases/{case_id}/packages/{kind}")
def package_build(case_id: int, kind: str):
    try:
        out = (paquetes.insurance_package(case_id) if kind == "insurance" else paquetes.legal_package(case_id) if kind == "legal"
               else paquetes.visit_package(case_id) if kind == "visit" else None)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if out is None:
        raise HTTPException(404, "Unknown package")
    out["url"] = f"/api/packages/{out['file']}"
    return out


@app.post("/api/cases/{case_id}/packages/insurance/submitted")
def package_submitted(case_id: int):
    return {"marked": paquetes.mark_submitted(case_id)}


@app.get("/api/packages/{name}")
def package_file(name: str):
    path = (config.DATA_DIR / "paquetes" / name).resolve()
    if path.parent != (config.DATA_DIR / "paquetes").resolve() or not path.is_file():
        raise HTTPException(404, "Package not found")
    return FileResponse(path, media_type="application/pdf", filename=name)


@app.get("/api/ai-calls")
def ai_calls(limit: int = 50):
    with db.connect() as con:
        return {
            "calls": db.rows(con, """SELECT a.*, d.title AS document_title FROM ai_calls a LEFT JOIN documents d ON d.id=a.document_id
                                     ORDER BY a.id DESC LIMIT ?""", limit),
            "totals": db.rows(con, """SELECT model, COUNT(*) AS n, SUM(ok) AS ok, ROUND(AVG(latency_ms)) AS avg_ms,
                                      SUM(input_tokens) AS tin, SUM(output_tokens) AS tout FROM ai_calls GROUP BY model"""),
            "endpoint": config.AMD_API_BASE_URL,
        }


class WebFiles(StaticFiles):
    """The web app, always revalidated so a new version shows up on the next reload."""
    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        resp.headers["Cache-Control"] = "no-cache"
        return resp


app.mount("/", WebFiles(directory=config.WEB_DIR, html=True), name="web")

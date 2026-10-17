"""Turn one extracted document (ground-truth schema, see docs/ground_truth_schema.md) into case records.

Used by the seed loader and by the AI pipeline. Every record keeps the document it came from.
"""
import json
import re
import sqlite3
import unicodedata
from datetime import date, timedelta
from difflib import SequenceMatcher

from . import db


def norm(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", s).split())


WORD_NUMBERS = {"una": 1, "un": 1, "dos": 2, "tres": 3, "cuatro": 4, "seis": 6}


def every_hours(freq: str | None) -> int | None:
    """Hours between doses from how prescriptions write it: "c/8h", "cada 12 horas", "2 veces x día", "x día", "diario"."""
    f = (freq or "").lower()
    for word, n in WORD_NUMBERS.items():
        f = re.sub(rf"\b{word}\b", str(n), f)
    m = re.search(r"(?:c\s*/\s*|cada\s+)?(\d+)\s*(h|hs|hrs|horas)\b", f) or re.search(r"(?:c\s*/\s*|cada\s+)(\d+)\b", f)
    if m and 0 < int(m.group(1)) <= 72:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*(veces|vez)\s*(al|por|x|/|a\s+el)?\s*d", f)
    if m and int(m.group(1)):
        return 24 // int(m.group(1))
    return 24 if re.search(r"(cada|por|al|x|/)\s*d[ií]a|diari|24\s*h|daily", f) else None


def duration_days(d: str | None) -> int | None:
    f = (d or "").lower()
    m = re.search(r"(\d+)\s*(d|semana|mes)", f)
    if not m:
        return None
    n = int(m.group(1))
    return n * 30 if m.group(2) == "mes" else n * 7 if m.group(2) == "semana" else n


def valid_date(s: str | None) -> str | None:
    try:
        return date.fromisoformat(s).isoformat() if s else None
    except ValueError:
        return None


def short_topic(text: str, limit: int = 44) -> str:
    """A short topic from a long description: the first clause, cut at a word boundary."""
    s = re.split(r"[.;:(]|,\s| que | por | para ", (text or "").strip(), maxsplit=1)[0].strip()
    if len(s) > limit:
        s = s[:limit].rsplit(" ", 1)[0] + "…"
    return s[:1].upper() + s[1:]


CATEGORY_HINTS = [  # (category, words in the invoice lines) to fix "other" when the model was unsure
    ("hospitalization", r"cirug|operac|quir[uú]rg|implante|osteos[ií]ntesis|placa|tornillo|internaci|anestes"),
    ("transport", r"silla de ruedas|muleta|camilla|inmovilizador|andador|colch[oó]n|ambulancia|traslado|taxi|delivery"),
    ("therapy", r"fisioterap|kinesio|rehabilit"),
    ("lab_imaging", r"laborat|hemograma|rayos|radiograf|tomograf|ecograf|doppler|resonanc"),
    ("doctor_fees", r"consulta|honorario"),
]


def better_category(category: str | None, text: str) -> str:
    if category and category != "other":
        return category
    for cat, pat in CATEGORY_HINTS:
        if re.search(pat, text or "", re.I):
            return cat
    return category or "other"


def classify_anomaly(text: str) -> tuple[str, str] | None:
    """(severity, kind) for an anomaly sentence, or None if it is noise."""
    low = text.lower()
    if re.search(r"otro paciente|another patient|different patient", low):
        return "warning", "patient"
    if any(w in low for w in ("duplic", "no relacionad", "unrelated", "publicidad", "anuncio", "ilegible", "lectura dudosa")):
        return None
    if re.search(r"derech|izquierd|right|left|lado", low):
        return "critical", "body_side"
    if re.search(r"fecha|date|anterior al servicio", low):
        return "warning", "date"
    if re.search(r"suma|total escrito|aritm|descuento", low):
        return "warning", "arithmetic"
    if re.search(r"nit|a nombre|seguro|reembols|particular|factura", low):
        return "warning", "billing"
    return "info", "other"


FOOD = re.compile(r"\b(bife|chorizo|restaurante?s?|cerveza|hamburguesa|pizza|parrillada|churrasco|almuerzo|cena|refresco|helado)\b", re.I)


def unrelated(it: dict) -> str | None:
    """Why a document is not part of the health case (a restaurant bill, for instance), or None if it is."""
    if it.get("case_related") is False:
        return it.get("unrelated_reason") or "No tiene relación con el caso de salud."
    if it.get("doc_type") in ("invoice", "receipt") and it.get("case_related") is not True:
        lines = " ".join(str(li.get("description") or "") for li in it.get("line_items") or [])
        if FOOD.search(f"{lines} {it.get('issuer') or ''} {it.get('title') or ''}"):
            return "Parece una cuenta de comida o restaurante."
    return None


def ingest_item(con: sqlite3.Connection, case_id: int, it: dict, file_path: str | None, doc_id: int | None = None) -> int:
    """Store a document and everything extracted from it. Returns the document id."""
    from .audit import other_patient  # local import: audit is a sibling module
    kind = (db.row(con, "SELECT subject_kind FROM cases WHERE id=?", case_id) or {}).get("subject_kind")
    if kind == "pet":  # a vet's paper is this case's own: never "not medical", never "not for a human"
        if it.get("case_related") is False:
            it["case_related"] = None  # only the restaurant-bill rule can still set it apart
        it["anomalies"] = [a for a in it.get("anomalies") or [] if not re.search(r"animal|veterinari|human|mascota|perro|gato", str(a), re.I)]
    foreign = other_patient(con, case_id, it.get("patient_name_as_written")) or any(
        re.search(r"otro paciente|another patient", str(a), re.I) for a in it.get("anomalies") or [])
    not_medical = None if foreign else unrelated(it)  # another patient's paper is medical, just not this case's
    if not_medical:  # kept, but filed apart from the health expenses and never sent to the insurer
        it["not_medical"] = not_medical
        it["anomalies"] = [a for a in it.get("anomalies") or [] if not re.search(r"asegurador|seguro|nombre|nit|insur", str(a), re.I)]
    # Models sometimes return an anomaly as an object (or its JSON text) instead of a sentence.
    def sentence(a):
        if isinstance(a, str) and a.strip().startswith("{"):
            try:
                a = json.loads(a)
            except ValueError:
                return a
        if isinstance(a, dict):
            texts = [v for v in a.values() if isinstance(v, str) and v.strip()]
            return str(a.get("description") or a.get("text") or a.get("detail") or a.get("anomaly")
                       or (texts[0] if len(texts) == 1 else json.dumps(a, ensure_ascii=False)))
        return str(a)
    it["anomalies"] = [sentence(a) for a in it.get("anomalies") or []]
    doc_date = valid_date(it.get("date"))
    values = (it.get("doc_type") or "other", it.get("title") or (file_path or "Documento"), doc_date, it.get("issuer"),
              file_path, 1 if it.get("handwritten") else 0, it.get("notes"), json.dumps(it, ensure_ascii=False))
    if doc_id:
        con.execute("""UPDATE documents SET doc_type=?, title=?, doc_date=?, issuer=?, file_path=?, handwritten=?, summary=?,
                       extracted_json=?, status='processed' WHERE id=?""", (*values, doc_id))
    else:
        doc_id = con.execute("""INSERT INTO documents (doc_type, title, doc_date, issuer, file_path, handwritten, summary,
                                extracted_json, case_id) VALUES (?,?,?,?,?,?,?,?,?)""", (*values, case_id)).lastrowid
    if foreign:  # keep the paper and its warning, but put nothing of it in this patient's schedule or expenses
        it = {**it, "medications": [], "events": [], "instructions": [], "studies_requested": [], "total": None}

    policy = db.row(con, "SELECT nit FROM insurance WHERE case_id=?", case_id)
    insurer_nit = (policy or {}).get("nit") or ""
    reimbursable = bool(insurer_nit) and (it.get("billed_to_nit") or "").replace(" ", "") == insurer_nit and not not_medical

    # The same payment can show up twice: a re-photographed invoice, or a receipt for an invoice.
    dup_doc = any("duplic" in a.lower() for a in it.get("anomalies") or [])
    dup = dup_doc
    if it.get("doc_type") == "invoice" and it.get("invoice_number"):
        number = str(it["invoice_number"]).lstrip("0")
        for e in db.rows(con, "SELECT vendor, invoice_number FROM expenses WHERE case_id=? AND invoice_number IS NOT NULL", case_id):
            if str(e["invoice_number"]).lstrip("0") == number and norm(e["vendor"]) == norm(it.get("issuer")):
                dup = True
    elif it.get("doc_type") == "receipt" and doc_date and it.get("total"):
        dup = dup or bool(db.row(con, "SELECT 1 FROM expenses WHERE case_id=? AND date=? AND amount=?",
                                 case_id, doc_date, float(it["total"])))
    if it.get("total") and doc_date and it.get("doc_type") in ("invoice", "receipt") and not dup:
        lines = "; ".join(li.get("description") or "" for li in it.get("line_items") or [])
        con.execute("""INSERT INTO expenses (case_id, document_id, date, amount, category, vendor, description, invoice_number,
                       billed_to, billed_to_nit, reimbursable, claim_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (case_id, doc_id, doc_date, float(it["total"]), "not_medical" if not_medical else better_category(it.get("expense_category"), f"{lines} {it.get('title') or ''}"), it.get("issuer"),
                     lines or it.get("title"), it.get("invoice_number"), it.get("billed_to"), it.get("billed_to_nit"),
                     1 if reimbursable else 0, "to_submit" if reimbursable else "not_applicable"))

    for m in it.get("medications") or []:
        if not m.get("name") or SUPPLIES.search(m["name"]):
            continue  # medical supplies (syringes, saline, bandages) are not medication to take
        if any(norm(x["name"]) == norm(m["name"]) for x in
               db.rows(con, "SELECT name FROM medications WHERE case_id=? AND start_date IS ?", case_id, doc_date)):
            continue
        days = duration_days(m.get("duration"))
        end = (date.fromisoformat(doc_date) + timedelta(days=days - 1)).isoformat() if doc_date and days else None
        hours = every_hours(m.get("frequency"))
        first = "06:00" if hours and hours <= 8 else "08:00"  # every 8 h -> 06, 14, 22 (all doses fit in the day)
        con.execute("""INSERT INTO medications (case_id, document_id, name, dose, instructions, every_hours, first_time, start_date, end_date)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (case_id, doc_id, m["name"], m.get("dose"),
                     " · ".join(x for x in (m.get("frequency"), m.get("duration"), m.get("instructions")) if x),
                     hours, first, doc_date, end))

    if not dup_doc:
        for s in it.get("studies_requested") or []:
            if s.get("name"):
                side = {"left": " (izquierda)", "right": " (derecha)"}.get(s.get("body_side") or "", "")
                con.execute("INSERT INTO tasks (case_id, document_id, title, kind) VALUES (?,?,?,?)",
                            (case_id, doc_id, s["name"] + side, "study"))
        for e in it.get("events") or []:
            d = valid_date(e.get("date"))
            desc = e.get("description") or ""
            title = (e.get("title") or "").strip() or short_topic(desc)
            if d and title:
                time = re.search(r"\b(\d{1,2}:\d{2})\b", f"{e.get('time') or ''} {desc}")
                con.execute("INSERT INTO events (case_id, document_id, kind, title, date, time, notes) VALUES (?,?,?,?,?,?,?)",
                            (case_id, doc_id, e.get("kind") or "other", title, d, time.group(1).zfill(5) if time else None, desc or None))
        for a in it.get("anomalies") or []:
            cls = classify_anomaly(a)
            if cls:
                con.execute("INSERT INTO findings (case_id, document_id, severity, kind, title, detail) VALUES (?,?,?,?,?,?)",
                            (case_id, doc_id, cls[0], cls[1], it.get("title") or "Documento", a))

    for ins in it.get("instructions") or []:
        if isinstance(ins, dict) and ins.get("text"):
            con.execute("""INSERT INTO instructions (case_id, document_id, kind, polarity, text, start_date, until)
                           VALUES (?,?,?,?,?,?,?)""",
                        (case_id, doc_id, ins.get("kind") or "other", "avoid" if ins.get("polarity") == "avoid" else "do",
                         ins["text"], doc_date, valid_date(ins.get("until"))))

    for q in it.get("questions") or []:
        if isinstance(q, dict) and q.get("question"):
            con.execute("INSERT INTO questions (case_id, document_id, question, options) VALUES (?,?,?,?)",
                        (case_id, doc_id, q["question"], json.dumps([str(o) for o in q.get("options") or []], ensure_ascii=False)))

    existing = db.rows(con, "SELECT id, name, phones FROM contacts WHERE case_id=?", case_id)
    last_id = None
    for c in it.get("contacts") or []:
        if not c.get("name"):
            continue
        phones = [p for p in c.get("phones") or [] if p]
        if norm(c["name"]) in GENERIC_NAMES and last_id:  # e.g. "Secretaria": a phone of the previous contact
            cur = next(x for x in db.rows(con, "SELECT id, phones FROM contacts WHERE id=?", last_id))
            con.execute("UPDATE contacts SET phones=? WHERE id=?",
                        (json.dumps(list(dict.fromkeys(json.loads(cur["phones"] or "[]") + phones))), last_id))
            continue
        cur = next((x for x in existing if same_person(x["name"], c["name"])), None)
        if cur:
            merged = list(dict.fromkeys(json.loads(cur["phones"] or "[]") + phones))
            con.execute("UPDATE contacts SET phones=? WHERE id=?", (json.dumps(merged), cur["id"]))
            cur["phones"] = json.dumps(merged)
            last_id = cur["id"]
        else:
            last_id = con.execute("""INSERT INTO contacts (case_id, document_id, name, role, organization, phones, email, address)
                                     VALUES (?,?,?,?,?,?,?,?)""",
                                  (case_id, doc_id, c["name"], c.get("role_or_specialty"), c.get("organization"),
                                   json.dumps(phones), c.get("email"), c.get("address"))).lastrowid
            existing.append({"id": last_id, "name": c["name"], "phones": json.dumps(phones)})
    return doc_id


SUPPLIES = re.compile(r"equipo|jeringa|br[aou]ula|bránula|cat[eé]ter|sol\.?\s|soluci[oó]n|suero|venda|l[aá]mina|bistur|gasa|guante|"
                      r"algod[oó]n|esparadrapo|sonda|aguja|ap[oó]sito|insumo|arco\s*c|honorario|quir[oó]fano|internaci", re.I)

GENERIC_NAMES = {"secretaria", "secretario", "consultorio", "recepcion", "call center"}
TITLES = {"dr", "dra", "lic", "abg", "abog", "mv", "ing", "sr", "sra"}


def same_person(a: str, b: str) -> bool:
    """Fuzzy match of two contact names ("Dr. Christian Añez" ~ "Dr. Cristian Añez Martínez")."""
    ta = [t for t in norm(a).split() if t not in TITLES and len(t) > 1]
    tb = [t for t in norm(b).split() if t not in TITLES and len(t) > 1]
    if not ta or not tb:
        return False
    if ta == tb:
        return True
    hits = sum(any(SequenceMatcher(None, x, y).ratio() >= 0.8 for y in tb) for x in ta)
    return hits >= min(2, len(ta), len(tb))

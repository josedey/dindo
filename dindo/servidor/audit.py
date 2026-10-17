"""Deterministic case audit. Rules never hallucinate: they complement the AI's own observations.

When a rule and the AI flag the same thing on the same document, the finding is marked as confirmed
by both (source 'ai+rule').
"""
import json
import re
import unicodedata
from datetime import date

from . import db

RANGE = re.compile(r"(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})")


def _dates_in(text: str) -> list[date]:
    out = []
    for d, m, y in RANGE.findall(text or ""):
        y = int(y) + (2000 if len(y) == 2 else 0)
        try:
            out.append(date(y, int(m), int(d)))
        except ValueError:
            pass
    return out


def _side(text: str) -> str | None:
    low = (text or "").lower()
    left, right = bool(re.search(r"izquierd|\bizq\b|left", low)), bool(re.search(r"derech|\bder\b|right", low))
    return "left" if left and not right else "right" if right and not left else None


def case_side(con, case_id: int) -> str | None:
    """The body side of the case: from the case summary, else from the diagnoses (never from the orders being checked)."""
    case = db.row(con, "SELECT summary FROM cases WHERE id=?", case_id)
    side = _side((case or {}).get("summary"))
    if side:
        return side
    votes = {"left": 0, "right": 0}
    for d in db.rows(con, "SELECT extracted_json FROM documents WHERE case_id=?", case_id):
        s = _side(json.loads(d["extracted_json"] or "{}").get("diagnosis_text"))
        if s:
            votes[s] += 1
    if votes["left"] == votes["right"]:
        return None
    return max(votes, key=votes.get)


GENERIC_SUBJECTS = {"paciente", "patient", "mascota", "pet", "persona"}


def _name_words(text: str) -> set[str]:
    plain = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return set(re.findall(r"[a-z]{3,}", plain))


def other_patient(con, case_id: int, written: str | None) -> str | None:
    """A warning when the paper names a different patient than the case's (not one name in common)."""
    case = db.row(con, "SELECT subject_name FROM cases WHERE id=?", case_id)
    subject = (case or {}).get("subject_name") or ""
    if not written or "anonimiz" in written.lower() or _name_words(subject) <= GENERIC_SUBJECTS:
        return None
    paper, ours = _name_words(written), _name_words(subject)
    if not paper or paper & ours:
        return None
    return (f"Este papel dice que es de «{written.strip()}», pero el caso es de «{subject}». ¿Es de otro paciente? "
            f"Si es así, borralo de este caso y subilo al caso correcto.")


def rule_findings(con, case_id: int, doc: dict, x: dict) -> list[tuple[str, str, str]]:
    """(severity, kind, detail) for one document."""
    if x.get("not_medical"):  # a restaurant bill and the like: one friendly note, none of the insurance rules
        return [("info", "not_medical", f"{x['not_medical']} La guardamos en «No médicos», aparte de los gastos de salud. "
                                        "Sirve para saber cuánto se gastó en total; normalmente el seguro no la cubre.")]
    out = []
    other = other_patient(con, case_id, x.get("patient_name_as_written"))
    if other:
        out.append(("warning", "patient", other))
    doc_date = date.fromisoformat(doc["doc_date"]) if doc["doc_date"] else None
    policy = db.row(con, "SELECT insurer, nit FROM insurance WHERE case_id=?", case_id)
    items = x.get("line_items") or []

    if x.get("doc_type") in ("invoice", "receipt") and doc_date:
        service = [d for li in items for d in _dates_in(li.get("description"))] + \
                  [date.fromisoformat(e["date"]) for e in x.get("events") or [] if (e.get("date") or "")[:4].isdigit()]
        if service and doc_date < min(service):
            out.append(("warning", "date", f"La fecha del documento ({doc_date:%d/%m/%Y}) es anterior al servicio que cobra "
                                           f"(desde {min(service):%d/%m/%Y}). El seguro podría rechazarlo."))
    if items and x.get("total") is not None:
        total = sum(float(li.get("amount") or 0) for li in items)
        if abs(total - float(x["total"])) > 0.5:
            out.append(("warning", "arithmetic", f"Los ítems suman {total:,.2f} Bs pero el total dice {float(x['total']):,.2f} Bs."))
    if x.get("doc_type") == "invoice" and policy and policy["nit"] and x.get("total"):
        if (x.get("billed_to_nit") or "").replace(" ", "") != policy["nit"]:
            out.append(("warning", "billing", f"La factura no está a nombre de {policy['insurer']} (NIT {policy['nit']}): "
                                              f"no sería reembolsable. Pedí que la emitan a nombre del seguro."))
    if x.get("doc_type") == "receipt" and x.get("total") and policy:
        out.append(("info", "billing", "Es un recibo, no una factura fiscal: el seguro normalmente no lo reembolsa."))
    side = case_side(con, case_id)
    for st in x.get("studies_requested") or []:
        s = st.get("body_side") or _side(st.get("name"))
        if side and s and s != side:
            names = {"left": "IZQUIERDA", "right": "DERECHA"}
            out.append(("critical", "body_side", f"El estudio pedido ({st.get('name')}) dice {names[s]}, pero el resto del caso "
                                                 f"es del lado {names[side]}. Confirmalo con el médico antes de hacerlo."))
    return out


def audit_document(con, case_id: int, doc_id: int) -> int:
    """Run the rules on one document. Returns how many new findings were added."""
    doc = db.row(con, "SELECT * FROM documents WHERE id=?", doc_id)
    x = json.loads(doc["extracted_json"] or "{}")
    added = 0
    con.execute("DELETE FROM findings WHERE document_id=? AND source='rule'", (doc_id,))
    for severity, kind, detail in rule_findings(con, case_id, doc, x):
        ai = db.row(con, "SELECT id FROM findings WHERE document_id=? AND kind=? AND source IN ('ai','ai+rule')", doc_id, kind)
        if ai:
            con.execute("UPDATE findings SET source='ai+rule', severity=? WHERE id=?", (severity, ai["id"]))
        else:
            con.execute("""INSERT INTO findings (case_id, document_id, severity, kind, title, detail, source)
                           VALUES (?,?,?,?,?,?, 'rule')""", (case_id, doc_id, severity, kind, doc["title"], detail))
            added += 1
    return added


def audit_case(con, case_id: int) -> int:
    return sum(audit_document(con, case_id, d["id"]) for d in db.rows(con, "SELECT id FROM documents WHERE case_id=?", case_id))

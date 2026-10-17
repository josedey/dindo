"""Shareable PDF packages built from a case.

- Insurance claim: AI-drafted cover letter, invoice table, coverage, invoices that need fixing first, invoice photos.
- Evidence pack for the lawyer: AI-drafted neutral summary of documented facts, timeline, documented expenses,
  medical and legal documents in date order.

PDFs are drawn with Pillow (text pages + document photos), so no extra dependency is needed.
"""
import json
import textwrap
from datetime import date, timedelta
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFont, ImageOps

from . import ai, config, db

W, H, M = 1240, 1754, 90          # A4 at 150 dpi, margin
INK, MUTED, ACCENT, LINE = (22, 33, 29), (95, 110, 104), (14, 106, 88), (205, 214, 210)
CAT = {"not_medical": "No médicos", "hospitalization": "Internación", "medication": "Medicación", "nursing": "Enfermería", "transport": "Transporte",
       "lab_imaging": "Estudios", "doctor_fees": "Consultas", "therapy": "Fisioterapia", "legal": "Legal", "other": "Otros"}
BLOCKING = ("date", "arithmetic", "billing")
LEGAL_TYPES = ("medical_report", "study_order", "study_result", "prescription", "referral", "attendance_sheet",
               "patient_instructions", "legal", "imaging", "invoice", "receipt")

_FONT_PATHS = {
    False: ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf"],
    True: ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"],
}


def font(size: int, bold: bool = False):
    for p in _FONT_PATHS[bold]:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def bs(n) -> str:
    return f"{float(n or 0):,.2f} Bs".replace(",", "X").replace(".", ",").replace("X", ".")


def fdate(iso) -> str:
    return date.fromisoformat(iso).strftime("%d/%m/%Y") if iso else "—"


class Pages:
    """Very small page layout engine: headings, paragraphs, tables, key-value rows, automatic page breaks."""

    def __init__(self, title: str):
        self.title, self.pages, self.y = title, [], 0
        self.new_page()

    def new_page(self):
        self.im = Image.new("RGB", (W, H), "white")
        self.d = ImageDraw.Draw(self.im)
        self.pages.append(self.im)
        self.d.text((M, 50), "Dindo", font=font(26, True), fill=ACCENT)
        self.d.text((W - M, 54), self.title, font=font(18), fill=MUTED, anchor="ra")
        self.d.line((M, 92, W - M, 92), fill=LINE, width=2)
        self.d.text((W / 2, H - 50), f"{len(self.pages)}", font=font(16), fill=MUTED, anchor="ma")
        self.y = 120

    def need(self, h):
        if self.y + h > H - 90:
            self.new_page()

    def h1(self, s):
        self.need(80)
        self.d.text((M, self.y), s, font=font(40, True), fill=INK)
        self.y += 66

    def h2(self, s):
        self.need(60)
        self.y += 12
        self.d.text((M, self.y), s.upper(), font=font(20, True), fill=ACCENT)
        self.y += 38

    def p(self, s, size=22, color=INK, bold=False, width=88):
        f = font(size, bold)
        for para in (s or "").split("\n"):
            for line in textwrap.wrap(para, width=int(width * 22 / size)) or [""]:
                self.need(size + 12)
                self.d.text((M, self.y), line, font=f, fill=color)
                self.y += size + 11
        self.y += 6

    def kv(self, rows):
        for k, v in rows:
            self.need(34)
            self.d.text((M, self.y), k, font=font(20), fill=MUTED)
            self.d.text((M + 330, self.y), str(v), font=font(20, True), fill=INK)
            self.y += 34
        self.y += 8

    def table(self, cols, rows, widths, align=None):
        align = align or ["l"] * len(cols)
        x0 = [M + sum(widths[:i]) for i in range(len(widths))]

        def draw(cells, f, color):
            lines = [textwrap.wrap(str(c), width=max(4, int(w / 11))) or [""] for c, w in zip(cells, widths)]
            h = max(len(ln) for ln in lines) * 28 + 10
            self.need(h)
            for i, ln in enumerate(lines):
                for j, t in enumerate(ln):
                    if align[i] == "r":
                        self.d.text((x0[i] + widths[i] - 8, self.y + j * 28), t, font=f, fill=color, anchor="ra")
                    else:
                        self.d.text((x0[i], self.y + j * 28), t, font=f, fill=color)
            self.y += h
            self.d.line((M, self.y - 4, W - M, self.y - 4), fill=LINE, width=1)

        draw(cols, font(18, True), MUTED)
        for r in rows:
            draw(r, font(19), INK)
        self.y += 10

    def document(self, path: Path, caption: str):
        """A full page with a document photo (or the first page of a PDF) under a caption."""
        if path.suffix.lower() == ".pdf":
            src = pdfium.PdfDocument(str(path))[0].render(scale=1.5).to_pil()
        else:
            src = ImageOps.exif_transpose(Image.open(path))
        self.new_page()
        self.d.text((M, self.y), caption, font=font(22, True), fill=INK)
        self.y += 44
        src = src.convert("RGB")
        src.thumbnail((W - 2 * M, H - self.y - 110))
        self.im.paste(src, (int((W - src.width) / 2), self.y))

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.pages[0].save(path, "PDF", save_all=True, append_images=self.pages[1:], resolution=150)


def _file(doc) -> Path | None:
    if not doc or not doc.get("file_path"):
        return None
    p = (config.ROOT / doc["file_path"])
    return p if p.is_file() else None


def _draft(prompt: str, data: dict, case_id: int, fallback: str) -> tuple[str, bool]:
    """A short text written by the AMD text model; the fallback is used if the AI is offline or fails."""
    if not ai.connected():
        return fallback, False
    try:
        text = ai.chat([{"role": "system", "content": prompt},
                        {"role": "user", "content": json.dumps(data, ensure_ascii=False, default=str)}],
                       config.AMD_TEXT_MODEL, "package", case_id, max_tokens=1200)
        return text.replace("**", "").strip() or fallback, True
    except Exception:
        return fallback, False


# ---------------- Insurance claim ----------------

def insurance_preview(case_id: int) -> dict:
    with db.connect() as con:
        case = db.row(con, "SELECT * FROM cases WHERE id=?", case_id)
        policy = db.row(con, "SELECT * FROM insurance WHERE case_id=?", case_id)
        items = db.rows(con, """SELECT e.*, d.title AS document_title FROM expenses e LEFT JOIN documents d ON d.id=e.document_id
                                WHERE e.case_id=? AND e.reimbursable=1 AND e.claim_status='to_submit' ORDER BY e.date""", case_id)
        recovered = db.row(con, """SELECT COALESCE(SUM(COALESCE(reimbursed_amount, amount)),0) AS n FROM expenses
                                   WHERE case_id=? AND claim_status IN ('approved','paid')""", case_id)["n"]
        in_claim = db.row(con, "SELECT COALESCE(SUM(amount),0) AS n FROM expenses WHERE case_id=? AND claim_status='submitted'", case_id)["n"]
        include, fix = [], []
        for it in items:
            problems = db.rows(con, f"""SELECT detail FROM findings WHERE document_id=? AND status='open'
                                        AND severity!='info' AND kind IN ({','.join('?' * len(BLOCKING))})""", it["document_id"], *BLOCKING)
            due = db.claim_due(policy, it["date"])
            if due:
                it["due"] = due.isoformat()
                if due < config.today():
                    problems.append({"detail": f"El plazo para presentarla venció el {due:%d/%m/%Y}."})
            it["problems"] = [p["detail"] for p in problems]
            (fix if problems else include).append(it)
    total = sum(i["amount"] for i in include)
    limit = (policy or {}).get("coverage_limit") or 0
    return {"case": case, "policy": policy, "include": include, "fix": fix, "total": total,
            "recovered": recovered, "in_claim": in_claim,
            "remaining_after": limit - recovered - in_claim - total if limit else None}


def insurance_package(case_id: int) -> dict:
    pv = insurance_preview(case_id)
    case, policy = pv["case"], pv["policy"]
    if not policy:
        raise ValueError("This case has no insurance policy")
    fallback = (f"Señores {policy['insurer']}:\n\nPor medio de la presente solicito el reembolso de los gastos médicos de "
                f"{case['subject_name']}, detallados en la tabla adjunta, por un total de {bs(pv['total'])}. "
                f"Se adjuntan las facturas originales emitidas a nombre de {policy['insurer']} (NIT {policy['nit']}).\n\nAtentamente.")
    letter, by_ai = _draft(
        "Write in Spanish a short, formal reimbursement request letter (max 170 words) from the patient's family to the "
        "insurer, for the invoices listed. Mention the patient, the insurer and NIT, the number of invoices and the total in Bs. "
        "No medical or legal advice, no invented facts, no placeholders like [name]. Plain text, no markdown.",
        {"patient": case["subject_name"], "insurer": policy["insurer"], "nit": policy["nit"], "today": config.today().isoformat(),
         "invoices": [{k: i[k] for k in ("date", "vendor", "invoice_number", "description", "amount")} for i in pv["include"]],
         "total": pv["total"]}, case_id, fallback)

    pg = Pages(f"Reclamo de reembolso · {case['title']}")
    pg.h1("Solicitud de reembolso")
    pg.kv([("Paciente", case["subject_name"]), ("Aseguradora", f"{policy['insurer']} (NIT {policy['nit']})"),
           ("Fecha", fdate(config.today().isoformat())), ("Facturas incluidas", len(pv["include"])),
           ("Total a reembolsar", bs(pv["total"]))])
    pg.h2("Carta")
    pg.p(letter)
    if by_ai:
        pg.p(f"Borrador redactado por {config.AMD_TEXT_MODEL} en GPUs AMD; revisado por la familia antes de enviar.", 16, MUTED)
    pg.h2("Facturas incluidas")
    pg.table(["Fecha", "Proveedor", "N.º", "Detalle", "Monto"],
             [[fdate(i["date"]), i["vendor"] or "", i["invoice_number"] or "", i["description"] or "", bs(i["amount"])] for i in pv["include"]]
             + [["", "", "", "TOTAL", bs(pv["total"])]],
             [150, 250, 110, 370, 180], ["l", "l", "l", "l", "r"])
    if policy.get("coverage_limit"):
        pg.h2("Cobertura")
        pg.kv([("Límite de la póliza", bs(policy["coverage_limit"])), ("Ya recuperado", bs(pv["recovered"])),
               ("En trámite", bs(pv["in_claim"])), ("Este reclamo", bs(pv["total"])),
               ("Saldo si se aprueba", bs(pv["remaining_after"]))])
    if pv["fix"]:
        pg.h2("Para corregir antes de presentar (no incluidas)")
        for i in pv["fix"]:
            pg.p(f"{fdate(i['date'])} · {i['vendor']} N.º {i['invoice_number'] or '—'} · {bs(i['amount'])}", 20, bold=True)
            for prob in i["problems"]:
                pg.p("• " + prob, 19, MUTED)
    with db.connect() as con:
        for n, i in enumerate(pv["include"], 1):
            path = _file(db.row(con, "SELECT file_path FROM documents WHERE id=?", i["document_id"]))
            if path:
                pg.document(path, f"Factura {n}: {i['vendor']} N.º {i['invoice_number'] or '—'} · {fdate(i['date'])} · {bs(i['amount'])}")
    name = f"reclamo-seguro-caso{case_id}-{config.today().isoformat()}.pdf"
    pg.save(config.DATA_DIR / "paquetes" / name)
    return {"file": name, "pages": len(pg.pages), "invoices": len(pv["include"]), "total": pv["total"], "ai_letter": by_ai}


def mark_submitted(case_id: int) -> int:
    ids = [i["id"] for i in insurance_preview(case_id)["include"]]
    with db.connect() as con:
        con.executemany("UPDATE expenses SET claim_status='submitted' WHERE id=?", [(i,) for i in ids])
    return len(ids)


# ---------------- Summary for the next medical visit ----------------

def visit_package(case_id: int) -> dict:
    from .app import _adherence, _doses  # local import: app imports this module
    today = config.today()
    with db.connect() as con:
        case = db.row(con, "SELECT * FROM cases WHERE id=?", case_id)
        last = db.row(con, "SELECT MAX(date) d FROM events WHERE case_id=? AND kind='appointment' AND date<?", case_id, today.isoformat())["d"]
        since = last or (today - timedelta(days=30)).isoformat()
        meds = db.rows(con, """SELECT name, dose, instructions, every_hours, start_date, end_date FROM medications WHERE case_id=?
                               AND start_date<=? AND (end_date IS NULL OR end_date>=?)""", case_id, today.isoformat(), today.isoformat())
        meds = [m for m in meds if m["end_date"] or (today - date.fromisoformat(m["start_date"])).days <= 30]
        adh = _adherence(con, case_id, today, 14)
        missed = [f"{fdate(p['date'])}: {p['expected'] - p['taken']} de {p['expected']} sin marcar" for p in adh["per_day"] if p["expected"] and p["taken"] < p["expected"]]
        events = db.rows(con, "SELECT DISTINCT date, kind, title FROM events WHERE case_id=? AND date>? AND date<=? ORDER BY date", case_id, since, today.isoformat())
        seen = set()  # the same session is often written on two papers
        events = [e for e in events if e["kind"] != "session" or not ((e["date"], "session") in seen or seen.add((e["date"], "session")))]
        docs = db.rows(con, """SELECT doc_date, doc_type, title FROM documents WHERE case_id=? AND doc_date>? AND doc_date<=?
                               AND doc_type IN ('study_result','study_order','medical_report','prescription','imaging','referral') ORDER BY doc_date""",
                       case_id, since, today.isoformat())
        # studies ordered in the last month that have no result yet (older orders are history, not news for the doctor)
        recent = (today - timedelta(days=30)).isoformat()
        tasks = db.rows(con, """SELECT DISTINCT t.title FROM tasks t JOIN documents d ON d.id=t.document_id WHERE t.case_id=? AND t.status='pending'
                                AND d.doc_date BETWEEN ? AND ?""", case_id, recent, today.isoformat())
        nxt = db.row(con, "SELECT date, time, title FROM events WHERE case_id=? AND kind='appointment' AND date>=? ORDER BY date LIMIT 1", case_id, today.isoformat())
    data = {"patient": case["subject_name"], "case": case["summary"], "today": today.isoformat(), "since": since,
            "medication": meds, "adherence_14_days": {"pct": adh["pct"], "days_with_unmarked_doses": missed},
            "events_since": events, "new_documents": docs, "pending_studies": tasks}
    fallback = (f"Desde la última consulta ({fdate(since)}): {len(events)} eventos y {len(docs)} documentos nuevos. "
                f"Medicación actual: {', '.join(m['name'] for m in meds) or 'ninguna registrada'}. "
                f"Cumplimiento de las últimas dos semanas: {adh['pct'] if adh['pct'] is not None else '—'} %.")
    text, by_ai = _draft(ai.VISIT_SYSTEM, data, case_id, fallback)

    pg = Pages(f"Resumen para la consulta · {case['title']}")
    pg.h1("Resumen para la consulta")
    pg.kv([("Paciente", case["subject_name"]), ("Fecha", fdate(today.isoformat())), ("Desde", fdate(since)),
           ("Próxima cita", f"{fdate(nxt['date'])} · {nxt['title']}" if nxt else "—"),
           ("Cumplimiento (14 días)", f"{adh['pct']} %" if adh["pct"] is not None else "—")])
    pg.h2("Resumen")
    pg.p(text)
    if by_ai:
        pg.p(f"Redactado por {config.AMD_TEXT_MODEL} en GPUs AMD a partir de los documentos del caso. No reemplaza la evaluación médica.", 16, MUTED)
    if meds:
        pg.h2("Medicación actual")
        pg.table(["Medicamento", "Dosis", "Frecuencia", "Desde", "Hasta"],
                 [[m["name"], m["dose"] or "", f"cada {m['every_hours']} h" if m["every_hours"] else "según indicación",
                   fdate(m["start_date"]), fdate(m["end_date"]) if m["end_date"] else "—"] for m in meds], [330, 160, 200, 170, 170])
    if docs:
        pg.h2("Estudios y documentos nuevos")
        pg.table(["Fecha", "Documento"], [[fdate(d["doc_date"]), d["title"]] for d in docs], [180, 880])
    if tasks:
        pg.h2("Estudios pedidos sin resultado todavía")
        for x in tasks:
            pg.p("• " + x["title"], 19)
    name = f"resumen-consulta-caso{case_id}-{today.isoformat()}.pdf"
    pg.save(config.DATA_DIR / "paquetes" / name)
    return {"file": name, "pages": len(pg.pages), "ai_summary": by_ai}


# ---------------- Evidence pack for the lawyer ----------------

def legal_preview(case_id: int) -> dict:
    with db.connect() as con:
        docs = db.rows(con, f"""SELECT id, doc_type, title, doc_date, issuer, file_path FROM documents WHERE case_id=?
                                AND doc_type IN ({','.join('?' * len(LEGAL_TYPES))}) ORDER BY doc_date IS NULL, doc_date, id""",
                       case_id, *LEGAL_TYPES)
        by_cat = db.rows(con, "SELECT category, SUM(amount) AS amount, COUNT(*) AS n FROM expenses WHERE case_id=? GROUP BY category ORDER BY amount DESC", case_id)
        events = db.rows(con, "SELECT date, time, kind, title FROM events WHERE case_id=? ORDER BY date, time", case_id)
        legal_contacts = db.rows(con, """SELECT name, role, phones FROM contacts WHERE case_id=? AND (lower(role) LIKE '%abog%'
                                         OR lower(role) LIKE '%fiscal%' OR lower(role) LIKE '%juez%' OR lower(role) LIKE '%concilia%')""", case_id)
    hearings = [e for e in events if e["kind"] == "hearing"]
    return {"documents": docs, "by_category": by_cat, "total": sum(c["amount"] for c in by_cat), "events": events,
            "hearings": hearings, "legal_contacts": legal_contacts,
            "counts": {"medical": sum(d["doc_type"] not in ("invoice", "receipt", "legal") for d in docs),
                       "legal": sum(d["doc_type"] == "legal" for d in docs),
                       "payments": sum(d["doc_type"] in ("invoice", "receipt") for d in docs)}}


def legal_package(case_id: int) -> dict:
    pv = legal_preview(case_id)
    with db.connect() as con:
        case = db.row(con, "SELECT * FROM cases WHERE id=?", case_id)
    key_events = [e for e in pv["events"] if e["kind"] in ("accident", "admission", "surgery", "hearing", "study")][:60]
    fallback = (f"Resumen de los documentos del caso de {case['subject_name']}: {pv['counts']['medical']} documentos médicos, "
                f"{pv['counts']['legal']} documentos legales y {pv['counts']['payments']} comprobantes de pago por un total de {bs(pv['total'])}.")
    summary, by_ai = _draft(
        "Write in Spanish a neutral 'resumen de hechos documentados' (max 250 words) for the family's lawyer: what happened "
        "and when, the medical course, and the documented expenses, strictly from the data given, with dates. "
        "No legal advice, no conclusions about guilt or compensation, no invented facts. Plain text, no markdown.",
        {"subject": case["subject_name"], "case": case["summary"], "events": key_events,
         "documents": [{k: d[k] for k in ("doc_date", "doc_type", "title")} for d in pv["documents"]][:120],
         "expenses_by_category": pv["by_category"], "total_documented": pv["total"]}, case_id, fallback)

    pg = Pages(f"Pruebas documentadas · {case['title']}")
    pg.h1("Pruebas documentadas del caso")
    pg.kv([("Persona afectada", case["subject_name"]), ("Fecha del informe", fdate(config.today().isoformat())),
           ("Documentos médicos", pv["counts"]["medical"]), ("Documentos legales", pv["counts"]["legal"]),
           ("Comprobantes de pago", pv["counts"]["payments"]), ("Gastos documentados", bs(pv["total"]))])
    pg.h2("Resumen de hechos documentados")
    pg.p(summary)
    pg.p("Este documento organiza la información del caso. No constituye asesoramiento legal ni médico." +
         (f" Resumen redactado por {config.AMD_TEXT_MODEL} en GPUs AMD." if by_ai else ""), 16, MUTED)
    if pv["hearings"]:
        pg.h2("Audiencias")
        pg.table(["Fecha", "Detalle"], [[fdate(h["date"]), h["title"]] for h in pv["hearings"]], [180, 880])
    pg.h2("Gastos documentados por categoría")
    pg.table(["Categoría", "Comprobantes", "Monto"],
             [[CAT.get(c["category"], c["category"]), c["n"], bs(c["amount"])] for c in pv["by_category"]] + [["TOTAL", "", bs(pv["total"])]],
             [600, 220, 240], ["l", "r", "r"])
    pg.h2("Línea de tiempo")
    pg.table(["Fecha", "Evento"], [[fdate(e["date"]) + (f" {e['time']}" if e["time"] else ""), e["title"]] for e in key_events], [220, 840])
    pg.h2("Índice de documentos")
    pg.table(["#", "Fecha", "Documento"], [[n, fdate(d["doc_date"]), d["title"]] for n, d in enumerate(pv["documents"], 1)], [70, 170, 820])
    for n, d in enumerate(pv["documents"], 1):
        path = _file(d)
        if path:
            pg.document(path, f"Documento {n}: {d['title']} · {fdate(d['doc_date'])}")
    name = f"pruebas-caso{case_id}-{config.today().isoformat()}.pdf"
    pg.save(config.DATA_DIR / "paquetes" / name)
    return {"file": name, "pages": len(pg.pages), "documents": len(pv["documents"]), "total": pv["total"], "ai_summary": by_ai}

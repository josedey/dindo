"""AMD Token Factory client: every model call in Dindo goes through here.

Token Factory serves open models on AMD GPUs behind an OpenAI-compatible API
(base URL https://developer.amd.com.cn/radeon/api/v1). Each call is logged in the ai_calls
table, which feeds the "Under the hood" panel.
"""
import base64
import io
import json
import random
import re
import time
from pathlib import Path

import pypdfium2 as pdfium
from openai import APIStatusError, OpenAI
from PIL import Image, ImageOps

from . import config, db
from .orientacion import best_rotation

SCHEMA_DOC = (config.ROOT / "docs" / "ground_truth_schema.md").read_text(encoding="utf-8")

EXTRACT_SYSTEM = f"""You read photos of medical, insurance, legal and payment documents for Dindo, an app that helps a
patient's family organise a health case. Return ONE JSON object describing the document, using exactly this format
(Spanish text as written on the document; null when unknown; never guess):

{SCHEMA_DOC}

Rules:
- Transcribe names, amounts, dates and phone numbers exactly. Dates as YYYY-MM-DD.
- "anomalies": report what a careful person should double-check, in Spanish, one sentence each:
  an invoice dated before the service it charges; line items that do not add up to the total; an invoice not billed
  to the patient's insurer (name and NIT given below); a body side that contradicts the case; a receipt that is not a
  fiscal invoice; missing key fields.
- Never diagnose, interpret medical images or give medical or legal advice. Only describe what the document says.
- "legibility" must honestly reflect how sure you are about handwritten parts.
- If a word is crossed out and corrected, use the correction (and you may note the correction in "notes").
- Report a body-side contradiction only when the side is clearly written. If the side is hard to read, do not
  report a contradiction: ask about it in "questions" instead.
- NEVER replace an illegible medication or drug name with a guess. Write only the letters you can read followed by
  "(ilegible)" and ask about it in "questions". The same for doses, frequencies and amounts you are not sure about.
- A product offer or price quote (a budget, a Facebook/marketplace post, a price screenshot) is doc_type "quote":
  product and price in line_items, seller in issuer, seller phone in contacts. It is not an expense.
- Add a key "case_related": false when the document has nothing to do with the patient's health case (a restaurant or
  food bill, groceries, personal shopping unrelated to care), with the reason in Spanish in "unrelated_reason"; true otherwise.
- Photos of the injury and X-ray/imaging photos: describe them neutrally in "notes" (what is visible), never
  interpret them medically.
- Every event needs a short "title" (max 5 words, like a calendar entry: "Control – Dr. Añez", "TAC de rodilla",
  "Fisioterapia – Rehalife", "Audiencia de conciliación"); put the long explanation in "description".
- Fill "instructions" with every indication for the patient written on the document: diet (allowed or to avoid),
  activity limits, care (immobilizer, compression stockings, rest) and how to take medication. One item each, in
  Spanish, with "until" computed from the document date when a duration is given.
- If the paper clearly names a different patient than this case's patient, report it as an anomaly ("El papel es de otro paciente: ...").
- Black rectangles are intentional redactions of personal data. Ignore them and never report them as anomalies.
- Add a key "questions": a list of {{"question": "...", "options": ["...", "..."]}} in Spanish for every value a person
  should confirm before relying on it (illegible drug names, doses, sides, amounts). Empty list if everything is clear."""

ASK_SYSTEM = """You are Dindo, an assistant that helps a family find things in the records of a health case: documents,
expenses, medication, appointments, instructions, alerts and insurance. Answer ONLY from the case data provided. Be brief
and concrete: dates (dd/mm/yyyy), amounts in Bs, names. After each fact, cite the document it comes from as [doc:ID]
using the document ids given. If the data does not contain the answer, say so plainly. Never give medical or legal advice
and never interpret results; for anything clinical, suggest asking the doctor. Answer in {lang}."""

VISIT_SYSTEM = """Write in Spanish a one-page summary for the patient's next medical visit, from the case data given
(max 220 words, plain text, no markdown). Sections, each a short paragraph introduced by its name and a colon:
"Desde la última consulta", "Medicación actual", "Cumplimiento", "Estudios y documentos nuevos", "Estudios pendientes" (only the pending_studies given; omit the section if there are none).
Facts only, with dates; no diagnosis, no advice, no invented data."""

LANG_NAME = {"es": "Spanish", "en": "English", "it": "Italian"}

_client: OpenAI | None = None


def connected() -> bool:
    return bool(config.AMD_API_KEY and config.AMD_API_BASE_URL)


def client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(base_url=config.AMD_API_BASE_URL, api_key=config.AMD_API_KEY, timeout=600, max_retries=0)
    return _client


def chat(messages: list, model: str, purpose: str, case_id=None, document_id=None, json_mode=False, max_tokens=4000) -> str:
    """One chat completion on AMD Token Factory, with backoff on 429/5xx and a log row per attempt."""
    kwargs = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if model.startswith(("MiMo", "Qwen3.8-Flash")):
        kwargs["reasoning_effort"] = "none"  # these think by default; extraction and Q&A don't need it
    for attempt in range(6):
        start = time.monotonic()
        try:
            resp = client().chat.completions.create(**kwargs)
            usage = resp.usage
            _log(case_id, document_id, model, purpose, int((time.monotonic() - start) * 1000),
                 usage.prompt_tokens if usage else None, usage.completion_tokens if usage else None, True)
            return resp.choices[0].message.content or ""
        except APIStatusError as e:
            _log(case_id, document_id, model, purpose, int((time.monotonic() - start) * 1000), None, None, False)
            # The gateway wraps an unavailable model as a 500 whose message says 503.
            unavailable = e.status_code in (502, 503) or (e.status_code == 500 and re.search(r"503|unavailable", str(e), re.I))
            if not (e.status_code == 429 or unavailable) or attempt == 3:
                raise
            retry_after = float(e.response.headers.get("retry-after") or 0)
            time.sleep(max(retry_after, 2 ** attempt) + random.uniform(0, 1))
    raise RuntimeError("unreachable")


def chat_with_fallback(messages: list, models: list[str], purpose: str, **kw) -> tuple[str, str]:
    """Try each model in order (shared endpoints can go down); returns (text, model used)."""
    last = None
    for m in [m for m in models if m]:
        try:
            return chat(messages, m, purpose, **kw), m
        except APIStatusError as e:
            last = e
    raise last or RuntimeError("No model configured")


def _log(case_id, document_id, model, purpose, latency, tin, tout, ok):
    with db.connect() as con:
        con.execute("""INSERT INTO ai_calls (case_id, document_id, model, purpose, endpoint, latency_ms, input_tokens,
                       output_tokens, ok) VALUES (?,?,?,?,?,?,?,?,?)""",
                    (case_id, document_id, model, purpose, config.AMD_API_BASE_URL, latency, tin, tout, 1 if ok else 0))


def image_parts(path: Path) -> list[dict]:
    """A photo or PDF as image_url parts (max 1600 px, JPEG), ready for a vision model."""
    if path.suffix.lower() == ".pdf":
        pdf = pdfium.PdfDocument(str(path))
        images = [pdf[i].render(scale=1.6).to_pil() for i in range(min(len(pdf), 3))]
    else:
        images = [ImageOps.exif_transpose(Image.open(path))]
    parts = []
    for im in images:
        im = im.convert("RGB")
        im = im.rotate(best_rotation(im), expand=True)  # sideways phone photos -> upright
        im.thumbnail((1600, 1600))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85)
        parts.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()}})
    return parts


def parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        return json.loads(text[start:end + 1])


def extract_document(path: Path, case: dict, insurer: dict | None, model: str | None = None,
                     case_id=None, document_id=None) -> dict:
    """Read one document photo with the AMD vision model and return it in the ground-truth schema."""
    context = (f"Case: {case['title']} ({case.get('summary') or ''}). Patient/subject: {case['subject_name']} "
               f"({'pet' if case.get('subject_kind') == 'pet' else 'person'}). "
               f"Insurer: {insurer['insurer']} NIT {insurer['nit']}." if insurer else "No insurer.")
    messages = [{"role": "system", "content": EXTRACT_SYSTEM},
                {"role": "user", "content": [{"type": "text", "text": context + f'\nFile name: "{path.name}". Return the JSON object.'},
                                             *image_parts(path)]}]
    models = [model] if model else [config.AMD_VISION_MODEL, config.AMD_VISION_FALLBACK]
    text, used = chat_with_fallback(messages, models, "extract", case_id=case_id, document_id=document_id, json_mode=True)
    out = parse_json(text)
    out["file"] = path.name
    out["_model"] = used
    return out


def ask(case_id: int, question: str, lang: str = "es") -> str:
    """Answer a question about a case from its records, with the AMD text model."""
    with db.connect() as con:
        case = db.row(con, "SELECT title, subject_name, summary FROM cases WHERE id=?", case_id)
        data = {
            "case": case,
            "expenses": db.rows(con, """SELECT e.date, e.amount, e.category, e.vendor, e.description, e.reimbursable, e.claim_status, e.document_id,
                                        m.name AS paid_by, d.title AS document FROM expenses e LEFT JOIN members m ON m.id=e.paid_by
                                        LEFT JOIN documents d ON d.id=e.document_id WHERE e.case_id=? ORDER BY e.date""", case_id),
            "medications": db.rows(con, "SELECT name, dose, instructions, every_hours, start_date, end_date, document_id FROM medications WHERE case_id=?", case_id),
            "events": db.rows(con, "SELECT date, time, kind, title, place, document_id FROM events WHERE case_id=? ORDER BY date", case_id),
            "pending": db.rows(con, "SELECT title, status FROM tasks WHERE case_id=?", case_id),
            "alerts": db.rows(con, """SELECT f.severity, f.detail, f.document_id, d.title AS document FROM findings f LEFT JOIN documents d ON d.id=f.document_id
                                      WHERE f.case_id=? AND f.status='open' AND f.severity!='info'""", case_id),
            "insurance": db.row(con, "SELECT insurer, coverage_limit, claim_days FROM insurance WHERE case_id=?", case_id),
            "instructions": db.rows(con, "SELECT kind, polarity, text, start_date, until, document_id FROM instructions WHERE case_id=?", case_id),
            "contacts": db.rows(con, "SELECT name, role, organization, phones FROM contacts WHERE case_id=?", case_id),
            "documents": [{"id": d["id"], "date": d["doc_date"], "type": d["doc_type"], "title": d["title"], "issuer": d["issuer"],
                           "summary": (d["summary"] or "")[:220], "diagnosis": json.loads(d["extracted_json"] or "{}").get("diagnosis_text")}
                          for d in db.rows(con, "SELECT id, doc_date, doc_type, title, issuer, summary, extracted_json FROM documents WHERE case_id=? ORDER BY doc_date", case_id)],
            "today": config.today().isoformat(),
        }
    messages = [{"role": "system", "content": ASK_SYSTEM.format(lang=LANG_NAME.get(lang, "Spanish"))},
                {"role": "user", "content": f"Case data (JSON):\n{json.dumps(data, ensure_ascii=False, default=str)}\n\nQuestion: {question}"}]
    return chat(messages, config.AMD_TEXT_MODEL, "ask", case_id, max_tokens=1500)

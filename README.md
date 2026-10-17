# Dindo

**An AI health case manager for patients and their families, running on open models served on AMD GPUs.**

Built for the AMD Developer Hackathon: ACT III (lablab.ai), Track 2, Health and Wellbeing.

## The problem

In July 2022 a car hit me while I was crossing the street. Fractured left tibial plateau, two surgeries, months of physiotherapy, a post-thrombotic syndrome and a lawsuit. What followed was also a paperwork ordeal:

- Handwritten prescriptions from five doctors, and never knowing which pill was due when.
- Days with 4,000 Bs of expenses and no idea what they were for.
- Invoices for the insurer that missed the deadline or were issued wrong, so part of the money was never recovered.
- Phone numbers that were nowhere when they were needed.

Clinics have systems. **The family has a bag of papers.** Dindo turns that bag into an organised, audited case.

## What it does

Take a photo of any paper (prescription, invoice, medical order, report, court summons). An open vision model on AMD GPUs reads it, and Dindo:

| | |
|---|---|
| **Today** | A 24-hour medication grid with one-click "taken" boxes, overdue doses, the agenda, what is still to be bought and the doctor's current instructions |
| **Calendar** | Every visit, test, physio session and hearing, with each treatment drawn as a bar across its days |
| **Treatment** | A weekly grid per medication and course progress ("day 12 of 180, ends 18 Jul 2023") |
| **Instructions** | Diet, activity and care indications (DO / AVOID, valid until), extracted from the doctors' notes |
| **Expenses** | Each expense with its invoice lines, who paid it, its category and whether insurance refunds it, plus natural-language questions ("Why did we spend 4,000 Bs today?") |
| **Insurance** | Coverage used and left, invoices to fix before submitting, and a claim PDF with an AI-drafted letter |
| **Lawsuit** | Hearings, legal contacts and an evidence-pack PDF for the lawyer |
| **Contacts** | Doctors, clinics, pharmacies and legal contacts, filled from stamps and notes, with an emergency sheet |

### It audits the case

Dindo cross-checks every document, using both the AI and deterministic rules. When both agree, the finding is marked **AI + rule**. Real errors it found in my own papers:

- A CT order for the **RIGHT** knee when the injury is the **LEFT** knee.
- A physiotherapy invoice **dated before** the sessions it charges, which insurers reject.
- Invoices **not issued to the insurer**, discounts that don't add up, and receipts that aren't fiscal invoices.

### It never guesses

When a handwritten drug name or a body side is not clearly legible, the model writes "(ilegible)" and **asks the family** ("Couldn't read this drug name — which is it?"). It never diagnoses, never interprets medical images and never gives legal advice. Every record links back to the photo it came from.

## How it uses AMD

All AI runs on **AMD Instinct GPUs through AMD Token Factory** (OpenAI-compatible API, `https://developer.amd.com.cn/radeon/api/v1`):

| Task | Model |
|---|---|
| Reading documents (vision) | `Gemma-4-31B-IT`, falling back to `Qwen3.8-Flash-Next` if the shared endpoint is unavailable |
| Questions, claim letter, evidence summary | `DeepSeek-V4-Flash` |

Every call is logged and visible in the **Under the hood** screen (model, latency, tokens). All calls live in [`dindo/servidor/ai.py`](dindo/servidor/ai.py). Retries honour `Retry-After` on 429/5xx.

**Measured accuracy.** On a set of synthetic documents with known contents, [`tools/evaluar.py`](tools/evaluar.py) scores Gemma-4-31B-IT at **98% of fields correct (55/56)** and **5/5 planted errors detected**, at about 15 s per document.

**Why open models on AMD.** Health data should not have to leave the family's or the clinic's infrastructure. The same app can run against a dedicated AMD endpoint or on-prem AMD Instinct hardware without code changes.

## Privacy and the demo data

Token Factory's terms ask not to send identifiable health data, so the public demo uses **my real documents with personal data covered**: [`demo/caso-demo/`](demo/caso-demo/). They were anonymized locally with OCR and manual review by [`tools/anonimizar.py`](tools/anonimizar.py). Clinics, doctors, amounts, dates and the real errors stay visible. [`demo/caso-sintetico/`](demo/caso-sintetico/) holds fictional documents used for the accuracy benchmark ([`tools/generar_documentos.py`](tools/generar_documentos.py)).

## Run it

Requirements: Python 3.10+ and an AMD Token Factory key.

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env              # add AMD_API_BASE_URL, AMD_API_KEY and model names
python -m dindo.servidor.seed     # creates the demo cases (add --gt to fill them without calling the AI)
python -m uvicorn dindo.servidor.app:app --port 8000
python tools/cargar_demo.py       # optional: the AMD models read the demo documents
```

Open http://localhost:8000. Set `DINDO_TODAY=2023-01-20` in `.env` to replay the case as of that day.

With Docker:

```bash
docker build -t dindo .
docker run -p 8000:8000 --env-file .env dindo
```

## Project layout

```
dindo/servidor/   FastAPI app: API, AMD client (ai.py), audit rules (audit.py), ingestion, PDF packages
dindo/web/        The web app (plain HTML/CSS/JS, mobile-first, ES/EN/IT, day/night themes)
demo/             Anonymized real documents, synthetic benchmark documents
tools/            Anonymizer, synthetic document generator, accuracy benchmark, demo loader
docs/             Plan, progress log, extraction schema
```

## License

MIT, see [LICENSE](LICENSE).

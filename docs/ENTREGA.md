# Entrega en lablab: todo listo para copiar y pegar

## Datos del proyecto

- **Título:** Dindo — AI health-case manager on AMD GPUs
- **Track:** Track 2 — Health and Wellbeing
- **Demo:** https://dindo-vgpq.onrender.com
- **Repositorio:** https://github.com/josedey/dindo
- **Portada:** `docs/cover/cover.png` (1920×1080)
- **Slides:** descargar como PDF o PowerPoint desde el enlace de las slides (Compartir › Exportar)
- **Video:** subirlo a YouTube como "No listado" y pegar el enlace

## Descripción corta (una línea)

Photograph any medical paper: open models on AMD GPUs read it, organize the whole health case (doses, appointments, expenses, insurance, lawsuit) and audit it for costly errors.

## Descripción larga

In July 2022 a car hit me while I was crossing the street. Fractured tibial plateau, surgeries, months of physiotherapy, a post-thrombotic syndrome and a lawsuit. The hardest part for my family was the paperwork: handwritten prescriptions from five doctors, almost 28,000 Bs in receipts, invoices the insurer refused because they were issued wrong or arrived after the month closed, and even studies ordered for the wrong knee. Clinics have systems. The family has a bag of papers.

Dindo turns that bag into an organized, audited case. You take a photo of any paper (prescription, invoice, medical order, report, court summons, even a screenshot of a wheelchair offer). Gemma-4-31B-IT, an open vision model running on AMD GPUs through AMD Token Factory, reads it, including handwriting and photos taken sideways. Dindo files every piece where it belongs:

- Today: a 24-hour dose grid with one-tap "taken", overdue doses, reminders and the day read aloud.
- Calendar, treatment adherence, doctors' instructions (DO / AVOID), diagnoses as written and test orders with their status.
- Expenses with invoice lines and who paid; insurance with the insurer's own deadline rule, claim status and an AI-drafted claim PDF; quotes compared before buying; restaurant bills recognized and filed apart.
- Ask your case: questions in plain language, answered by DeepSeek-V4-Flash on AMD, with every fact linked to its document. Plus a 2-page summary for the next doctor visit and an evidence pack for the lawyer.

Dindo also audits the case with AI plus deterministic rules. In my own papers it found an X-ray and an echo-Doppler ordered for the right knee when the fracture is the left one, a physiotherapy invoice dated before the sessions it charges, and three invoices (4,660 Bs) past the insurer's deadline.

It never guesses: when a drug name or a body side is illegible, it asks the family. It never diagnoses or interprets images. The public demo is my real case, with personal data covered locally before any AI call. All 166 documents were read by Gemma on AMD (about 15 s each). On a benchmark with known answers it gets 98% of fields right and catches 5 of 5 planted errors. Every AMD call is visible in the app's "Under the hood" screen. Because the models are open, the same app can run on a clinic's own AMD Instinct hardware, so health data never has to leave it.

Built with FastAPI, plain HTML/CSS/JS (installable on Android), Spanish, English and Italian.

## Etiquetas (tecnologías)

AMD, AMD Token Factory, AMD Instinct, Gemma, DeepSeek, Vision Language Model, LLM, Healthcare, OCR, Python, FastAPI, PWA

## Guion del video (2:30 a 3:00)

Grabar en la compu con **Win + Alt + R** (Xbox Game Bar) u OBS, con la app en https://dindo-vgpq.onrender.com y en Verde clínico. Si preferís hablar en español, está bien: agregá subtítulos en inglés en YouTube (Subtítulos › Agregar). Antes de grabar, abrí la app una vez para despertarla.

| Tiempo | Qué se ve | Qué decís |
|---|---|---|
| 0:00–0:20 | Slide 1 (portada) y slide 2 (el problema) | "Hi, I'm José. In 2022 a car hit me. Surgeries, physiotherapy, a lawsuit, and a bag full of papers: five doctors writing by hand, almost 28,000 bolivianos in receipts, invoices the insurer refused. Dindo is the app I wish my family had." |
| 0:20–0:45 | Pantalla **Subir**: subir una foto de una receta o factura; se ve "leyendo" y el resultado | "You take a photo of any paper. Gemma, an open vision model on AMD GPUs through Token Factory, reads it, even handwriting, and Dindo files everything: medication, appointments, expenses." |
| 0:45–1:10 | **Hoy** en la compu y luego en el celular: dosis atrasada en rojo, marcar tomada | "Every day it tells the family which pill is due and what is late. One tap to mark it, reminders, and it can read the day aloud." |
| 1:10–1:35 | **Alertas**: los 3 "lado incorrecto" y la factura fechada antes | "It audits the case. In my own papers it found an X-ray ordered for the right knee when my fracture is the left one, and an invoice dated before the sessions it charges." |
| 1:35–2:00 | **Gastos** y **Seguro**: total, categorías, "Marcar enviada", PDF de reclamo | "All the money in one place. It knows my insurer only accepts invoices until the end of the month and warns me, and it drafts the claim letter." |
| 2:00–2:20 | **Preguntar**: "¿Cuánto gastamos en fisioterapia?" y la respuesta con documentos | "And I can just ask my case. Every answer links to the document it comes from." |
| 2:20–2:40 | **Bajo el capó**: las llamadas a Gemma y DeepSeek | "Everything runs on AMD: 166 real documents read by Gemma, 98% of fields correct on our benchmark. It never guesses: when something is illegible, it asks." |
| 2:40–2:55 | Slide final | "Clinics have systems. Families deserve one too. Dindo, your health, with you every step. Try it at the link below." |

## Antes de enviar

- [ ] Abrir la demo para que Render esté despierta cuando la vean los jueces.
- [ ] Compartir las slides (Compartir › cualquiera con el enlace) o subir el PDF exportado.
- [ ] Video en YouTube como "No listado", con subtítulos si está en español.
- [ ] En lablab: título, descripciones, track, etiquetas, portada, video, slides, repo y demo.
- [ ] Opcional: renombrar el equipo "0605" a "Dindo".

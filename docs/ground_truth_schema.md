# Ground truth: formato de transcripción

Cada imagen del caso se transcribe en un objeto JSON con estas claves. Se usa `null` cuando un dato no se sabe, sin adivinar. El texto se transcribe fielmente, en español, tal como está escrito.

```json
{
  "file": "ruta relativa desde accidente-jose/ con barras /",
  "doc_type": "invoice | receipt | quote | prescription | medical_report | study_order | study_result | referral | attendance_sheet | patient_instructions | insurance | legal | imaging | photo | screenshot | other",
  "title": "título corto en español, p. ej. 'Factura Rehalife N.º 001408'",
  "date": "YYYY-MM-DD tal como está escrita (si es obviamente errónea, igual se pone y se explica en anomalies)",
  "issuer": "clínica, empresa o médico que lo emite",
  "doctor": {"name": "", "specialty": "", "license": ""},
  "patient_name_as_written": "",
  "billed_to": "Nombre o razón social de la factura",
  "billed_to_nit": "",
  "invoice_number": "",
  "line_items": [{"description": "", "amount": 0}],
  "total": 0,
  "currency": "BOB",
  "expense_category": "hospitalization | medication | nursing | transport | lab_imaging | doctor_fees | therapy | legal | other",
  "medications": [{"name": "", "dose": "", "frequency": "", "duration": "", "instructions": ""}],
  "studies_requested": [{"name": "", "body_side": "left | right | null", "reason": ""}],
  "diagnosis_text": "tal como está escrito, con código CIE si lo hay",
  "events": [{"kind": "accident | admission | surgery | appointment | session | study | hearing | other", "date": "YYYY-MM-DD", "time": "HH:MM o null", "title": "tema corto, máx. 5 palabras: 'Control – Dr. Añez', 'TAC de rodilla', 'Fisioterapia – Rehalife'", "description": ""}],
  "contacts": [{"name": "", "role_or_specialty": "", "phones": [], "email": "", "organization": "", "address": ""}],
  "instructions": [{"kind": "diet | activity | care | medication | other", "polarity": "do | avoid", "text": "", "until": "YYYY-MM-DD o null"}],
  "handwritten": false,
  "legibility": "good | fair | poor",
  "anomalies": [],
  "notes": ""
}
```

Reglas:
- `instructions` recoge las indicaciones para el paciente: dieta (qué comer o evitar), actividad ("sin apoyo por 8 semanas"), cuidados ("usar inmovilizador 30 días") y otras. Va una por elemento, con `until` calculado a partir de la fecha del documento cuando dice una duración.
- `quote` es una cotización o una oferta de producto (presupuesto, publicación de venta en redes, captura de precios): va el producto y su precio en `line_items`, el vendedor en `issuer` y su teléfono en `contacts`. No es un gasto.
- `photo` e `imaging` (fotos de la lesión, radiografías): se describen de forma neutral en `notes`, sin interpretar ni diagnosticar.
- Los descuentos van como montos negativos en `line_items`.
- `doctor` es `null` si el documento no tiene médico.
- En `anomalies` va todo lo incoherente: fechas erróneas, lado del cuerpo distinto al del resto del caso, errores de suma, facturas que no están a nombre de la aseguradora del caso, campos faltantes y duplicados de otro archivo.
- Para `photo` y `screenshot`: describir el contenido de forma neutral y breve en `notes`, y dejar el resto en `null` o vacío salvo fechas y contactos visibles.

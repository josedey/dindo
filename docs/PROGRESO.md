# Progreso (para retomar)

## Hecho
- Estructura del proyecto, `docs/PLAN.md`, licencia, README y `.env` (con `DINDO_TODAY=2023-01-20`).
- 323 documentos reales en `demo/accidente-jose/`: los 57 originales y 266 de `NUEVA CARPETA`, achicados a 1600 px.
- Transcripción de referencia de los 323 documentos: `ground_truth.json` y `ground_truth_lote_1..4.json` (formato en `docs/ground_truth_schema.md`).
- Servidor FastAPI (`dindo/servidor/app.py`) con API de hoy, gastos, documentos con trazabilidad, medicación y dosis, línea de tiempo, contactos, pendientes, hallazgos, seguro y registro de llamadas a la IA.
- Cargador del caso (`dindo/servidor/seed.py`): descarta duplicados de facturas y medicamentos y clasifica los hallazgos (critical / warning / info).
- Pantallas web (`dindo/web/`): Hoy, Gastos, Subir, Tratamiento y Caso (hallazgos, documentos, línea de tiempo, contactos, pendientes, seguro), con ficha de documento, botón Compartir y 3 idiomas.

## Cómo correr
```
.venv\Scripts\python -m dindo.servidor.seed      # recarga el caso desde ground_truth*.json
.venv\Scripts\python -m uvicorn dindo.servidor.app:app --port 8000 --reload --reload-dir dindo
```
Abrir http://localhost:8000

## Lo que reveló la transcripción (para el pitch y la demo)
- **Accidente:** 04/07/2022, 19:00, atropello con fuga en la Av. La Barranca. Emergencia en Clínica Manantial de Vida; cirugía con placa e injerto (Dr. Aguilera, Dr. López Baigorria).
- **Evolución:**
  - 17/10/2022: emergencia en la CPS.
  - 20/01/2023: síndrome postrombótico severo, anticoagulante 5 mg c/12 h durante 6 meses.
  - 07–14/02/2023: no consolidación (TAC).
  - 20/04/2023: cirugía de retiro de material en Clínica España.
- **Juicio:** declaración policial, fiscal, conciliadora, acuerdo de 63.000 Bs (17/11/2023) y audiencia suspendida (24/05/2024).
- **Mascota:** recetas del veterinario del 24/05/2024 (Ferrocan, Echinacea, Kualcohepat, Doxiciclina). Sirve para el segundo caso.
- **Hallazgos reales:**
  - Varias órdenes de Foianini dicen rodilla DERECHA; una orden tiene "derecha" tachada y corregida.
  - Factura de Rehalife 001648 con el año equivocado.
  - Facturas que no están a nombre de Alianza; recibos "PARTICULAR"; documentos que dicen "Sin seguro".
  - Descuentos mal calculados (30% con monto 0; 70 Bs con "0%").
  - Fechas de nacimiento y edades inconsistentes; apellido mal escrito ("Manacho", "Menocho").
  - Asistencia de fisioterapia que no coincide con el informe.
- **Ruido:** selfies, un gato, formularios de impuestos, QR de licencia y chats ajenos. Hay que excluirlos o marcarlos.

## Pendientes con José
- [ ] Datos de la mascota de las recetas veterinarias del 24/05/2024 (nombre, especie) para el segundo caso. José lo revisa más adelante.
- [x] Sacar del caso los documentos ajenos: hecho con `demo/accidente-jose/excluir.txt` (26 archivos, incluidas las 4 recetas veterinarias, que pasan al caso de la mascota).

## IA de AMD conectada (jueves 15–16)
- Clave de Token Factory en `.env` (team-1236). Límites: 20 solicitudes por minuto y 1 USD por día, que se reinicia a las 12:00 hora de Bolivia.
- Los términos de Token Factory prohíben enviar datos de salud reales, así que **la demo usa documentos inventados**: `demo/caso-sintetico/`, generados con `tools/generar_documentos.py`, que replican los formatos y errores reales. El caso real de José queda local y nunca se envía a la IA.
- Modelos:
  - **Gemma-4-31B-IT** lee documentos: **98% de campos correctos (55/56) y 5/5 errores plantados detectados**, unos 15 s por documento (`tools/evaluar.py`).
  - **DeepSeek-V4-Flash** responde preguntas.
  - DeepSeek-V4.1-Flash quedó descartado: tardaba de 1,5 a 4 minutos por documento.
- `ai.py`: extracción con visión, preguntas, reintentos ante 429/5xx y registro de cada llamada en `ai_calls`.
- `audit.py`: reglas fijas (fecha anterior al servicio, sumas, factura no emitida al seguro, recibo sin factura, lado del cuerpo). Cuando coinciden con la IA, el hallazgo queda como `ai+rule`.
- `ingest.py`: guarda lo extraído con trazabilidad; lo usan el cargador y la subida.
- Casos:
  1. Daniel (sintético, se llena subiendo los 11 documentos).
  2. Toby (mascota).
  3. José (real, local).
- App: subir con IA, preguntas sobre gastos, selector de casos, panel "Bajo el capó" (`#capo`), Dockerfile.

## Viernes 16: documentos reales anonimizados, paquetes y preguntas
- José pidió usar sus documentos reales (los sintéticos "se veían horribles"). Se anonimizaron **19 documentos reales** con barras negras: `demo/caso-demo/`, con `tools/anonimizar.py` (OCR local más zonas manuales en `seleccion.json`). Cada uno se revisó a ojo.
- Casos:
  1. Accidente (caso real anonimizado): el de la demo.
  2. Mascota.
  3. José (local, nunca va a la IA).
  4. Daniel (sintético, para `tools/evaluar.py`).
- `tools/cargar_demo.py` sube los 19 documentos a través de la app (con el servidor corriendo).
- Paquetes PDF (`paquetes.py`): reclamo al seguro (carta de la IA, facturas, cobertura, facturas para corregir, fotos) y pruebas para el abogado (resumen de la IA, audiencias, gastos, línea de tiempo, documentos). En la app están en Caso → Seguro y Caso → Juicio.
- Si el modelo principal no responde, se usa el de respaldo: Gemma-4-31B-IT y, si falla, Qwen3.8-Flash-Next.
- La IA pregunta cuando duda (tabla `questions`): nunca adivina nombres de medicamentos y pregunta sobre lados dudosos. Las preguntas se responden en la app.
- El lado del cuerpo del caso sale del resumen del caso, no de las órdenes que se están revisando.
- Se borran documentos con `DELETE /api/documents/{id}`.

## Viernes 16 (tarde): rediseño completo de la interfaz
- José armó una versión en Lovable (sin código descargable: se quedó sin créditos). Se usó como modelo visual de casi todas las pantallas. Calendario y Gastos siguen la maqueta propia (https://claude.ai/artifact/PV9ioz8QKcSp1joFh7Un5m).
- Colores: Día beige y burdeos, Noche carbón y menta, con botón Día/Noche. Tipografía Source Serif 4 + IBM Plex Sans + IBM Plex Mono.
- Web: índice lateral (Día a día, Dinero, Archivo, Revisión). Celular: tarjetas, la próxima dosis arriba y barra inferior con "+".
- Pantallas:
  - Hoy: cuadro de 24 h, agenda, por comprar, teléfonos, indicaciones, alertas.
  - Calendario: mes o semana, panel del día, tratamientos como barras.
  - Tratamiento: semana por medicamento y progreso.
  - Indicaciones.
  - Gastos: ítems, quién pagó editable, filtro por categoría y período, CSV, preguntas.
  - Seguro, Documentos (miniaturas reales), Contactos agrupados (+ agregar), Juicio, Alertas, Preguntas, Bajo el capó, Subir.
- Servidor nuevo: `/doses`, `/calendar`, `/instructions`, `/to-buy`, contactos agrupados, ítems por gasto, `POST /contacts`, tabla `instructions`. La IA extrae indicaciones.
- Corrección: ingest tolera alertas que el modelo devuelve como objeto.

## Privacidad del repositorio
- `demo/accidente-jose/`, con los documentos sin tapar y la transcripción completa, queda **fuera de git y de Docker** (`.gitignore` y `.dockerignore`).
- El demo público usa `demo/caso-demo/`: 35 documentos anonimizados y `ground_truth.json` limpio, generado con `tools/exportar_gt_demo.py`.
- El caso "José" solo se crea si existe la carpeta local.

## Viernes 16 (noche): caso completo y funciones nuevas
- Demo con **166 documentos reales anonimizados**: 70 documentos más 96 entre documentos, radiografías, fotos de la herida (sin caras) y cotizaciones. Cada uno revisado a ojo.
- `tools/cargar_demo.py --workers 3` sube y procesa en paralelo. `tools/preparar_demo.py` elige el día de demo con más actividad real y carga el historial de dosis.
- Funciones nuevas:
  - Preguntar (sobre todo el caso, con citas `[doc:ID]`).
  - Resumen para la consulta (PDF).
  - Avisos: audiencias, citas, por comprar, medicamento por acabarse, plazos del seguro, cobertura.
  - Cumplimiento y quién marcó cada dosis.
  - Recordatorios (Notification API + service worker + manifest PWA).
  - Escuchar el día (speechSynthesis).
  - Cotizaciones (doc_type `quote`, agrupadas por producto, marca cuál se compró).
  - Evolución del caso (hitos por mes con documentos, filtros y resumen de la IA).
  - Agregar medicamento a mano.
- La IA lee fotos de costado: `orientacion.py` detecta el giro con OCR local y gira solo la copia que va al modelo.
- Diseño de Hoy alineado con Lovable: títulos cortos de alertas y agenda, filas de una línea, franja de la hora actual, atrasadas.
- Alianza: regla `end_of_month` (la factura se presenta hasta fin del mes en que se emitió). Avisos "por vencer" y "ya no se pueden presentar".

## 2026-10-17 (madrugada): QA completo con capturas
- Los 166 documentos del caso demo procesados por Gemma-4-31B-IT. "Hoy" de la demo: 17/10/2022, reloj fijo en 15:10 (`DINDO_TIME` en `.env`, lo escribe `preparar_demo.py`), para que se vea una dosis atrasada.
- Privacidad: tapado "Para: José…" en la factura Rehalife de diciembre y la cuenta y titular de la transferencia bancaria; limpiados de la base. `leak_scan` sin hallazgos en los casos 1 y 2.
- Arreglos: el aviso "falta comprar" ya no sale si hay dosis tomadas; tarjeta roja de dosis atrasada en el celular; montos en una línea; contactos con muchos teléfonos compactados; alertas con JSON crudo corregidas (y prevenido en `ingest.py`); cotizaciones agrupadas por producto real (silla de ruedas: 9 opciones, comprada en HP Medical por 2.506 Bs); latencia en segundos; archivos web con `Cache-Control: no-cache`; `?theme=dark` en la URL.
- Resumen para la consulta (PDF): solo estudios pedidos en el último mes sin resultado; sin las preguntas internas de la IA; "sin marcar" en vez de "omitida".
- Probado de punta a punta: Preguntar (cita documentos), resumen de Evolución, PDFs de consulta, reclamo (11 facturas) y pruebas (113 documentos).

## Siguiente
1. Repo público en GitHub (sin `demo/accidente-jose` ni `.env`).
2. Deploy (Docker o hosting gratis).
3. Video demo, slides, textos de lablab (título, descripciones, tags, portada).

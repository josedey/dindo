"""Generate the synthetic demo case: fictional documents that mirror the real ones (formats and errors).

Names, clinics, phones and ID numbers are invented. Each document is drawn on a sheet, then
"photographed" (rotation, background, shadow, noise) so it looks like a phone picture.
Writes demo/caso-sintetico/*.jpg and demo/caso-sintetico/ground_truth.json (the exact answers).

Run (Windows, needs the system fonts):  python tools/generar_documentos.py
"""
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "demo" / "caso-sintetico"
FONTS = Path("C:/Windows/Fonts")
INK = (28, 45, 140)
INK2 = (40, 40, 60)
GREEN = (20, 110, 90)
PATIENT = "Daniel Vargas Suárez"
INSURER = "Seguros Andina S.A."
INSURER_NIT = "1020304050"

random.seed(7)


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


class Sheet:
    def __init__(self, w: int, h: int, paper=(250, 250, 246)):
        self.im = Image.new("RGB", (w, h), paper)
        self.d = ImageDraw.Draw(self.im)

    def text(self, xy, s, size=24, name="arial.ttf", fill=(30, 30, 30), anchor="la"):
        self.d.text(xy, s, font=font(name, size), fill=fill, anchor=anchor)

    def bold(self, xy, s, size=24, fill=(30, 30, 30), anchor="la"):
        self.text(xy, s, size, "arialbd.ttf", fill, anchor)

    def mono(self, xy, s, size=22, fill=(40, 40, 40)):
        self.text(xy, s, size, "cour.ttf", fill)

    def hand(self, xy, s, size=34, name="segoepr.ttf", fill=INK, tilt=None):
        """Handwriting: rendered on its own layer and slightly rotated."""
        f = font(name, size)
        box = self.d.textbbox((0, 0), s, font=f)
        layer = Image.new("RGBA", (box[2] + 20, box[3] + 20), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((10, 10), s, font=f, fill=fill + (235,))
        layer = layer.rotate(tilt if tilt is not None else random.uniform(-2.2, 2.2), expand=True, resample=Image.BICUBIC)
        self.im.paste(layer, (int(xy[0]), int(xy[1] - 10)), layer)

    def line(self, x1, y1, x2, y2, fill=(150, 150, 150), width=2):
        self.d.line((x1, y1, x2, y2), fill=fill, width=width)

    def rect(self, box, outline=(120, 120, 120), width=2, fill=None, radius=0):
        self.d.rounded_rectangle(box, radius=radius, outline=outline, width=width, fill=fill)

    def stamp(self, xy, lines, color=(80, 50, 150), size=20, tilt=-8):
        f = font("arialbd.ttf", size)
        w = max(self.d.textbbox((0, 0), ln, font=f)[2] for ln in lines) + 30
        h = len(lines) * (size + 6) + 22
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        dl = ImageDraw.Draw(layer)
        dl.rounded_rectangle((2, 2, w - 3, h - 3), radius=12, outline=color + (170,), width=3)
        for i, ln in enumerate(lines):
            dl.text((w / 2, 12 + i * (size + 6)), ln, font=f, fill=color + (170,), anchor="ma")
        layer = layer.rotate(tilt, expand=True, resample=Image.BICUBIC)
        self.im.paste(layer, (int(xy[0]), int(xy[1])), layer)

    def signature(self, xy, color=INK):
        pts, x, y = [], xy[0], xy[1]
        for i in range(26):
            x += random.randint(6, 14)
            y = xy[1] + random.randint(-22, 22)
            pts.append((x, y))
        self.d.line(pts, fill=color, width=3, joint="curve")

    def photo(self, name: str, bg=(110, 84, 60), angle=None):
        """Place the sheet on a background, rotate, add shadow and noise: a phone photo."""
        im = self.im
        pad = 90
        canvas = Image.new("RGB", (im.width + pad * 2, im.height + pad * 2), bg)
        grain = Image.effect_noise(canvas.size, 18).convert("RGB")
        canvas = Image.blend(canvas, Image.composite(canvas, grain, Image.new("L", canvas.size, 200)), 0.35)
        shadow = Image.new("L", canvas.size, 0)
        ImageDraw.Draw(shadow).rectangle((pad + 12, pad + 14, pad + im.width + 12, pad + im.height + 14), fill=120)
        shadow = shadow.filter(ImageFilter.GaussianBlur(14))
        canvas.paste((30, 25, 20), mask=shadow)
        canvas.paste(im, (pad, pad))
        canvas = canvas.rotate(angle if angle is not None else random.uniform(-2.5, 2.5), resample=Image.BICUBIC, fillcolor=bg)
        light = Image.linear_gradient("L").resize(canvas.size).rotate(35)
        canvas = Image.composite(canvas, Image.blend(canvas, Image.new("RGB", canvas.size, (0, 0, 0)), 0.12), light)
        noise = Image.effect_noise(canvas.size, 10).convert("RGB")
        canvas = Image.blend(canvas, noise, 0.04).filter(ImageFilter.GaussianBlur(0.6))
        canvas.thumbnail((1500, 1500))
        canvas.save(OUT / name, "JPEG", quality=86)


def invoice(issuer, address, nit, number, auth, activity, day, rows, total, words, billed_to, billed_nit, accent=GREEN):
    s = Sheet(1240, 1500)
    s.bold((60, 60), issuer[0], 52, accent)
    s.text((60, 125), issuer[1], 22, fill=(80, 80, 80))
    for i, ln in enumerate(address):
        s.text((60, 165 + i * 28), ln, 20, fill=(70, 70, 70))
    s.rect((820, 50, 1180, 200), outline=accent, width=3, radius=10)
    s.bold((1000, 65), f"NIT: {nit}", 26, accent, "ma")
    s.bold((1000, 102), "FACTURA", 22, accent, "ma")
    s.bold((1000, 132), f"Nº {number}", 30, (190, 40, 40), "ma")
    s.text((1000, 172), f"Cod. Autorización: {auth}", 16, fill=accent, anchor="ma")
    s.bold((620, 230), "FACTURA", 64, accent, "ma")
    s.text((620, 305), "(Con Derecho a Crédito Fiscal)", 22, fill=accent, anchor="ma")
    s.text((1180, 230), activity, 18, fill=(80, 80, 80), anchor="ra")
    s.text((60, 380), "Santa Cruz,", 24)
    for i, (lab, val) in enumerate(zip(("DIA", "MES", "AÑO"), day)):
        x = 210 + i * 150
        s.text((x + 60, 352), lab, 16, fill=accent, anchor="ma")
        s.rect((x, 372, x + 125, 418), outline=accent, radius=18)
        s.hand((x + 22, 374), val, 32)
    s.text((690, 385), "NIT/CI/CEX:", 22, fill=accent)
    s.line(840, 415, 1180, 415, accent)
    if billed_nit:
        s.hand((850, 372), billed_nit, 32)
    s.text((60, 455), "Nombre/Razón Social:", 22, fill=accent)
    s.line(300, 485, 1180, 485, accent)
    s.hand((320, 442), billed_to, 34)
    s.rect((60, 520, 1180, 1180), outline=accent, width=3, radius=14)
    s.d.rectangle((62, 522, 1178, 572), fill=(225, 238, 233))
    s.bold((520, 532), "D E T A L L E", 24, accent, "ma")
    s.bold((1080, 532), "SUBTOTAL", 22, accent, "ma")
    s.line(980, 522, 980, 1180, accent)
    for i in range(10):
        s.line(62, 630 + i * 55, 1178, 630 + i * 55, (190, 210, 205), 1)
    for i, (desc, amount) in enumerate(rows):
        s.hand((100, 585 + i * 55), desc, 32)
        s.hand((1000, 585 + i * 55), amount, 32)
    s.text((60, 1230), "Son:", 22)
    s.line(120, 1258, 860, 1258, accent)
    s.hand((140, 1215), words, 32)
    s.bold((900, 1220), "TOTAL Bs.", 28, accent)
    s.rect((1050, 1205, 1180, 1265), outline=accent, radius=12)
    s.hand((1058, 1212), total, 32)
    s.d.rectangle((60, 1310, 1180, 1350), fill=accent)
    s.bold((620, 1318), "ESTA FACTURA CONTRIBUYE AL DESARROLLO DEL PAÍS. EL USO ILÍCITO SERÁ SANCIONADO", 18, (255, 255, 255), "ma")
    s.text((60, 1370), "Fecha límite de emisión: 31/12/2023", 18, fill=(70, 70, 70))
    return s


def build() -> list[dict]:
    OUT.mkdir(parents=True, exist_ok=True)
    gt = []

    def add(file, **kw):
        base = {"file": file, "doctor": None, "patient_name_as_written": None, "billed_to": None, "billed_to_nit": None,
                "invoice_number": None, "line_items": [], "total": None, "currency": None, "expense_category": None,
                "medications": [], "studies_requested": [], "diagnosis_text": None, "events": [], "contacts": [],
                "handwritten": False, "legibility": "good", "anomalies": [], "notes": None}
        base.update(kw)
        gt.append(base)

    # 1. Physiotherapy invoice with the wrong year (mirrors the real Rehalife 001648)
    s = invoice(("FisioActiva", "FISIOACTIVA S.R.L. · Fisioterapia y rehabilitación"),
                ["Av. Beni N° 455, Zona Norte", "Telf.: 3-310200 · Santa Cruz - Bolivia"], "301122334", "002417",
                "29A1CC80F", "Actividades de salud humana", ("09", "01", "2022"),
                [("Paq. 10 sesiones de fisioterapia", "1.800,00"), ("- Descuento", "180,00"), ("Del 02-12-22 al 27-12-22", ""),
                 (f"Paciente: {PATIENT}", "")],
                "1.620,00", "Un mil seiscientos veinte 00/100", INSURER, INSURER_NIT)
    s.photo("01_factura_fisioterapia.jpg")
    add("01_factura_fisioterapia.jpg", doc_type="invoice", title="Factura FisioActiva N.º 002417", date="2022-01-09",
        issuer="FisioActiva S.R.L.", patient_name_as_written=PATIENT, billed_to=INSURER, billed_to_nit=INSURER_NIT,
        invoice_number="002417", line_items=[{"description": "Paq. 10 sesiones de fisioterapia", "amount": 1800},
                                             {"description": "Descuento", "amount": -180}],
        total=1620, currency="BOB", expense_category="therapy", handwritten=True,
        events=[{"kind": "session", "date": "2022-12-02", "description": "Inicio de 10 sesiones de fisioterapia (hasta 27/12/2022)"}],
        contacts=[{"name": "FisioActiva S.R.L.", "role_or_specialty": "Fisioterapia", "phones": ["3-310200"], "email": None,
                   "organization": "FisioActiva S.R.L.", "address": "Av. Beni N° 455, Zona Norte"}],
        anomalies=["La factura está fechada el 09/01/2022 pero cobra sesiones del 02/12/2022 al 27/12/2022: la fecha es anterior al servicio (probablemente 2023). El seguro podría rechazarla."])

    # 2. Handwritten prescription: anticoagulant every 12 h for 6 months + tramadol
    s = Sheet(1000, 1350)
    s.bold((500, 50), "Dr. Andrés Paz Montaño", 40, GREEN, "ma")
    s.text((500, 105), "CIRUGÍA VASCULAR Y ENDOVASCULAR", 22, fill=GREEN, anchor="ma")
    s.text((500, 140), "Calle Florida 120, Consultorio 4 · Santa Cruz", 18, fill=(90, 90, 90), anchor="ma")
    s.line(60, 180, 940, 180, GREEN, 3)
    s.text((60, 210), "Paciente:", 22)
    s.hand((180, 198), PATIENT, 34)
    s.text((60, 270), "Fecha:", 22)
    s.hand((160, 258), "20/01/2023", 34)
    s.hand((60, 340), "Rp./", 44, tilt=0)
    s.hand((120, 420), "1) Apixabán 5 mg", 44)
    s.hand((170, 490), "1 comp. cada 12 hs", 38)
    s.hand((170, 550), "por 6 meses", 38)
    s.hand((120, 650), "2) Tramadol 50 mg", 44)
    s.hand((170, 720), "1 comp. cada 8 hs x 5 días", 38)
    s.hand((170, 780), "si hay dolor", 38)
    s.hand((120, 880), "Medias de compresión 20-30 mmHg", 34)
    s.signature((560, 1100))
    s.stamp((560, 1140), ["Dr. Andrés Paz Montaño", "CIRUJANO VASCULAR", "M.P. P-1187"])
    s.photo("02_receta_anticoagulante.jpg", bg=(200, 205, 210))
    add("02_receta_anticoagulante.jpg", doc_type="prescription", title="Receta Dr. Paz Montaño (anticoagulante)", date="2023-01-20",
        issuer="Dr. Andrés Paz Montaño", doctor={"name": "Dr. Andrés Paz Montaño", "specialty": "Cirugía vascular", "license": "P-1187"},
        patient_name_as_written=PATIENT, handwritten=True,
        medications=[{"name": "Apixabán", "dose": "5 mg", "frequency": "cada 12 horas", "duration": "6 meses", "instructions": "1 comprimido"},
                     {"name": "Tramadol", "dose": "50 mg", "frequency": "cada 8 horas", "duration": "5 días", "instructions": "si hay dolor"}],
        notes="Indica además medias de compresión 20-30 mmHg.")

    # 3. CT order that says RIGHT knee (the case is the LEFT knee)
    s = Sheet(1240, 1450)
    s.bold((60, 60), "CLÍNICA SANTA LUCÍA", 44, (30, 70, 140))
    s.text((60, 115), "Amamos cuidar", 20, fill=(90, 90, 90))
    s.bold((1180, 70), "Solicitud de Imagen", 40, anchor="ra")
    rows = [("Fecha y Hora:", "14 de Diciembre del 2022 Hrs. 11:31"), ("Paciente:", "Vargas Suárez Daniel"),
            ("Expediente Clínico:", "552014"), ("Seguro:", "Sin Seguro"), ("Médico Solicitante:", "Antelo Ribera Marcelo"),
            ("Especialidad:", "TRAUMATOLOGÍA ADULTOS")]
    for i, (k, v) in enumerate(rows):
        s.bold((520, 170 + i * 34), k, 20, anchor="ra")
        s.mono((540, 170 + i * 34), v, 20)
    s.line(60, 400, 1180, 400, (100, 100, 100))
    s.mono((60, 430), "Tomografía Rodilla Sin Contraste", 24)
    s.bold((60, 500), "MOTIVO DEL ESTUDIO", 24)
    s.mono((60, 540), "Dolor persistente", 22)
    s.bold((60, 600), "DIAGNÓSTICO", 24)
    s.mono((60, 640), "Z54.4 Convalecencia consecutiva a tratamiento de fractura", 22)
    s.bold((60, 700), "OBSERVACIÓN", 24)
    s.mono((60, 740), "TAC DE RODILLA CON RECONSTRUCCIÓN DE RODILLA DERECHA", 22)
    s.signature((640, 1050))
    s.stamp((640, 1090), ["Dr. Marcelo Antelo Ribera", "TRAUMATOLOGÍA Y ORTOPEDIA", "M.P. A-2290"], color=(40, 70, 150))
    s.text((620, 1380), "Av. Irala 900 · Emergencias T. 3-336000 · www.clinicasantalucia.bo (ficticio)", 16, fill=(90, 90, 90), anchor="ma")
    s.photo("03_orden_tomografia.jpg", bg=(60, 60, 65))
    add("03_orden_tomografia.jpg", doc_type="study_order", title="Solicitud de tomografía de rodilla (Clínica Santa Lucía)", date="2022-12-14",
        issuer="Clínica Santa Lucía", doctor={"name": "Dr. Marcelo Antelo Ribera", "specialty": "Traumatología", "license": "A-2290"},
        patient_name_as_written="Vargas Suárez Daniel", diagnosis_text="Z54.4 Convalecencia consecutiva a tratamiento de fractura",
        studies_requested=[{"name": "Tomografía de rodilla sin contraste con reconstrucción", "body_side": "right", "reason": "Dolor persistente"}],
        contacts=[{"name": "Clínica Santa Lucía", "role_or_specialty": "Clínica", "phones": ["3-336000"], "email": None,
                   "organization": "Clínica Santa Lucía", "address": "Av. Irala 900"}],
        anomalies=["La orden pide tomografía de rodilla DERECHA, pero la lesión del paciente es la rodilla IZQUIERDA (resto del caso). Confirmar con el médico antes de hacer el estudio.",
                   "Figura 'Sin Seguro' aunque el paciente tiene seguro (Seguros Andina S.A.)."])

    # 4. Handwritten medical report: left tibial plateau fracture, asks for MRI
    s = Sheet(1000, 1500, paper=(252, 252, 250))
    s.bold((500, 50), "MÉDICOS UNIDOS", 46, GREEN, "ma")
    s.text((500, 110), "Policonsultorio · C/ Sucre 340 · Telf. 3-345870", 20, fill=GREEN, anchor="ma")
    s.line(60, 150, 940, 150, GREEN, 3)
    s.hand((330, 190), "Informe Médico", 48, tilt=0)
    lines = ["Paciente Daniel Vargas Suárez con", "diagnóstico de osteosíntesis de", "meseta tibial izquierda y posible",
             "lesión meniscal de rodilla izquierda.", "Se solicita Resonancia Magnética", "de rodilla izquierda para descartar",
             "lesión meniscal. Paciente con", "limitación funcional de rodilla izq."]
    for i, ln in enumerate(lines):
        s.hand((70, 300 + i * 78), ln, 38)
    s.hand((70, 960), "Santa Cruz, 02 de diciembre de 2022", 32)
    s.signature((520, 1150))
    s.stamp((520, 1190), ["Dr. Iván Rocha Ortiz", "TRAUMATÓLOGO", "M.P. R-0931"], color=(30, 90, 70))
    s.photo("04_informe_medico.jpg", bg=(40, 40, 42))
    add("04_informe_medico.jpg", doc_type="medical_report", title="Informe médico Dr. Rocha (Médicos Unidos)", date="2022-12-02",
        issuer="Médicos Unidos", doctor={"name": "Dr. Iván Rocha Ortiz", "specialty": "Traumatología", "license": "R-0931"},
        patient_name_as_written=PATIENT, handwritten=True, legibility="fair",
        diagnosis_text="Osteosíntesis de meseta tibial izquierda y posible lesión meniscal de rodilla izquierda",
        studies_requested=[{"name": "Resonancia magnética de rodilla", "body_side": "left", "reason": "Descartar lesión meniscal"}],
        contacts=[{"name": "Dr. Iván Rocha Ortiz", "role_or_specialty": "Traumatología", "phones": ["3-345870"], "email": None,
                   "organization": "Médicos Unidos", "address": "C/ Sucre 340"}])

    # 5. Invoice with a wrong total after the discount
    s = invoice(("Clínica Santa Lucía", "CLÍNICA SANTA LUCÍA S.A. · Servicios de salud"),
                ["Av. Irala 900", "Telf.: 3-336000 · Santa Cruz - Bolivia"], "102233445", "018832", "77F0A1B2C",
                "Servicio de salud en clínica", ("14", "12", "2022"),
                [("Consulta traumatología", "300,00"), ("Rx rodilla izquierda AP y lateral", "450,00"), ("Descuento 10%", "75,00")],
                "700,00", "Setecientos 00/100", INSURER, INSURER_NIT, accent=(30, 70, 140))
    s.photo("05_factura_clinica.jpg", bg=(150, 120, 90))
    add("05_factura_clinica.jpg", doc_type="invoice", title="Factura Clínica Santa Lucía N.º 018832", date="2022-12-14",
        issuer="Clínica Santa Lucía S.A.", billed_to=INSURER, billed_to_nit=INSURER_NIT, invoice_number="018832",
        line_items=[{"description": "Consulta traumatología", "amount": 300}, {"description": "Rx rodilla izquierda AP y lateral", "amount": 450},
                    {"description": "Descuento 10%", "amount": -75}],
        total=700, currency="BOB", expense_category="lab_imaging", handwritten=True,
        events=[{"kind": "appointment", "date": "2022-12-14", "description": "Consulta de traumatología y radiografía de rodilla izquierda"}],
        anomalies=["Error de suma: 300 + 450 - 75 = 675 Bs, pero el total escrito es 700 Bs (25 Bs de más)."])

    # 6. Pharmacy invoice NOT billed to the insurer
    s = invoice(("FarmaSalud", "FARMASALUD S.R.L. · Farmacia"), ["Av. Cristo Redentor 2100", "Telf.: 3-422100 · Santa Cruz - Bolivia"],
                "309988776", "145520", "5B21D0E44", "Venta de medicamentos", ("20", "01", "2023"),
                [("Apixabán 5 mg x 60 comp.", "312,50"), ("Medias compresión 20-30", "74,00")],
                "386,50", "Trescientos ochenta y seis 50/100", "Daniel Vargas", "6123457", accent=(170, 60, 60))
    s.photo("06_factura_farmacia.jpg", bg=(225, 225, 228))
    add("06_factura_farmacia.jpg", doc_type="invoice", title="Factura FarmaSalud N.º 145520", date="2023-01-20",
        issuer="FarmaSalud S.R.L.", billed_to="Daniel Vargas", billed_to_nit="6123457", invoice_number="145520",
        line_items=[{"description": "Apixabán 5 mg x 60 comp.", "amount": 312.5}, {"description": "Medias compresión 20-30", "amount": 74}],
        total=386.5, currency="BOB", expense_category="medication", handwritten=True,
        anomalies=["La factura está a nombre del paciente (Daniel Vargas, CI 6123457) y no del seguro Seguros Andina S.A. (NIT 1020304050): no sería reembolsable. Pedir que la rehagan."])

    # 7. Referral with the doctor's phones in the stamp
    s = Sheet(1000, 1300)
    s.bold((60, 50), "centro vascular", 30, (60, 60, 110))
    s.bold((60, 85), "ORIENTE", 54, (60, 60, 110))
    s.text((940, 60), "Cirugía vascular · Várices · Ecografía doppler", 18, fill=(90, 90, 90), anchor="ra")
    s.line(60, 170, 940, 170, (60, 60, 110), 2)
    s.hand((60, 210), "Rp./", 44, tilt=0)
    s.hand((180, 330), "Ecodoppler venoso", 44)
    s.hand((180, 400), "de miembro inferior", 44)
    s.hand((180, 470), "izquierdo", 44)
    s.text((60, 900), "Nombre:", 22)
    s.hand((170, 888), "Daniel V. Suárez", 34)
    s.text((60, 960), "Diagnóstico:", 22)
    s.hand((220, 948), "Síndrome postrombótico", 34)
    s.text((60, 1020), "Santa Cruz,", 22)
    s.hand((200, 1008), "20 de enero de 2023", 34)
    s.stamp((520, 860), ["Dr. Andrés Paz Montaño", "Cirujano Vascular · M.P. P-1187", "Cons.: 3-344556  Cel.: 70011223",
                         "Secretaria: 76655443", "andres.paz@correo-ficticio.bo"], color=(50, 60, 150), size=18, tilt=4)
    s.photo("07_derivacion_ecodoppler.jpg", bg=(235, 235, 238))
    add("07_derivacion_ecodoppler.jpg", doc_type="study_order", title="Orden de ecodoppler venoso (Dr. Paz Montaño)", date="2023-01-20",
        issuer="Centro Vascular Oriente", doctor={"name": "Dr. Andrés Paz Montaño", "specialty": "Cirugía vascular", "license": "P-1187"},
        patient_name_as_written="Daniel V. Suárez", handwritten=True, diagnosis_text="Síndrome postrombótico",
        studies_requested=[{"name": "Ecodoppler venoso de miembro inferior", "body_side": "left", "reason": "Síndrome postrombótico"}],
        contacts=[{"name": "Dr. Andrés Paz Montaño", "role_or_specialty": "Cirugía vascular",
                   "phones": ["3-344556", "70011223", "76655443"], "email": "andres.paz@correo-ficticio.bo",
                   "organization": "Centro Vascular Oriente", "address": None}],
        notes="76655443 es el teléfono de la secretaria.")

    # 8. Physiotherapy attendance sheet (10 signed sessions)
    s = Sheet(1000, 1400)
    s.bold((60, 50), "FisioActiva", 44, GREEN)
    s.text((60, 105), "Av. Beni N° 455 · Telf. 3-310200", 18, fill=(90, 90, 90))
    s.bold((60, 170), f"Para: {PATIENT.upper()}", 22)
    s.bold((60, 205), f"Seguro: {INSURER.upper()}", 22)
    s.bold((60, 240), "Otra especificación: 10 SESIONES", 22)
    s.bold((60, 300), "ASISTENCIA:", 24)
    dates = ["Vie 02/12/22", "Lun 05/12/22", "Mié 07/12/22", "Vie 09/12/22", "Lun 12/12/22",
             "Mié 14/12/22", "Vie 16/12/22", "Lun 19/12/22", "Mié 21/12/22", "Mar 27/12/22"]
    for i, d in enumerate(dates):
        y = 350 + i * 80
        s.text((60, y + 10), f"{i + 1}.", 24)
        s.line(100, y + 50, 440, y + 50)
        s.hand((110, y), d, 32)
        s.line(520, y + 50, 900, y + 50)
        s.signature((540, y + 25))
    s.photo("08_asistencia_fisioterapia.jpg", bg=(120, 95, 70))
    add("08_asistencia_fisioterapia.jpg", doc_type="attendance_sheet", title="Asistencia a fisioterapia FisioActiva (10 sesiones)", date="2022-12-27",
        issuer="FisioActiva S.R.L.", patient_name_as_written=PATIENT.upper(), handwritten=True,
        events=[{"kind": "session", "date": f"2022-12-{d[4:6]}", "description": f"Sesión de fisioterapia {i + 1} de 10"} for i, d in enumerate(dates)],
        notes="Coincide con la factura FisioActiva N.º 002417 (10 sesiones del 02 al 27/12/2022).")

    # 9. Court summons to a conciliation hearing
    s = Sheet(1240, 1600)
    s.bold((620, 60), "ÓRGANO JUDICIAL DE BOLIVIA", 30, anchor="ma")
    s.bold((620, 105), "JUZGADO DE INSTRUCCIÓN PENAL TERCERO · SANTA CRUZ", 24, anchor="ma")
    s.text((620, 150), "(documento ficticio para demostración)", 18, fill=(120, 120, 120), anchor="ma")
    s.line(100, 190, 1140, 190, (60, 60, 60), 2)
    s.bold((620, 230), "CITACIÓN", 40, anchor="ma")
    body = ["Caso N.º: FIS-SCZ-2210457", "Delito: Lesiones graves y gravísimas en accidente de tránsito",
            f"Víctima: {PATIENT}", "Imputado: Rodrigo Medina Flores", "",
            "Se cita a las partes a AUDIENCIA DE CONCILIACIÓN a llevarse a cabo",
            "el día MARTES 05 DE NOVIEMBRE DE 2023 a horas 09:00, en Sala 4",
            "del Juzgado de Instrucción Penal Tercero (Palacio de Justicia, piso 2).", "",
            "La inasistencia injustificada dará lugar a las acciones de ley.",
            "Fiscal asignada: Dra. Lorena Ibáñez Cuéllar.",
            "Abogado de la víctima: Abg. Javier Rojas Terrazas · Cel. 71122334."]
    for i, ln in enumerate(body):
        s.text((110, 320 + i * 44), ln, 24)
    s.text((110, 950), "Santa Cruz, 18 de octubre de 2023", 24)
    s.signature((760, 1120), color=INK2)
    s.stamp((700, 1160), ["JUZGADO DE INSTRUCCIÓN", "PENAL 3.º · SANTA CRUZ"], color=(120, 30, 40))
    s.photo("09_citacion_audiencia.jpg", bg=(70, 70, 75))
    add("09_citacion_audiencia.jpg", doc_type="legal", title="Citación a audiencia de conciliación (Caso FIS-SCZ-2210457)", date="2023-10-18",
        issuer="Juzgado de Instrucción Penal Tercero, Santa Cruz", patient_name_as_written=PATIENT,
        events=[{"kind": "hearing", "date": "2023-11-05", "description": "Audiencia de conciliación, 09:00, Sala 4, Juzgado de Instrucción Penal Tercero (Palacio de Justicia, piso 2)"}],
        contacts=[{"name": "Abg. Javier Rojas Terrazas", "role_or_specialty": "Abogado de la víctima", "phones": ["71122334"], "email": None,
                   "organization": None, "address": None},
                  {"name": "Dra. Lorena Ibáñez Cuéllar", "role_or_specialty": "Fiscal", "phones": [], "email": None,
                   "organization": "Fiscalía", "address": None}],
        notes="Caso penal por lesiones en accidente de tránsito; imputado Rodrigo Medina Flores.")

    # 10. Handwritten ambulance receipt (no invoice: not reimbursable)
    s = Sheet(1000, 700, paper=(255, 253, 240))
    s.bold((60, 40), "RECIBO", 40, (150, 40, 40))
    s.bold((940, 45), "Nº 0381", 30, (150, 40, 40), "ra")
    s.text((60, 120), "Recibí de:", 24)
    s.hand((200, 108), "Familia Vargas", 36)
    s.text((60, 190), "La suma de:", 24)
    s.hand((220, 178), "Trescientos cincuenta 00/100 Bs", 36)
    s.text((60, 260), "Por concepto de:", 24)
    s.hand((280, 248), "Traslado en ambulancia, bajar del", 34)
    s.hand((280, 305), "2º piso (pac. 105 kg) a fisioterapia", 34)
    s.text((60, 400), "Fecha:", 24)
    s.hand((160, 388), "05/12/2022", 36)
    s.text((600, 400), "Bs.", 26)
    s.hand((660, 385), "350.-", 42)
    s.signature((560, 520))
    s.text((560, 600), "Ambulancias Rápido Auxilio · Cel. 77788990", 18, fill=(90, 90, 90))
    s.photo("10_recibo_ambulancia.jpg", bg=(190, 160, 120))
    add("10_recibo_ambulancia.jpg", doc_type="receipt", title="Recibo de ambulancia N.º 0381", date="2022-12-05",
        issuer="Ambulancias Rápido Auxilio", total=350, currency="BOB", expense_category="transport", handwritten=True,
        line_items=[{"description": "Traslado en ambulancia del 2º piso a fisioterapia", "amount": 350}],
        contacts=[{"name": "Ambulancias Rápido Auxilio", "role_or_specialty": "Ambulancia", "phones": ["77788990"], "email": None,
                   "organization": "Ambulancias Rápido Auxilio", "address": None}],
        anomalies=["Es un recibo simple, no una factura con NIT: el seguro normalmente no lo reembolsa."])

    # 11. Veterinary prescription (second case: the dog)
    s = Sheet(900, 1250, paper=(250, 252, 255))
    s.bold((450, 40), "Clínica Veterinaria Patitas", 36, (40, 100, 160), "ma")
    s.text((450, 92), "Av. Piraí 777 · Cel. 69900112 (ficticio)", 18, fill=(90, 90, 90), anchor="ma")
    s.line(50, 130, 850, 130, (40, 100, 160), 3)
    s.text((50, 160), "Paciente:", 22)
    s.hand((170, 148), "Toby (perro, 4 años, 12 kg)", 32)
    s.text((50, 220), "Propietario:", 22)
    s.hand((200, 208), "Daniel Vargas", 32)
    s.text((50, 280), "Fecha:", 22)
    s.hand((140, 268), "24/05/2024", 32)
    s.hand((50, 350), "Rp./", 40, tilt=0)
    s.hand((90, 430), "Doxiciclina 100 mg", 38)
    s.hand((130, 495), "1/4 comp. cada 24 hs x 25 días", 32)
    s.hand((90, 590), "Ferrocan jarabe", 38)
    s.hand((130, 655), "3 ml cada 24 hs x 15 días", 32)
    s.hand((130, 715), "después de la comida", 32)
    s.signature((450, 960))
    s.stamp((430, 1000), ["M.V. Paula Gil Rivero", "Médica Veterinaria"], color=(40, 100, 160))
    s.photo("11_receta_veterinaria.jpg", bg=(210, 200, 185))
    add("11_receta_veterinaria.jpg", doc_type="prescription", title="Receta veterinaria de Toby (Clínica Patitas)", date="2024-05-24",
        issuer="Clínica Veterinaria Patitas", doctor={"name": "M.V. Paula Gil Rivero", "specialty": "Medicina veterinaria", "license": None},
        patient_name_as_written="Toby", handwritten=True,
        medications=[{"name": "Doxiciclina", "dose": "1/4 comprimido de 100 mg", "frequency": "cada 24 horas", "duration": "25 días", "instructions": None},
                     {"name": "Ferrocan", "dose": "3 ml", "frequency": "cada 24 horas", "duration": "15 días", "instructions": "después de la comida"}],
        contacts=[{"name": "Clínica Veterinaria Patitas", "role_or_specialty": "Veterinaria", "phones": ["69900112"], "email": None,
                   "organization": "Clínica Veterinaria Patitas", "address": "Av. Piraí 777"}],
        notes="Paciente: Toby, perro de 4 años y 12 kg; propietario Daniel Vargas. Pertenece al caso de la mascota.")

    (OUT / "ground_truth.json").write_text(json.dumps(gt, ensure_ascii=False, indent=2), encoding="utf-8")
    return gt


if __name__ == "__main__":
    docs = build()
    print(f"{len(docs)} documents written to {OUT}")

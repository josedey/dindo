"""Anonymize the selected real documents: cover personal data with black bars.

Personal data is found with a local OCR engine (nothing leaves the computer), plus manual boxes for what OCR
can't read (handwriting, signatures). Clinics, doctors, dates, amounts, medications and the real errors stay.

Input:  demo/caso-demo/seleccion.json   [{"out", "src" (relative to demo/accidente-jose/), "case", "boxes"?}]
        "boxes" are extra rectangles in relative coordinates [x0, y0, x1, y1] (0..1).
Output: demo/caso-demo/<out> and demo/caso-demo/ocr_matches.txt (what was covered, for review).

Run:  python tools/anonimizar.py
"""
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps
from rapidocr_onnxruntime import RapidOCR

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "demo" / "accidente-jose"
OUT = ROOT / "demo" / "caso-demo"

# Patient, family and third parties (names, ID numbers, phones, birth dates, file numbers, plates, home address).
# The names, ID numbers and phones to cover are personal, so they live in a local file that never goes to the
# repository: demo/accidente-jose/pii.json {"pattern": "<regex>"}. Without it only generic ID patterns are covered.
_LOCAL = SRC / "pii.json"
PII = re.compile(json.loads(_LOCAL.read_text(encoding="utf-8"))["pattern"] if _LOCAL.exists()
                 else r"\b(C\.?I\.?|CI)\s*:?\s*\d{6,8}\b|cta\.?\s*\d{6,}", re.I)


def cover(draw: ImageDraw.ImageDraw, box, pad=6):
    x0, y0, x1, y1 = box
    draw.rectangle((x0 - pad, y0 - pad, x1 + pad, y1 + pad), fill=(18, 18, 18))


def main():
    sel = json.loads((OUT / "seleccion.json").read_text(encoding="utf-8"))
    ocr = RapidOCR()
    log = []
    for item in sel:
        im = ImageOps.exif_transpose(Image.open(SRC / item["src"])).convert("RGB")
        im.thumbnail((1800, 1800))
        draw = ImageDraw.Draw(im)
        result, _ = ocr(im) if True else (None, None)
        hits = 0
        for quad, text, conf in result or []:
            for m in PII.finditer(text):
                xs, ys = [p[0] for p in quad], [p[1] for p in quad]
                x0, x1 = min(xs), max(xs)
                # Cover only the matched part of the line, estimated from character positions.
                n = max(len(text), 1)
                a = x0 + (x1 - x0) * m.start() / n
                b = x0 + (x1 - x0) * m.end() / n
                cover(draw, (a, min(ys), b, max(ys)))
                hits += 1
                log.append(f"{item['out']}: '{m.group(0)}' in '{text}'")
        for bx in item.get("boxes", []):
            w, h = im.size
            cover(draw, (bx[0] * w, bx[1] * h, bx[2] * w, bx[3] * h), pad=0)
        if item.get("rotate"):  # applied after covering, so the boxes keep their coordinates
            im = im.rotate(item["rotate"], expand=True)
        im.save(OUT / item["out"], "JPEG", quality=88)
        print(f"{item['out']:<36} OCR hits: {hits:>2}  manual boxes: {len(item.get('boxes', []))}")
    (OUT / "ocr_matches.txt").write_text("\n".join(log), encoding="utf-8")


if __name__ == "__main__":
    main()

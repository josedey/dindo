"""Find how much a document photo must be turned so the AI reads it upright (the stored photo is never changed).

Uses a local OCR engine (nothing leaves the machine). Step 1, fast: detect the text lines and check whether most of
them run vertically. Step 2, only for sideways photos: read both 90° turns and keep the one that reads better.
"""
from functools import lru_cache

from PIL import Image


@lru_cache(maxsize=1)
def _ocr():
    try:
        from rapidocr_onnxruntime import RapidOCR
        return RapidOCR()
    except Exception:  # optional dependency: without it, images are sent as they are
        return None


def _boxes(ocr, im):
    result, _ = ocr(im, use_det=True, use_cls=False, use_rec=False)
    return result or []


def _readability(ocr, im) -> float:
    result, _ = ocr(im)
    return sum(len(text) * float(conf) for _, text, conf in result or [])


def best_rotation(im: Image.Image) -> int:
    """Degrees (counter-clockwise, PIL convention) to make the text upright: 0, 90 or 270."""
    ocr = _ocr()
    if ocr is None:
        return 0
    small = im.convert("RGB")
    small.thumbnail((900, 900))
    boxes = _boxes(ocr, small)
    if not boxes:
        return 0
    vertical = sum(1 for b in boxes if (max(p[1] for p in b) - min(p[1] for p in b)) > 1.6 * (max(p[0] for p in b) - min(p[0] for p in b)))
    if vertical < 0.6 * len(boxes):
        return 0
    left, right = _readability(ocr, small.rotate(90, expand=True)), _readability(ocr, small.rotate(270, expand=True))
    return 90 if left >= right else 270

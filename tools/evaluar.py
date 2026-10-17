"""Score an AMD vision model on the synthetic documents against their known contents.

Run:  python tools/evaluar.py [MODEL ...]      (default: the AMD_VISION_MODEL in .env)
Writes demo/caso-sintetico/eval/<model>/<file>.json and prints a field-by-field score.
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dindo.servidor import ai, config, db  # noqa: E402
from dindo.servidor.ingest import norm  # noqa: E402

DIR = config.DEMO_DIR / "caso-sintetico"
CASE = {"title": "Accidente de Daniel", "subject_name": "Daniel Vargas Suárez", "subject_kind": "person",
        "summary": "Fractura de meseta tibial izquierda por accidente de tránsito."}
INSURER = {"insurer": "Seguros Andina S.A.", "nit": "1020304050"}
# The error planted in each document, and words that show the model noticed it.
PLANTED = {"01_factura_fisioterapia.jpg": r"fecha|anterior|2022|2023", "03_orden_tomografia.jpg": r"derech|izquierd",
           "05_factura_clinica.jpg": r"suma|675|total", "06_factura_farmacia.jpg": r"nombre|nit|seguro|reembols",
           "10_recibo_ambulancia.jpg": r"recibo|factura|reembols"}


def digits(s) -> str:
    return re.sub(r"\D", "", str(s or ""))


def score(gt: dict, out: dict) -> dict[str, bool]:
    r = {"tipo": gt["doc_type"] == out.get("doc_type"), "fecha": gt["date"] == out.get("date")}
    if gt.get("total") is not None:
        r["total"] = out.get("total") is not None and abs(float(gt["total"]) - float(out["total"])) < 0.01
    if gt.get("invoice_number"):
        r["n_factura"] = digits(gt["invoice_number"]).lstrip("0") == digits(out.get("invoice_number")).lstrip("0")
    if gt.get("billed_to_nit"):
        r["nit"] = digits(gt["billed_to_nit"]) == digits(out.get("billed_to_nit"))
    for m in gt.get("medications") or []:
        got = [x for x in out.get("medications") or [] if norm(m["name"])[:6] in norm(x.get("name"))]
        r[f"med:{m['name']}"] = bool(got)
        r[f"frec:{m['name']}"] = bool(got) and digits(m["frequency"]) == digits(got[0].get("frequency"))
    for s in gt.get("studies_requested") or []:
        r["lado_estudio"] = any(x.get("body_side") == s["body_side"] for x in out.get("studies_requested") or [])
    phones = {digits(p) for c in gt.get("contacts") or [] for p in c.get("phones") or []}
    if phones:
        got = {digits(p) for c in out.get("contacts") or [] for p in c.get("phones") or []}
        r["teléfonos"] = phones <= got
    for h in [e for e in gt.get("events") or [] if e["kind"] == "hearing"]:
        r["audiencia"] = any(e.get("date") == h["date"] for e in out.get("events") or [])
    if gt["file"] in PLANTED:
        r["error_detectado"] = bool(re.search(PLANTED[gt["file"]], " ".join(out.get("anomalies") or []).lower()))
    return r


def main(models: list[str]) -> None:
    db.init()
    gts = json.loads((DIR / "ground_truth.json").read_text(encoding="utf-8"))
    for model in models:
        outdir = DIR / "eval" / model
        outdir.mkdir(parents=True, exist_ok=True)
        ok = total = caught = planted = 0
        t0 = time.monotonic()
        print(f"\n=== {model} ===")
        for gt in gts:
            case = dict(CASE, subject_name="Toby", subject_kind="pet") if gt["file"].startswith("11_") else CASE
            try:
                out = ai.extract_document(DIR / gt["file"], case, None if gt["file"].startswith("11_") else INSURER, model=model)
            except Exception as e:  # keep scoring the rest
                print(f"  {gt['file']}: ERROR {e}")
                continue
            (outdir / (gt["file"] + ".json")).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
            r = score(gt, out)
            ok += sum(r.values())
            total += len(r)
            if "error_detectado" in r:
                planted += 1
                caught += r["error_detectado"]
            misses = [k for k, v in r.items() if not v]
            print(f"  {gt['file']:<32} {sum(r.values())}/{len(r)}" + (f"   falló: {', '.join(misses)}" if misses else ""))
        if total:
            print(f"  TOTAL campos: {ok}/{total} = {ok / total:.0%} · errores plantados detectados: {caught}/{planted} · {time.monotonic() - t0:.0f} s")


if __name__ == "__main__":
    main(sys.argv[1:] or [config.AMD_VISION_MODEL])

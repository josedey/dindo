"""Write demo/caso-demo/ground_truth.json: the transcription of the anonymized demo documents, with personal data scrubbed.

The full transcription (demo/accidente-jose/) stays local and out of the public repository; this file lets the
public demo be seeded offline (python -m dindo.servidor.seed --gt).

Run:  python tools/exportar_gt_demo.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.anonimizar import PII  # noqa: E402

REAL = ROOT / "demo" / "accidente-jose"
DEMO = ROOT / "demo" / "caso-demo"
_LOCAL = REAL / "pii.json"  # local only: the family's phone numbers
FAMILY_PHONES = set(json.loads(_LOCAL.read_text(encoding="utf-8")).get("family_phones", [])) if _LOCAL.exists() else set()
ANON = "[anonimizado]"


def scrub(v):
    if isinstance(v, str):
        return PII.sub(ANON, v)
    if isinstance(v, list):
        return [scrub(x) for x in v]
    if isinstance(v, dict):
        return {k: scrub(x) for k, x in v.items()}
    return v


def main():
    by_file = {}
    for f in sorted(REAL.glob("ground_truth*.json")):
        for it in json.loads(f.read_text(encoding="utf-8")):
            by_file[it["file"]] = it
    out = []
    for sel in json.loads((DEMO / "seleccion.json").read_text(encoding="utf-8")):
        it = dict(by_file.get(sel["src"]) or {"doc_type": "other", "title": sel["out"]})
        it["contacts"] = [c for c in it.get("contacts") or []
                          if not FAMILY_PHONES & {re.sub(r"\D", "", p) for p in c.get("phones") or []}]
        if it.get("patient_name_as_written"):
            it["patient_name_as_written"] = ANON
        it = scrub(it)
        it["file"] = sel["out"]
        it["case"] = sel["case"]
        out.append(it)
    (DEMO / "ground_truth.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    left = [m.group(0) for it in out for m in PII.finditer(json.dumps(it, ensure_ascii=False))]
    print(f"{len(out)} documents written; personal data left: {left or 'none'}")


if __name__ == "__main__":
    main()

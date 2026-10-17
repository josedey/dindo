"""Upload the anonymized demo documents through the running app, so the AMD models fill the demo cases.

Run (with the server up):  python tools/cargar_demo.py [--base http://127.0.0.1:8000] [--from N] [--to M] [--workers 3]
"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo" / "caso-demo"


def arg(name, default):
    return type(default)(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


BASE = arg("--base", "http://127.0.0.1:8000")


def upload(client, case_id, sel):
    t0 = time.monotonic()
    with (DEMO / sel["out"]).open("rb") as f:
        r = client.post(f"{BASE}/api/cases/{case_id}/documents", files={"file": (sel["out"], f, "image/jpeg")})
    if r.status_code != 200:
        return f"{sel['out']:<36} ERROR {r.status_code} {r.text[:150]}"
    d = r.json()
    alerts = [x["detail"][:60] for x in d["linked"]["findings"] if x["severity"] != "info"]
    return (f"{sel['out']:<36} {time.monotonic() - t0:4.0f}s {d['extracted'].get('_model', ''):<19} {d['doc_type']:<18}"
            f" q:{len(d['linked']['questions'])} {' / '.join(alerts)}")


def main():
    cases = {c["title"]: c["id"] for c in httpx.get(f"{BASE}/api/cases").json()}
    target = {"real": cases["Accidente (caso real anonimizado)"], "pet": cases["Mascota"]}
    first, upto = arg("--from", 0), arg("--to", 10 ** 6)
    todo = [s for s in json.loads((DEMO / "seleccion.json").read_text(encoding="utf-8")) if first <= int(s["out"].split("_")[0]) <= upto]
    with httpx.Client(timeout=900) as client, ThreadPoolExecutor(arg("--workers", 3)) as pool:
        for line in pool.map(lambda s: upload(client, target[s["case"]], s), todo):
            print(line, flush=True)


if __name__ == "__main__":
    main()

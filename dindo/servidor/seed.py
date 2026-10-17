"""Reset the demo database.

Cases:
  1. "Accidente (caso real anonimizado)": José's real documents with personal data covered (demo/caso-demo/),
     the public demo case.
  2. "Mascota": the real veterinary prescription.
  3. "Accidente de José": José's full real case from the ground-truth transcriptions. Local only: it is never
     sent to the AI service (Token Factory terms forbid identifiable health data).
  4. "Daniel (sintético)": fictional documents used to measure extraction accuracy (tools/evaluar.py).

Cases 1, 2 and 4 start empty so the demo shows the AMD models filling them. Pass --gt to fill them from their
ground truth instead (works offline, used by the Docker image).

Run:  python -m dindo.servidor.seed [--gt]
"""
import json
import sys

from . import audit, config, db
from .ingest import ingest_item

REAL_DIR = config.DEMO_DIR / "accidente-jose"
# Names for the local-only case come from a local file, so they never reach the repository.
LOCAL_CASE = json.loads((REAL_DIR / "pii.json").read_text(encoding="utf-8")).get("case", {}) if (REAL_DIR / "pii.json").exists() else {}
DEMO_DIR = config.DEMO_DIR / "caso-demo"
SYNTH_DIR = config.DEMO_DIR / "caso-sintetico"


def excluded() -> set[str]:
    f = REAL_DIR / "excluir.txt"
    lines = f.read_text(encoding="utf-8").splitlines() if f.exists() else []
    return {ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")}


def real_items() -> list[dict]:
    items = []
    for f in sorted(REAL_DIR.glob("ground_truth*.json")):
        try:
            items += json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            print(f"Skipping {f.name}: not valid JSON")
    return items


def anonymized_items() -> list[tuple[str, dict]]:
    """Transcription of the anonymized demo documents (personal data scrubbed, see tools/exportar_gt_demo.py)."""
    f = DEMO_DIR / "ground_truth.json"
    return [(it.get("case", "real"), it) for it in json.loads(f.read_text(encoding="utf-8"))] if f.exists() else []


def new_case(con, title, subject, kind, summary, members, insurer=None) -> int:
    case_id = con.execute("INSERT INTO cases (title, subject_name, subject_kind, summary) VALUES (?,?,?,?)",
                          (title, subject, kind, summary)).lastrowid
    con.executemany("INSERT INTO members (case_id, name, role, color) VALUES (?,?,?,?)", [(case_id, *m) for m in members])
    if insurer:
        con.execute("INSERT INTO insurance (case_id, insurer, nit, coverage_limit, claim_days, claim_rule) VALUES (?,?,?,?,?,?)",
                    (case_id, *insurer, "end_of_month" if insurer[1] == "1015327022" else None))
    return case_id


def seed(fill: bool = False) -> None:
    if config.DB_PATH.exists():
        config.DB_PATH.unlink()
    db.init()
    alianza = ("Alianza Vida Seguros y Reaseguros S.A.", "1015327022", 12000, None)  # invoices accepted only within their own month
    with db.connect() as con:
        demo = new_case(con, "Accidente (caso real anonimizado)", "Paciente", "person",
                        "Fractura de meseta tibial izquierda por atropello (julio de 2022). Documentos reales con datos personales tapados.",
                        [("Paciente", "patient", "#0E6A58"), ("Esposa", "spouse", "#3E8FB0")], alianza)
        pet = new_case(con, "Mascota", "Mascota", "pet", "Tratamiento veterinario (mayo de 2024).",
                       [("Paciente", "owner", "#0E6A58")])
        jose = new_case(con, "Accidente de José", LOCAL_CASE.get("subject", "Paciente"), "person",
                        "Fractura de meseta tibial izquierda por accidente de tránsito (2022). Caso completo, solo local.",
                        [(n, r, c) for (n, r), c in zip(LOCAL_CASE.get("members", [["Paciente", "patient"]]), ["#0E6A58", "#3E8FB0", "#B08530"])], alianza) if REAL_DIR.exists() else None
        daniel = new_case(con, "Daniel (sintético)", "Daniel Vargas Suárez", "person",
                          "Caso inventado para medir la precisión de la IA.",
                          [("Daniel", "patient", "#0E6A58"), ("Lucía", "spouse", "#3E8FB0")],
                          ("Seguros Andina S.A.", "1020304050", 12000, 90))
        if fill:
            for kind, it in anonymized_items():
                ingest_item(con, pet if kind == "pet" else demo, it, f"demo/caso-demo/{it['file']}")
            for it in json.loads((SYNTH_DIR / "ground_truth.json").read_text(encoding="utf-8")):
                if not it["file"].startswith("11_"):
                    ingest_item(con, daniel, it, f"demo/caso-sintetico/{it['file']}")
        real = []
        if jose:
            skip = excluded()
            real = [it for it in real_items() if it["file"] not in skip]
            for it in real:
                ingest_item(con, jose, it, f"demo/accidente-jose/{it['file']}")
        for case_id in (demo, pet, jose, daniel):
            if case_id:
                audit.audit_case(con, case_id)
    print(f"Seeded 4 cases ({len(real)} real documents in the local case{', demo cases filled' if fill else ''}) into {config.DB_PATH}")


if __name__ == "__main__":
    seed("--gt" in sys.argv)

"""Write demo/dindo_demo.db: a copy of the local database without the local-only case, for the public deployment.

The public demo then shows exactly what the AMD models extracted (and the call log), not the hand transcription.
Uploaded files are pointed back to the anonymized images in demo/ (matched by content), so no upload folder is needed.

Run:  python tools/exportar_db_demo.py
"""
import hashlib
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dindo.servidor import config  # noqa: E402

OUT = ROOT / "demo" / "dindo_demo.db"


def sha(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def main():
    shutil.copyfile(config.DB_PATH, OUT)
    con = sqlite3.connect(OUT)
    local = [r[0] for r in con.execute("SELECT id FROM cases WHERE title LIKE '%José%' OR id IN "
                                       "(SELECT DISTINCT case_id FROM documents WHERE file_path LIKE '%accidente-jose%')")]
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    for cid in local:
        con.execute("DELETE FROM dose_log WHERE medication_id IN (SELECT id FROM medications WHERE case_id=?)", (cid,))
        for t in tables:
            cols = {r[1] for r in con.execute(f"PRAGMA table_info({t})")}
            if "case_id" in cols:
                con.execute(f"DELETE FROM {t} WHERE case_id=?", (cid,))
        con.execute("DELETE FROM cases WHERE id=?", (cid,))
    # uploads -> the matching anonymized image shipped in demo/
    by_hash = {sha(p): p.relative_to(ROOT).as_posix() for p in (ROOT / "demo").rglob("*")
               if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".pdf") and "accidente-jose" not in p.parts}
    fixed = missing = 0
    for did, fp in con.execute("SELECT id, file_path FROM documents WHERE file_path LIKE 'data%'").fetchall():
        src = ROOT / fp.replace("\\", "/")
        new = by_hash.get(sha(src)) if src.exists() else None
        if new:
            con.execute("UPDATE documents SET file_path=? WHERE id=?", (new, did))
            fixed += 1
        else:
            missing += 1
    con.commit()
    con.execute("VACUUM")
    con.close()
    print(f"removed cases {local}; files re-pointed {fixed}, without image {missing}; {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()

"""Prepare the demo case after the AMD models have read the documents.

1. Pick the demo "today": the day of the case with the most real activity at once (scheduled medications, active
   instructions, events that day and in the next three weeks, expenses), and write it as DINDO_TODAY in .env.
2. Fill the dose history like a family would have: every dose of the previous two weeks and of today's early
   morning is marked as taken, so the doses that are past due and unmarked show up as late.

Run (server stopped or running):  python tools/preparar_demo.py [CASE_ID]
"""
import re
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dindo.servidor import db  # noqa: E402
from dindo.servidor.app import _doses  # noqa: E402

case_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1


def score(con, d: date) -> tuple[int, dict]:
    iso, soon = d.isoformat(), (d + timedelta(days=21)).isoformat()
    meds = len({x["medication_id"] for x in _doses(con, case_id, d)})
    ins = db.rows(con, """SELECT polarity FROM instructions WHERE case_id=? AND (start_date IS NULL OR start_date<=?)
                          AND (until IS NULL OR until>=?)""", case_id, iso, iso)
    avoid = sum(i["polarity"] == "avoid" for i in ins)
    today_ev = db.row(con, "SELECT COUNT(*) n FROM events WHERE case_id=? AND date=?", case_id, iso)["n"]
    soon_ev = db.row(con, "SELECT COUNT(*) n FROM events WHERE case_id=? AND date>? AND date<=?", case_id, iso, soon)["n"]
    spend = db.row(con, "SELECT COUNT(*) n FROM expenses WHERE case_id=? AND date=?", case_id, iso)["n"]
    detail = {"meds": meds, "instructions": len(ins), "avoid": avoid, "events_today": today_ev, "events_soon": soon_ev, "expenses": spend}
    return 6 * meds + 2 * len(ins) + 3 * avoid + 2 * today_ev + min(soon_ev, 6) + 2 * min(spend, 2), detail


DEMO_TIME = "15:10"


def main():
    con = db.connect()
    first = db.row(con, "SELECT MIN(date) d FROM (SELECT date FROM events WHERE case_id=? UNION SELECT start_date FROM medications WHERE case_id=?)",
                   case_id, case_id)["d"]
    last = db.row(con, "SELECT MAX(date) d FROM (SELECT date FROM events WHERE case_id=? UNION SELECT start_date FROM medications WHERE case_id=?)",
                  case_id, case_id)["d"]
    if not first:
        sys.exit("No dated records in this case yet.")
    days = [date.fromisoformat(first) + timedelta(days=i) for i in range((date.fromisoformat(last) - date.fromisoformat(first)).days + 1)]
    ranked = sorted(((score(con, d), d) for d in days), key=lambda x: -x[0][0])
    print("Best demo days:")
    for (s, det), d in ranked[:5]:
        print(f"  {d}  score {s}  {det}")
    best = ranked[0][1]

    env = ROOT / ".env"
    text = env.read_text(encoding="utf-8")
    text = re.sub(r"^DINDO_TODAY=.*$", f"DINDO_TODAY={best.isoformat()}", text, flags=re.M) if "DINDO_TODAY=" in text else text + f"\nDINDO_TODAY={best.isoformat()}\n"
    # demo clock mid-afternoon: the morning doses are taken, the 14:00 one shows up as late
    text = re.sub(r"^DINDO_TIME=.*$", f"DINDO_TIME={DEMO_TIME}", text, flags=re.M) if "DINDO_TIME=" in text else text.rstrip("\n") + f"\nDINDO_TIME={DEMO_TIME}\n"
    env.write_text(text, encoding="utf-8")

    marked = 0
    for i in range(14, -1, -1):
        d = best - timedelta(days=i)
        for x in _doses(con, case_id, d):
            if i > 0 or x["time"] < "12:00":
                con.execute("INSERT OR IGNORE INTO dose_log (medication_id, scheduled_at) VALUES (?,?)", (x["medication_id"], x["scheduled_at"]))
                marked += 1
    con.commit()
    print(f"DINDO_TODAY={best} DINDO_TIME={DEMO_TIME} written to .env; {marked} past doses marked as taken. Restart the server.")


if __name__ == "__main__":
    main()

"""Settings read from the environment (.env at the project root)."""
import contextvars
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATA_DIR = Path(os.getenv("DINDO_DATA_DIR", ROOT / "data"))
DB_PATH = DATA_DIR / "dindo.db"
UPLOAD_DIR = DATA_DIR / "uploads"
WEB_DIR = ROOT / "dindo" / "web"
DEMO_DIR = ROOT / "demo"

# AMD Token Factory (OpenAI-compatible API served on AMD GPUs)
AMD_API_BASE_URL = os.getenv("AMD_API_BASE_URL", "")
AMD_API_KEY = os.getenv("AMD_API_KEY", "")
AMD_VISION_MODEL = os.getenv("AMD_VISION_MODEL", "")
AMD_TEXT_MODEL = os.getenv("AMD_TEXT_MODEL", "")
# Used when the main vision model is unavailable on the shared endpoint
AMD_VISION_FALLBACK = os.getenv("AMD_VISION_FALLBACK", "Qwen3.8-Flash-Next")

# Replaying a past case (the demo case is from 2022): pin "today" and the clock (e.g. "15:10") for demo cases.
# Cases the family creates run on the real date and time.
_today = os.getenv("DINDO_TODAY", "").strip()
_time = os.getenv("DINDO_TIME", "").strip()
# The family's time zone (the server may run in UTC); Bolivia is UTC-4
LOCAL_TZ = timezone(timedelta(hours=float(os.getenv("DINDO_UTC_OFFSET", "-4"))))
_replay = contextvars.ContextVar("replay", default=True)


def replaying(on: bool):
    """Set for the current request whether its case is a replayed demo case. Returns a token for reset_replay."""
    return _replay.set(on)


def reset_replay(token) -> None:
    _replay.reset(token)


def _now() -> datetime:
    return datetime.now(LOCAL_TZ)


def today(replay: bool | None = None) -> date:
    on = _replay.get() if replay is None else replay
    return date.fromisoformat(_today) if (_today and on) else _now().date()


def now_hm(replay: bool | None = None) -> str:
    on = _replay.get() if replay is None else replay
    return _time if (_time and on) else _now().strftime("%H:%M")

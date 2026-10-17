"""Settings read from the environment (.env at the project root)."""
import os
from datetime import date, datetime
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

# Replaying a past case (the demo case is from 2022): pin "today" to a date.
_today = os.getenv("DINDO_TODAY", "").strip()


def today() -> date:
    return date.fromisoformat(_today) if _today else date.today()


# Optional fixed clock for the demo (e.g. "15:10"), so the recorded day always looks the same.
_time = os.getenv("DINDO_TIME", "").strip()


def now_hm() -> str:
    return _time or datetime.now().strftime("%H:%M")

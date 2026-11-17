import os
from pathlib import Path


def _load_dotenv() -> None:
    """Мінімальний читач .env (без зовнішніх залежностей)."""
    path = Path(__file__).resolve().parent.parent / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.1-flash-lite")
DATABASE_URL = os.getenv("DATABASE_URL", "") or "sqlite:///weather.db"
WEATHER_CACHE_TTL = int(os.getenv("WEATHER_CACHE_TTL", "600"))  # секунд
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "15"))

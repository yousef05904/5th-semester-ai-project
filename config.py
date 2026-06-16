from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Create a .env file from .env.example and set it."
        )
    return value


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {name} must be an integer.") from exc


def _resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


OPENAI_API_KEY = _require_env("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
MAX_RESULTS_PER_QUERY = _get_int("MAX_RESULTS_PER_QUERY", 5)
MAX_ARTICLE_CHARS = _get_int("MAX_ARTICLE_CHARS", 12000)
OUTPUT_DIR = _resolve_path(os.getenv("OUTPUT_DIR", "outputs"))

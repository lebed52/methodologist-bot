from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    polza_ai_api_key: str
    polza_ai_base_url: str
    polza_ai_model: str
    memory_dir: Path
    skills_dir: Path
    database_path: Path
    max_history_messages: int
    max_context_chars: int
    allowed_user_ids: frozenset[int]
    required_channel: str
    required_channel_url: str


def _parse_user_ids(raw: str) -> frozenset[int]:
    if not raw.strip():
        return frozenset()
    try:
        return frozenset(
            int(value.strip()) for value in raw.split(",") if value.strip()
        )
    except ValueError as error:
        message = "ALLOWED_USER_IDS должен содержать Telegram ID через запятую"
        raise ValueError(message) from error


def load_settings() -> Settings:
    load_dotenv(ROOT_DIR / ".env")

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    api_key = os.getenv("POLZA_AI_API_KEY", "").strip()
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не задан")
    if not api_key:
        raise ValueError("POLZA_AI_API_KEY не задан")

    return Settings(
        telegram_bot_token=token,
        polza_ai_api_key=api_key,
        polza_ai_base_url=os.getenv(
            "POLZA_AI_BASE_URL", "https://api.polza.ai/v1"
        ).rstrip("/"),
        polza_ai_model=os.getenv("POLZA_AI_MODEL", "openai/gpt-5"),
        memory_dir=ROOT_DIR / os.getenv("MEMORY_DIR", "memory"),
        skills_dir=ROOT_DIR / os.getenv("SKILLS_DIR", "skills"),
        database_path=ROOT_DIR / os.getenv("DATABASE_PATH", "data/bot.sqlite3"),
        max_history_messages=max(2, int(os.getenv("MAX_HISTORY_MESSAGES", "12"))),
        max_context_chars=max(4_000, int(os.getenv("MAX_CONTEXT_CHARS", "30000"))),
        allowed_user_ids=_parse_user_ids(os.getenv("ALLOWED_USER_IDS", "")),
        required_channel=os.getenv("REQUIRED_CHANNEL", "@qabigtech").strip(),
        required_channel_url=os.getenv(
            "REQUIRED_CHANNEL_URL", "https://t.me/qabigtech"
        ).strip(),
    )

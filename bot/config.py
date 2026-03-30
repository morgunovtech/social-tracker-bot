from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required env variable: {name}")
    return value


@dataclass(frozen=True)
class Config:
    # Telegram
    bot_token: str
    admin_chat_id: int
    telegram_channel_id: str

    # YouTube
    youtube_api_key: str
    youtube_channel_id: str

    # LinkedIn (RapidAPI)
    rapidapi_key: str | None
    linkedin_profile_url: str | None

    # Schedule (UTC)
    report_hour_utc: int
    report_minute: int

    # Database
    db_path: str

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            bot_token=_require("BOT_TOKEN"),
            admin_chat_id=int(_require("ADMIN_CHAT_ID")),
            telegram_channel_id=_require("TELEGRAM_CHANNEL_ID"),
            youtube_api_key=_require("YOUTUBE_API_KEY"),
            youtube_channel_id=_require("YOUTUBE_CHANNEL_ID"),
            rapidapi_key=os.getenv("RAPIDAPI_KEY"),
            linkedin_profile_url=os.getenv("LINKEDIN_PROFILE_URL"),
            report_hour_utc=int(os.getenv("REPORT_HOUR_UTC", "4")),
            report_minute=int(os.getenv("REPORT_MINUTE", "0")),
            db_path=os.getenv("DB_PATH", "data/followers.db"),
        )

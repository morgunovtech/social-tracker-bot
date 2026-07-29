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

    # LinkedIn
    rapidapi_key: str | None  # RapidAPI fallback
    linkedin_profile_url: str | None
    linkedin_li_at: str | None  # 'li_at' cookie from logged-in browser session
    linkedin_stale_days: int  # mark manual entry as stale after N days

    # Schedule (UTC)
    report_hour_utc: int
    report_minute: int
    report_dow: str  # APScheduler day_of_week expression: 'sat', 'mon,thu', '*', etc.
    quiet_if_no_change: bool

    # Database
    db_path: str

    # Site push — sends finalized counts to about-me-page's ingest endpoint.
    site_ingest_url: str | None
    site_ingest_token: str | None

    # Dead man's switch: pinged after each successful daily collect
    # (e.g. https://hc-ping.com/<uuid> from healthchecks.io).
    healthcheck_url: str | None

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
            linkedin_li_at=os.getenv("LINKEDIN_LI_AT"),
            linkedin_stale_days=int(os.getenv("LINKEDIN_STALE_DAYS", "7")),
            report_hour_utc=int(os.getenv("REPORT_HOUR_UTC", "8")),
            report_minute=int(os.getenv("REPORT_MINUTE", "0")),
            report_dow=os.getenv("REPORT_DOW", "sat").lower(),
            quiet_if_no_change=os.getenv("QUIET_IF_NO_CHANGE", "0") == "1",
            db_path=os.getenv("DB_PATH", "data/followers.db"),
            site_ingest_url=os.getenv(
                "SITE_INGEST_URL", "https://s.morgunov.tech/api/ingest/subscribers"
            ),
            site_ingest_token=os.getenv("SOCIALBOT_INGEST_TOKEN"),
            healthcheck_url=os.getenv("HEALTHCHECK_URL"),
        )

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


DOW_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required env variable: {name}")
    return value


def normalize_dow(value: str) -> str:
    """Validate and normalize a day-of-week expression for APScheduler.

    Accepts: 'daily', '*', 'all', 'sat', 'mon,thu', 'mon-fri'.
    Returns canonical form. Raises ValueError on invalid input.
    """
    v = value.strip().lower()
    if v in ("daily", "*", "all"):
        return "*"

    # Range: mon-fri
    if "-" in v and "," not in v:
        a, _, b = v.partition("-")
        if a.strip() in DOW_ORDER and b.strip() in DOW_ORDER:
            return f"{a.strip()}-{b.strip()}"
        raise ValueError(f"Invalid day range: {value}")

    parts = [p.strip() for p in v.split(",") if p.strip()]
    if not parts or any(p not in DOW_ORDER for p in parts):
        raise ValueError(f"Invalid day-of-week: {value}")
    return ",".join(parts)


def _report_dow() -> str:
    # Fail fast: an unparsed value (e.g. 'daily') would silently never match a report day.
    raw = os.getenv("REPORT_DOW", "sat")
    try:
        return normalize_dow(raw)
    except ValueError as e:
        raise RuntimeError(f"Invalid REPORT_DOW={raw!r}: {e}") from None


@dataclass(frozen=True)
class Config:
    # Telegram bot (required) and the channel to track (optional)
    bot_token: str
    admin_chat_id: int
    telegram_channel_id: str | None

    # YouTube (optional: both values or the platform is off)
    youtube_api_key: str | None
    youtube_channel_id: str | None

    # LinkedIn (optional: off without a profile URL)
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

    # Optional push of finalized counts to your own site (POST JSON, Bearer token).
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
            telegram_channel_id=os.getenv("TELEGRAM_CHANNEL_ID") or None,
            youtube_api_key=os.getenv("YOUTUBE_API_KEY") or None,
            youtube_channel_id=os.getenv("YOUTUBE_CHANNEL_ID") or None,
            linkedin_profile_url=os.getenv("LINKEDIN_PROFILE_URL") or None,
            linkedin_li_at=os.getenv("LINKEDIN_LI_AT"),
            linkedin_stale_days=int(os.getenv("LINKEDIN_STALE_DAYS", "7")),
            report_hour_utc=int(os.getenv("REPORT_HOUR_UTC", "8")),
            report_minute=int(os.getenv("REPORT_MINUTE", "0")),
            report_dow=_report_dow(),
            quiet_if_no_change=os.getenv("QUIET_IF_NO_CHANGE", "0") == "1",
            db_path=os.getenv("DB_PATH", "data/followers.db"),
            site_ingest_url=os.getenv("SITE_INGEST_URL") or None,
            site_ingest_token=os.getenv("SOCIALBOT_INGEST_TOKEN"),
            healthcheck_url=os.getenv("HEALTHCHECK_URL"),
        )

    @property
    def enabled_platforms(self) -> list[str]:
        """Platforms configured well enough to collect, in report order."""
        configured = {
            "telegram": bool(self.telegram_channel_id),
            "youtube": bool(self.youtube_api_key and self.youtube_channel_id),
            "linkedin": bool(self.linkedin_profile_url),
        }
        return [platform for platform, on in configured.items() if on]

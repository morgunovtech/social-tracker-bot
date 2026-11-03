from __future__ import annotations

import functools
import os
import re
from dataclasses import dataclass
from zoneinfo import available_timezones

from dotenv import load_dotenv

from bot import platforms

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


@functools.cache
def _zones() -> dict[str, str]:
    return {name.lower(): name for name in available_timezones()}


def normalize_tz(value: str) -> str:
    """The canonical IANA name of a time zone: 'europe/moscow' -> 'Europe/Moscow'.

    Raises ValueError for a name the tz database doesn't have.
    """
    name = _zones().get(value.strip().lower())
    if name is None:
        raise ValueError(f"Unknown time zone: {value}")
    return name


def _url(name: str) -> str | None:
    """The first http(s) URL in the variable. Tolerates a whole pasted line
    such as `&& curl -fsS https://…`, the way TofsDevOps shows a heartbeat."""
    match = re.search(r"https?://[^\s'\"]+", os.getenv(name) or "")
    return match.group(0) if match else None


def _report_dow() -> str:
    # Fail fast: an unparsed value (e.g. 'daily') would silently never match a report day.
    raw = os.getenv("REPORT_DOW", "sat")
    try:
        return normalize_dow(raw)
    except ValueError as e:
        raise RuntimeError(f"Invalid REPORT_DOW={raw!r}: {e}") from None


def _report_tz() -> str:
    raw = os.getenv("REPORT_TZ") or "UTC"
    try:
        return normalize_tz(raw)
    except ValueError as e:
        raise RuntimeError(f"Invalid REPORT_TZ={raw!r}: {e}") from None


def _repo_slug() -> str | None:
    slug = os.getenv("GITHUB_REPOSITORY", "").strip()
    if not slug:
        owner = os.getenv("RAILWAY_GIT_REPO_OWNER", "").strip()
        name = os.getenv("RAILWAY_GIT_REPO_NAME", "").strip()
        slug = f"{owner}/{name}" if owner and name else ""
    return slug or None


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

    # Schedule: the time and the day(s) are in report_tz
    report_hour: int
    report_minute: int
    report_dow: str  # APScheduler day_of_week expression: 'sat', 'mon,thu', '*', etc.
    report_tz: str  # IANA name: 'UTC', 'Europe/Moscow'
    quiet_if_no_change: bool

    # Database
    db_path: str

    # Optional push of finalized counts to your own site (POST JSON, Bearer token).
    site_ingest_url: str | None
    site_ingest_token: str | None

    # Dead man's switch: pinged after each successful daily collect
    # (e.g. https://hc-ping.com/<uuid> from healthchecks.io).
    healthcheck_url: str | None

    # Update awareness (bot/updates.py). Railway provides the commit and the
    # repository by itself; elsewhere pass APP_COMMIT and GITHUB_REPOSITORY.
    app_commit: str
    repo_slug: str | None  # owner/name on GitHub
    github_token: str | None  # optional: only lifts GitHub's rate limit
    update_watch: bool
    # Security emails: the mail-worker that receives forwarded security
    # notifications (see mail-worker/README.md) and its bearer token.
    security_mail_url: str | None
    security_mail_token: str | None

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
            # REPORT_HOUR_UTC is its name from before the zone setting.
            report_hour=int(os.getenv("REPORT_HOUR") or os.getenv("REPORT_HOUR_UTC") or "8"),
            report_minute=int(os.getenv("REPORT_MINUTE", "0")),
            report_dow=_report_dow(),
            report_tz=_report_tz(),
            quiet_if_no_change=os.getenv("QUIET_IF_NO_CHANGE", "0") == "1",
            db_path=os.getenv("DB_PATH", "data/followers.db"),
            site_ingest_url=os.getenv("SITE_INGEST_URL") or None,
            site_ingest_token=os.getenv("SOCIALBOT_INGEST_TOKEN"),
            healthcheck_url=_url("HEALTHCHECK_URL"),
            app_commit=(os.getenv("APP_COMMIT") or os.getenv("RAILWAY_GIT_COMMIT_SHA") or "").strip()[:12],
            repo_slug=_repo_slug(),
            github_token=os.getenv("GITHUB_TOKEN") or None,
            update_watch=os.getenv("UPDATE_WATCH", "1") == "1",
            security_mail_url=(os.getenv("SECURITY_MAIL_URL") or "").rstrip("/") or None,
            security_mail_token=os.getenv("SECURITY_MAIL_TOKEN") or None,
        )

    @property
    def enabled_platforms(self) -> list[str]:
        """Ids of the platforms configured well enough to collect, in report order."""
        return [p.id for p in platforms.enabled(self)]

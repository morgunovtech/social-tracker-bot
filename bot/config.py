from __future__ import annotations

import functools
import os
import re
from dataclasses import dataclass
from zoneinfo import available_timezones

from dotenv import load_dotenv

from bot import platforms
from bot.classifier import DEFAULT_MODEL as DEFAULT_COMMENTS_MODEL
from bot.i18n import LANGUAGES

load_dotenv()


DOW_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
# Comment checks per day unless COMMENTS_DAILY_LIMIT says otherwise (0 = no limit):
# a spam wave must not turn into an unbounded API bill. The model itself is
# classifier.DEFAULT_MODEL, re-exported here as DEFAULT_COMMENTS_MODEL.
DEFAULT_COMMENTS_DAILY_LIMIT = 300
# The zone of the schedule when neither the chat nor TIMEZONE set one: it
# follows the chat language (BOT_PRINCIPLES §5).
DEFAULT_TZ = {"ru": "Europe/Moscow", "en": "UTC"}


# What @BotFather gives: the bot's id, a colon and the secret. The value is
# never repeated in an error — it may be a real token with a typo in it.
_TOKEN_SHAPE = re.compile(r"^\d+:\S+$")


def _bot_token() -> str:
    """BOT_TOKEN, or a stop with what to do: the placeholder copied from
    .env.example used to end in a python-telegram-bot traceback."""
    raw = (os.getenv("BOT_TOKEN") or "").strip()
    if not raw:
        raise RuntimeError("Missing required env variable: BOT_TOKEN — the token @BotFather gave you, «123456:ABC…»")
    if not _TOKEN_SHAPE.match(raw):
        raise RuntimeError(
            "BOT_TOKEN is not a bot token yet (still the placeholder from .env.example?): "
            "paste the one @BotFather gave you, «123456:ABC…», into .env or the Railway variables"
        )
    return raw


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


def _int(name: str, default: int, lo: int, hi: int, *, legacy: str | None = None) -> int:
    """A whole number from lo to hi; an empty variable means the default
    (every optional variable in .env.example is left empty, this one too).
    legacy is an older name of the same variable, read when the current one
    is empty. A value out of range stops the bot now, with its name, not
    later with a traceback from the scheduler."""
    raw = (os.getenv(name) or "").strip()
    if not raw and legacy:
        raw = (os.getenv(legacy) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise RuntimeError(f"Invalid {name}={raw!r}: a whole number from {lo} to {hi}") from None
    if not lo <= value <= hi:
        raise RuntimeError(f"Invalid {name}={raw!r}: a whole number from {lo} to {hi}")
    return value


def first_url(text: str) -> str | None:
    """The first http(s) URL in a text. Tolerates a whole pasted line such as
    `&& curl -fsS https://…`, the way TofsDevOps shows a heartbeat."""
    match = re.search(r"https?://[^\s'\"]+", text or "")
    return match.group(0) if match else None


def _url(name: str) -> str | None:
    return first_url(os.getenv(name) or "")


def _report_dow() -> str:
    # Fail fast: an unparsed value (e.g. 'daily') would silently never match a report day.
    raw = os.getenv("REPORT_DOW", "sat")
    try:
        return normalize_dow(raw)
    except ValueError as e:
        raise RuntimeError(f"Invalid REPORT_DOW={raw!r}: {e}") from None


def _report_tz(lang: str) -> str:
    """TIMEZONE, or REPORT_TZ — its name before 1.5.0, read when TIMEZONE is
    empty; with neither, the zone of the chat language (DEFAULT_TZ)."""
    name = "TIMEZONE" if (os.getenv("TIMEZONE") or "").strip() else "REPORT_TZ"
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return DEFAULT_TZ[lang]
    try:
        return normalize_tz(raw)
    except ValueError as e:
        raise RuntimeError(f"Invalid {name}={raw!r}: {e}") from None


def _lang() -> str:
    raw = (os.getenv("BOT_LANG") or "ru").strip().lower()
    if raw not in LANGUAGES:
        raise RuntimeError(f"Invalid BOT_LANG={raw!r}: use one of {', '.join(LANGUAGES)}")
    return raw


def _repo_slug() -> str | None:
    slug = os.getenv("GITHUB_REPOSITORY", "").strip()
    if not slug:
        owner = os.getenv("RAILWAY_GIT_REPO_OWNER", "").strip()
        name = os.getenv("RAILWAY_GIT_REPO_NAME", "").strip()
        slug = f"{owner}/{name}" if owner and name else ""
    return slug or None


def _chat_id(name: str) -> int | None:
    """An optional numeric chat id; empty means «not set»."""
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        raise RuntimeError(f"Invalid {name}={raw!r}: a Telegram chat id is a number such as -1001234567890") from None


def _admin_chat_id() -> int | None:
    """ADMIN_CHAT_ID is optional: empty means «the first /start is the owner»."""
    raw = (os.getenv("ADMIN_CHAT_ID") or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        raise RuntimeError(f"Invalid ADMIN_CHAT_ID={raw!r}: a Telegram user id is a number") from None


@dataclass(frozen=True)
class Config:
    # Telegram bot (required) and the channel to track (optional)
    bot_token: str
    # The owner. None until the first /start claims the bot (then it is kept in
    # the DB); ADMIN_CHAT_ID in the environment pins the owner and wins over
    # the DB. The one field that changes after start — see set_owner().
    admin_chat_id: int | None
    telegram_channel_id: str | None

    # YouTube (optional: both values or the platform is off)
    youtube_api_key: str | None
    youtube_channel_id: str | None

    # Instagram (optional: off without a username). The access token comes
    # from /igtoken (stored in the DB) or from env.
    instagram_username: str | None
    instagram_access_token: str | None

    # LinkedIn (optional: off without a profile URL)
    linkedin_profile_url: str | None
    linkedin_li_at: str | None  # 'li_at' cookie from logged-in browser session
    linkedin_stale_days: int  # mark manual entry as stale after N days

    # Schedule: the time and the day(s) are in report_tz
    report_hour: int
    report_minute: int
    report_dow: str  # APScheduler day_of_week expression: 'sat', 'mon,thu', '*', etc.
    report_tz: str  # IANA name: 'UTC', 'Europe/Moscow'; TIMEZONE (REPORT_TZ), else by the language
    quiet_if_no_change: bool

    # Chat language: ru (default) or en. Reports, screens, alerts and the / menu.
    # BOT_LANG is the starting value: the language chosen in the chat — or taken
    # from the owner's Telegram at the first /start when BOT_LANG is empty —
    # is kept in the database and wins (handlers.restore_language).
    lang: str

    # Database
    db_path: str

    # Optional push of finalized counts to your own site (POST JSON, Bearer token).
    site_ingest_url: str | None
    site_ingest_token: str | None

    # Dead man's switch: pinged after each successful daily collect
    # (e.g. https://hc-ping.com/<uuid> from healthchecks.io). The fallback:
    # an address set in the chat wins (bot/watchdog.py).
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
    # Comments of the channel (bot/monitors/comments.py): the Claude API key
    # that classifies them and the model; off without the key. The discussion
    # group is found through the channel (linked_chat_id) unless COMMENTS_CHAT_ID
    # names one.
    anthropic_api_key: str | None
    comments_model: str
    comments_chat_id: int | None
    comments_daily_limit: int  # checks per UTC day, 0 = no limit
    # Security emails from a separate mailbox over IMAP (bot/mailbox.py): set
    # in the chat only (🔌 Подключения → ✉️ Письма безопасности) and laid
    # over the config by bot/connections.py; the password is an app password.
    mailbox_address: str | None = None
    mailbox_password: str | None = None

    @classmethod
    def from_env(cls) -> Config:
        lang = _lang()
        return cls(
            bot_token=_bot_token(),
            admin_chat_id=_admin_chat_id(),
            telegram_channel_id=os.getenv("TELEGRAM_CHANNEL_ID") or None,
            youtube_api_key=os.getenv("YOUTUBE_API_KEY") or None,
            youtube_channel_id=os.getenv("YOUTUBE_CHANNEL_ID") or None,
            instagram_username=(os.getenv("INSTAGRAM_USERNAME") or "").strip().lstrip("@") or None,
            instagram_access_token=os.getenv("INSTAGRAM_ACCESS_TOKEN") or None,
            linkedin_profile_url=os.getenv("LINKEDIN_PROFILE_URL") or None,
            linkedin_li_at=(os.getenv("LINKEDIN_LI_AT") or "").strip() or None,
            linkedin_stale_days=_int("LINKEDIN_STALE_DAYS", 7, 1, 3650),
            # REPORT_HOUR_UTC is its name from before the zone setting.
            report_hour=_int("REPORT_HOUR", 8, 0, 23, legacy="REPORT_HOUR_UTC"),
            report_minute=_int("REPORT_MINUTE", 0, 0, 59),
            report_dow=_report_dow(),
            report_tz=_report_tz(lang),
            quiet_if_no_change=os.getenv("QUIET_IF_NO_CHANGE", "0") == "1",
            lang=lang,
            db_path=os.getenv("DB_PATH", "data/followers.db"),
            site_ingest_url=os.getenv("SITE_INGEST_URL") or None,
            site_ingest_token=(os.getenv("SOCIALBOT_INGEST_TOKEN") or "").strip() or None,
            healthcheck_url=_url("HEALTHCHECK_URL"),
            app_commit=(os.getenv("APP_COMMIT") or os.getenv("RAILWAY_GIT_COMMIT_SHA") or "").strip()[:12],
            repo_slug=_repo_slug(),
            github_token=os.getenv("GITHUB_TOKEN") or None,
            update_watch=os.getenv("UPDATE_WATCH", "1") == "1",
            security_mail_url=(os.getenv("SECURITY_MAIL_URL") or "").rstrip("/") or None,
            security_mail_token=os.getenv("SECURITY_MAIL_TOKEN") or None,
            anthropic_api_key=(os.getenv("ANTHROPIC_API_KEY") or "").strip() or None,
            comments_model=(os.getenv("COMMENTS_MODEL") or "").strip() or DEFAULT_COMMENTS_MODEL,
            comments_chat_id=_chat_id("COMMENTS_CHAT_ID"),
            comments_daily_limit=_int("COMMENTS_DAILY_LIMIT", DEFAULT_COMMENTS_DAILY_LIMIT, 0, 100_000),
        )

    def set_lang(self, lang: str) -> None:
        """The chat language chosen at runtime (the second exception to the
        frozen dataclass, next to set_owner)."""
        object.__setattr__(self, "lang", lang)

    def set_owner(self, user_id: int) -> None:
        """The owner learnt at runtime: the first /start, or the DB at startup.
        The dataclass is frozen so nothing changes under the bot's feet; this
        one field is the exception, and it only ever goes from None to an id."""
        object.__setattr__(self, "admin_chat_id", user_id)

    @property
    def enabled_platforms(self) -> list[str]:
        """Ids of the platforms configured well enough to collect, in report order."""
        return [p.id for p in platforms.enabled(self)]

from __future__ import annotations

import logging
from datetime import datetime

import aiohttp
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot

UTC = pytz.utc

# Warn user when cookie has been in use longer than this (LinkedIn lifetime ~12 months)
COOKIE_AGING_DAYS = 330

from bot.collectors.linkedin import collect_linkedin
from bot.collectors.telegram import collect_telegram
from bot.collectors.youtube import collect_youtube
from bot.config import Config
from bot.db import Database
from bot.reporter import build_report

logger = logging.getLogger(__name__)

VALID_DOW = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
_DOW_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _today_matches_dow(dow_expr: str, now_utc: datetime | None = None) -> bool:
    """Return True if today (UTC) matches the cron day-of-week expression."""
    if dow_expr == "*":
        return True
    today_idx = (now_utc or datetime.utcnow()).weekday()  # 0=Mon..6=Sun
    today_short = _DOW_ORDER[today_idx]

    if "-" in dow_expr and "," not in dow_expr:
        a, _, b = dow_expr.partition("-")
        try:
            a_idx = _DOW_ORDER.index(a.strip())
            b_idx = _DOW_ORDER.index(b.strip())
        except ValueError:
            return False
        if a_idx <= b_idx:
            return a_idx <= today_idx <= b_idx
        # Wrap-around (e.g. fri-mon)
        return today_idx >= a_idx or today_idx <= b_idx

    days = {d.strip() for d in dow_expr.split(",")}
    return today_short in days


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
        if a.strip() in VALID_DOW and b.strip() in VALID_DOW:
            return f"{a.strip()}-{b.strip()}"
        raise ValueError(f"Invalid day range: {value}")

    parts = [p.strip() for p in v.split(",") if p.strip()]
    if not parts or any(p not in VALID_DOW for p in parts):
        raise ValueError(f"Invalid day-of-week: {value}")
    return ",".join(parts)


async def get_active_cookie(db: Database, config: Config) -> str | None:
    """Cookie precedence: DB (set via /setcookie) > env (LINKEDIN_LI_AT)."""
    return (await db.get_setting("linkedin_li_at")) or config.linkedin_li_at


async def get_cookie_age_days(db: Database) -> int | None:
    """Days since the active cookie was set via /setcookie (None if from env or unset)."""
    set_at = await db.get_setting("linkedin_li_at_set_at")
    if not set_at:
        return None
    try:
        return (datetime.utcnow() - datetime.fromisoformat(set_at)).days
    except (ValueError, TypeError):
        return None


async def collect_and_report(
    bot: Bot, config: Config, db: Database, force_linkedin: bool = True
) -> tuple[str, bool]:
    """Collect from all sources, persist, and build a report.

    Returns (report_text, has_meaningful_change).
    LinkedIn is collected by default; pass force_linkedin=False to skip.
    """
    errors: dict[str, bool | int] = {}

    async with aiohttp.ClientSession() as session:
        tg_count = await collect_telegram(bot, config.telegram_channel_id)
        if tg_count is not None:
            await db.upsert("telegram", tg_count)
        else:
            errors["telegram"] = True

        yt_count = await collect_youtube(session, config.youtube_api_key, config.youtube_channel_id)
        if yt_count is not None:
            await db.upsert("youtube", yt_count)
        else:
            errors["youtube"] = True

        if force_linkedin:
            li_at = await get_active_cookie(db, config)
            li_count, li_source = await collect_linkedin(
                session,
                config.rapidapi_key,
                config.linkedin_profile_url,
                li_at=li_at,
            )
            if li_count is not None and li_source is not None:
                await db.upsert("linkedin", li_count, source=li_source)
            elif li_source == "cookie_expired":
                errors["linkedin_cookie_expired"] = True
            elif (li_at or config.rapidapi_key) and config.linkedin_profile_url:
                errors["linkedin"] = True

            # Proactive aging warning (only meaningful when cookie was set via /setcookie)
            age = await get_cookie_age_days(db)
            if age is not None and age >= COOKIE_AGING_DAYS:
                errors["linkedin_cookie_aging"] = age

        # Push finalized counts to the website (reuses the open session).
        await _push_subscribers(session, config, db)

    return await build_report(db, errors=errors, linkedin_stale_days=config.linkedin_stale_days)


async def _push_subscribers(
    session: aiohttp.ClientSession, config: Config, db: Database
) -> None:
    """Push finalized subscriber counts to the website's ingest endpoint.

    Fire-and-forget: any failure is logged, never raised, so the report flow is
    unaffected. Reads the authoritative latest count per platform from the DB,
    so a transient collection miss on one platform still pushes the last good
    numbers. Skips entirely until all three platforms have data.
    """
    if not config.site_ingest_url or not config.site_ingest_token:
        return

    counts: dict[str, int] = {}
    for platform in ("telegram", "youtube", "linkedin"):
        latest = await db.get_latest(platform)
        if latest is not None:
            counts[platform] = latest["count"]

    if len(counts) < 3:
        logger.info("Site push skipped — not all platforms have data yet: %s", sorted(counts))
        return

    payload = {**counts, "updatedAt": datetime.utcnow().isoformat() + "Z"}
    try:
        async with session.post(
            config.site_ingest_url,
            json=payload,
            headers={"Authorization": f"Bearer {config.site_ingest_token}"},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status == 200:
                logger.info("Pushed subscriber counts to site: %s", counts)
            else:
                body = (await resp.text())[:200]
                logger.warning("Site push failed: HTTP %s — %s", resp.status, body)
    except Exception:
        logger.exception("Site push errored")


async def _scheduled_job(bot: Bot, config: Config, db: Database) -> None:
    """Daily collect; push report only on configured report day(s)."""
    try:
        report, has_change = await collect_and_report(bot, config, db, force_linkedin=True)
    except Exception:
        logger.exception("Scheduled collection failed")
        return

    dow = await db.get_setting("report_dow") or config.report_dow
    if not _today_matches_dow(dow):
        logger.info("Today is not a report day (dow=%s) — collected, no push", dow)
        return

    quiet = await is_quiet_mode(db, config)
    if quiet and not has_change:
        logger.info("Quiet mode: no changes detected, skipping push")
        return

    try:
        await bot.send_message(chat_id=config.admin_chat_id, text=report)
        logger.info("Scheduled report sent to admin")
    except Exception:
        logger.exception("Scheduled report send failed")


async def get_report_schedule(db: Database, config: Config) -> tuple[str, int, int]:
    """Return (day_of_week, hour, minute), preferring DB over config."""
    dow = await db.get_setting("report_dow") or config.report_dow
    stored_time = await db.get_setting("report_time")
    if stored_time:
        try:
            h, m = stored_time.split(":")
            return dow, int(h), int(m)
        except (ValueError, AttributeError):
            pass
    return dow, config.report_hour_utc, config.report_minute


async def is_quiet_mode(db: Database, config: Config) -> bool:
    stored = await db.get_setting("quiet_if_no_change")
    if stored is not None:
        return stored == "1"
    return config.quiet_if_no_change


def reschedule(
    scheduler: AsyncIOScheduler,
    dow: str,
    hour: int,
    minute: int,
) -> None:
    """Update the run time. Job fires daily; dow filter is applied inside the job
    so we always have daily data for trends, but push only on report day(s).
    """
    scheduler.reschedule_job(
        "scheduled_report",
        trigger=CronTrigger(hour=hour, minute=minute, timezone=UTC),
    )
    logger.info("Rescheduled daily collect to %02d:%02d UTC (push dow=%s)", hour, minute, dow)


async def setup_scheduler(bot: Bot, config: Config, db: Database) -> AsyncIOScheduler:
    dow, hour, minute = await get_report_schedule(db, config)
    scheduler = AsyncIOScheduler(timezone=UTC)
    scheduler.add_job(
        _scheduled_job,
        trigger=CronTrigger(hour=hour, minute=minute, timezone=UTC),
        args=[bot, config, db],
        id="scheduled_report",
        replace_existing=True,
    )
    logger.info("Scheduler started: daily collect at %02d:%02d UTC, push on %s", hour, minute, dow)
    return scheduler

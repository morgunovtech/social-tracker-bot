from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import aiohttp
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from telegram import Bot

UTC = pytz.utc

# Warn user when cookie has been in use longer than this (LinkedIn lifetime ~12 months)
COOKIE_AGING_DAYS = 330

# A same-day drop is alert-worthy when it exceeds either bound.
DROP_ALERT_MIN_ABS = 20
DROP_ALERT_MIN_PCT = 1.0

# Failed platforms are re-collected up to this many times, an hour apart.
COLLECT_MAX_ATTEMPTS = 3
COLLECT_RETRY_DELAY = timedelta(hours=1)

from bot.chart import render_chart
from bot.collectors.linkedin import collect_linkedin, plausible_count
from bot.collectors.telegram import collect_telegram
from bot.collectors.youtube import collect_youtube
from bot.config import Config
from bot.db import Database, parse_utc, utcnow
from bot.reporter import (
    PLATFORM_LABELS,
    PLATFORMS,
    _crossed_milestone,
    _fmt,
    build_month_report,
    build_report,
)

logger = logging.getLogger(__name__)


@dataclass
class CollectOutcome:
    """Result of one collection pass, including alert-worthy events."""

    report: str
    has_change: bool
    errors: dict[str, bool | int] = field(default_factory=dict)
    collected: dict[str, tuple[int, str]] = field(default_factory=dict)  # platform -> (count, source)
    drops: dict[str, tuple[int, int]] = field(default_factory=dict)  # platform -> (prev, new)
    milestones: list[tuple[str, int]] = field(default_factory=list)  # (platform, milestone)

VALID_DOW = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
_DOW_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _today_matches_dow(dow_expr: str, now_utc: datetime | None = None) -> bool:
    """Return True if today (UTC) matches the cron day-of-week expression."""
    if dow_expr == "*":
        return True
    today_idx = (now_utc or utcnow()).weekday()  # 0=Mon..6=Sun
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
        return (utcnow() - parse_utc(set_at)).days
    except (ValueError, TypeError):
        return None


async def collect_and_report(
    bot: Bot, config: Config, db: Database, force_linkedin: bool = True
) -> CollectOutcome:
    """Collect from all sources, persist, and build a report.

    LinkedIn is collected by default; pass force_linkedin=False to skip.
    Alert-worthy events (drops, milestones, failures) are recorded on the
    returned CollectOutcome; deciding whether to notify is the caller's job.
    """
    outcome = CollectOutcome(report="", has_change=False)
    errors = outcome.errors

    async def record(platform: str, count: int, source: str = "api") -> None:
        """Persist a count and detect drops / milestone crossings vs the stored value."""
        prev_row = await db.get_latest(platform)
        prev = prev_row["count"] if prev_row else None
        await db.upsert(platform, count, source=source)
        outcome.collected[platform] = (count, source)
        if prev is None:
            return
        drop = prev - count
        if drop > 0 and (
            drop >= DROP_ALERT_MIN_ABS or (prev > 0 and drop / prev * 100 >= DROP_ALERT_MIN_PCT)
        ):
            outcome.drops[platform] = (prev, count)
        milestone = _crossed_milestone(prev, count)
        if milestone is not None:
            outcome.milestones.append((platform, milestone))

    async with aiohttp.ClientSession() as session:
        tg_count = await collect_telegram(bot, config.telegram_channel_id)
        if tg_count is not None:
            await record("telegram", tg_count)
        else:
            errors["telegram"] = True

        yt_count = await collect_youtube(session, config.youtube_api_key, config.youtube_channel_id)
        if yt_count is not None:
            await record("youtube", yt_count)
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
                prev = await db.get_latest("linkedin")
                prev_count = prev["count"] if prev else None
                if plausible_count(prev_count, li_count):
                    await record("linkedin", li_count, source=li_source)
                else:
                    logger.warning(
                        "LinkedIn count %d rejected as implausible (previous: %s) — "
                        "likely parsed someone else's counter; reset baseline via /linkedin <N>",
                        li_count,
                        prev_count,
                    )
                    errors["linkedin"] = True
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

    outcome.report, outcome.has_change = await build_report(
        db, errors=errors, linkedin_stale_days=config.linkedin_stale_days
    )
    return outcome


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

    payload = {**counts, "updatedAt": utcnow().isoformat().replace("+00:00", "Z")}
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


async def _build_alerts(db: Database, outcome: CollectOutcome) -> list[str]:
    """Turn the collection outcome into proactive alert lines, with dedup state in settings.

    - cookie expiry: alerted once until the cookie works again;
    - failure streaks: alerted at 2 consecutive days, then weekly while broken;
    - drops and milestones: naturally deduped (the stored value moves past them).
    """
    today_iso = utcnow().date().isoformat()
    lines: list[str] = []

    if outcome.errors.get("linkedin_cookie_expired"):
        if await db.get_setting("cookie_expired_alerted") != "1":
            await db.set_setting("cookie_expired_alerted", "1")
            lines.append("🔴 LinkedIn cookie истёк или отклонён — обнови через /setcookie")
    elif outcome.collected.get("linkedin", (None, None))[1] == "cookie":
        await db.set_setting("cookie_expired_alerted", "0")

    for platform in PLATFORMS:
        label = PLATFORM_LABELS[platform]
        if outcome.errors.get(platform):
            # Count at most one failure per day, so same-day retries don't inflate the streak.
            if await db.get_setting(f"fail_last_date_{platform}") != today_iso:
                streak = int(await db.get_setting(f"fail_streak_{platform}") or "0") + 1
                await db.set_setting(f"fail_streak_{platform}", str(streak))
                await db.set_setting(f"fail_last_date_{platform}", today_iso)
                if streak == 2 or (streak > 2 and streak % 7 == 0):
                    lines.append(f"🔴 {label}: не удаётся собрать данные {streak} дн. подряд")
        elif platform in outcome.collected:
            await db.set_setting(f"fail_streak_{platform}", "0")

    for platform, (prev, new) in outcome.drops.items():
        label = PLATFORM_LABELS[platform]
        lines.append(f"🟠 {label}: −{_fmt(prev - new)} подписчиков за день ({_fmt(prev)} → {_fmt(new)})")

    for platform, milestone in outcome.milestones:
        label = PLATFORM_LABELS[platform]
        lines.append(f"🎯 {label} перешагнул {_fmt(milestone)}!")

    return lines


async def _build_chart_png(db: Database, days: int = 30) -> bytes | None:
    series: dict[str, list[tuple[datetime, int]]] = {}
    for platform in PLATFORMS:
        rows = await db.get_history(platform, days)
        points = []
        for row in rows:
            try:
                points.append((parse_utc(row["collected_at"]), row["count"]))
            except (ValueError, TypeError):
                continue
        series[PLATFORM_LABELS[platform]] = points
    # Rendering is sync CPU work — keep the event loop free.
    return await asyncio.to_thread(render_chart, series)


async def _send_backup(bot: Bot, config: Config) -> None:
    """Weekly DB backup straight into the admin chat — free offsite storage."""
    try:
        with open(config.db_path, "rb") as f:
            data = f.read()
        today = utcnow().date().isoformat()
        await bot.send_document(
            chat_id=config.admin_chat_id,
            document=data,
            filename=f"followers-{today}.db",
            caption="📦 Еженедельный бэкап БД",
        )
        logger.info("DB backup sent (%d bytes)", len(data))
    except Exception:
        logger.exception("DB backup failed")


async def _ping_healthcheck(config: Config) -> None:
    """Dead man's switch: no ping today → healthchecks.io notifies the admin."""
    if not config.healthcheck_url:
        return
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                config.healthcheck_url, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                logger.info("Healthcheck ping: HTTP %s", resp.status)
    except Exception:
        logger.warning("Healthcheck ping failed", exc_info=True)


async def _scheduled_job(
    bot: Bot, config: Config, db: Database, scheduler: AsyncIOScheduler, attempt: int = 1
) -> None:
    """Daily collect. Pushes the report only on configured report day(s); other
    daily outputs: instant problem alerts, retries for failed platforms, monthly
    digest (1st), weekly DB backup (Sunday), watchdog ping.
    """
    try:
        outcome = await collect_and_report(bot, config, db, force_linkedin=True)
    except Exception:
        # No healthcheck ping on failure — the watchdog will fire.
        logger.exception("Scheduled collection failed")
        return

    today = utcnow().date()

    # Proactive alerts: sent immediately, not held for the report day.
    alerts = await _build_alerts(db, outcome)
    if alerts:
        try:
            await bot.send_message(chat_id=config.admin_chat_id, text="\n".join(alerts))
            logger.info("Sent %d proactive alert(s)", len(alerts))
        except Exception:
            logger.exception("Alert send failed")

    # Retry failed platforms in an hour (cookie expiry is excluded — retrying won't help).
    failed = [p for p in PLATFORMS if outcome.errors.get(p)]
    if failed and attempt < COLLECT_MAX_ATTEMPTS:
        run_at = utcnow() + COLLECT_RETRY_DELAY
        scheduler.add_job(
            _scheduled_job,
            trigger=DateTrigger(run_date=run_at, timezone=UTC),
            args=[bot, config, db, scheduler],
            kwargs={"attempt": attempt + 1},
            id="collect_retry",
            replace_existing=True,
        )
        logger.info(
            "Collection failed for %s — retry %d/%d at %s",
            failed, attempt + 1, COLLECT_MAX_ATTEMPTS, run_at.strftime("%H:%M UTC"),
        )

    if attempt > 1:
        return  # retries only fill data and alert; the rest already ran today

    # Report push on configured day(s)
    dow = await db.get_setting("report_dow") or config.report_dow
    if _today_matches_dow(dow):
        quiet = await is_quiet_mode(db, config)
        try:
            if quiet and not outcome.has_change:
                await bot.send_message(
                    chat_id=config.admin_chat_id,
                    text="😴 Без изменений за неделю — всё стабильно ✅",
                )
                logger.info("Quiet mode: sent no-change one-liner")
            else:
                await bot.send_message(chat_id=config.admin_chat_id, text=outcome.report)
                chart = await _build_chart_png(db)
                if chart:
                    await bot.send_photo(
                        chat_id=config.admin_chat_id,
                        photo=chart,
                        caption="📉 Динамика за 30 дней",
                    )
                logger.info("Scheduled report sent to admin")
        except Exception:
            logger.exception("Scheduled report send failed")
    else:
        logger.info("Today is not a report day (dow=%s) — collected, no push", dow)

    # Monthly digest on the 1st
    if today.day == 1:
        try:
            digest = await build_month_report(db)
            if digest:
                await bot.send_message(chat_id=config.admin_chat_id, text=digest)
                logger.info("Monthly digest sent")
        except Exception:
            logger.exception("Monthly digest failed")

    # Weekly DB backup on Sundays
    if today.weekday() == 6:
        await _send_backup(bot, config)

    await _ping_healthcheck(config)


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
        args=[bot, config, db, scheduler],
        id="scheduled_report",
        replace_existing=True,
    )
    logger.info("Scheduler started: daily collect at %02d:%02d UTC, push on %s", hour, minute, dow)
    return scheduler

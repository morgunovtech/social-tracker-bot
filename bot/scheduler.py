from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from telegram import Bot

from bot import monitors, platforms
from bot.chart import render_chart
from bot.config import DOW_ORDER, Config
from bot.db import Database, parse_utc, utcnow
from bot.monitors import collection, followers, hygiene, mail, profile
from bot.platforms import LABELS, PLATFORM_IDS
from bot.platforms.base import Context
from bot.reporter import _crossed_milestone, build_month_report, build_report
from bot.updates import run_dependency_watch, run_deploy_watch

UTC = ZoneInfo("UTC")

# Failed platforms are re-collected up to this many times, an hour apart.
COLLECT_MAX_ATTEMPTS = 3
COLLECT_RETRY_DELAY = timedelta(hours=1)

# The daily job still runs if it starts up to this many seconds late
# (APScheduler's default grace is 1 second).
DAILY_MISFIRE_GRACE_S = 3600
# On startup, a daily run missed while the bot was down is caught up after this delay.
CATCH_UP_DELAY = timedelta(seconds=30)
LAST_DAILY_RUN_KEY = "last_daily_run"

logger = logging.getLogger(__name__)


@dataclass
class CollectOutcome:
    """Result of one collection pass, including alert-worthy events."""

    report: str
    has_change: bool
    errors: dict[str, bool | int] = field(default_factory=dict)
    collected: dict[str, tuple[int, str]] = field(default_factory=dict)  # platform -> (count, source)
    drops: dict[str, tuple[int, int]] = field(default_factory=dict)  # platform -> (prev, new)
    spikes: dict[str, tuple[int, int]] = field(default_factory=dict)  # platform -> (prev, new)
    milestones: list[tuple[str, int]] = field(default_factory=list)  # (platform, milestone)


def _today_matches_dow(dow_expr: str, now_utc: datetime | None = None) -> bool:
    """Return True if today (UTC) matches the cron day-of-week expression."""
    if dow_expr == "*":
        return True
    today_idx = (now_utc or utcnow()).weekday()  # 0=Mon..6=Sun
    today_short = DOW_ORDER[today_idx]

    if "-" in dow_expr and "," not in dow_expr:
        a, _, b = dow_expr.partition("-")
        try:
            a_idx = DOW_ORDER.index(a.strip())
            b_idx = DOW_ORDER.index(b.strip())
        except ValueError:
            return False
        if a_idx <= b_idx:
            return a_idx <= today_idx <= b_idx
        # Wrap-around (e.g. fri-mon)
        return today_idx >= a_idx or today_idx <= b_idx

    days = {d.strip() for d in dow_expr.split(",")}
    return today_short in days


async def collect_and_report(bot: Bot, config: Config, db: Database) -> CollectOutcome:
    """Collect from every enabled platform, persist, and build a report.

    Alert-worthy events (drops, milestones, failures) are recorded on the
    returned CollectOutcome; deciding whether to notify is the caller's job.
    """
    outcome = CollectOutcome(report="", has_change=False)

    async def record(platform: str, count: int, source: str) -> None:
        """Persist a count and detect drops / spikes / milestone crossings vs the stored value."""
        prev_row = await db.get_latest(platform)
        prev = prev_row["count"] if prev_row else None
        if prev is not None:
            # Spike check reads history, so it runs before today's upsert.
            if count > prev and await followers.is_spike(db, platform, prev, count - prev):
                outcome.spikes[platform] = (prev, count)
        await db.upsert(platform, count, source=source)
        outcome.collected[platform] = (count, source)
        if prev is None:
            return
        if followers.is_drop(prev, count):
            outcome.drops[platform] = (prev, count)
        milestone = _crossed_milestone(prev, count)
        if milestone is not None:
            outcome.milestones.append((platform, milestone))

    enabled = platforms.enabled(config)
    async with aiohttp.ClientSession() as session:
        for platform in enabled:
            prev_row = await db.get_latest(platform.id)
            ctx = Context(bot, session, config, db, prev=prev_row["count"] if prev_row else None)
            snap = await platform.collect(ctx)
            outcome.errors.update(snap.flags)
            if snap.count is not None:
                await record(platform.id, snap.count, snap.source)
            elif snap.error:
                outcome.errors[platform.id] = True

        # Push finalized counts to the website (reuses the open session).
        await _push_subscribers(session, config, db)

    outcome.report, outcome.has_change = await build_stats(db, config, outcome.errors)
    return outcome


async def build_stats(
    db: Database, config: Config, errors: dict[str, bool | int] | None = None
) -> tuple[str, bool]:
    """The follower report plus the security score line (when hygiene is on)."""
    report, has_change = await build_report(
        db,
        errors=errors,
        linkedin_stale_days=config.linkedin_stale_days,
        platforms=config.enabled_platforms,
    )
    if await monitors.is_on(db, config, "hygiene"):
        line = await hygiene.report_line(db, config)
        if line:
            report += f"\n{line}"
    return report, has_change


async def _push_subscribers(
    session: aiohttp.ClientSession, config: Config, db: Database
) -> None:
    """Push finalized subscriber counts to the website's ingest endpoint.

    Fire-and-forget: any failure is logged, never raised, so the report flow is
    unaffected. Reads the authoritative latest count per platform from the DB,
    so a transient collection miss on one platform still pushes the last good
    numbers. Skips entirely until every enabled platform has data.
    """
    if not config.site_ingest_url or not config.site_ingest_token:
        return

    enabled = config.enabled_platforms
    counts: dict[str, int] = {}
    for platform in enabled:
        latest = await db.get_latest(platform)
        if latest is not None:
            counts[platform] = latest["count"]

    if not enabled or len(counts) < len(enabled):
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


async def _build_alerts(db: Database, config: Config, outcome: CollectOutcome) -> list[str]:
    """Proactive alert lines of the monitors that are switched on.

    Drops and milestones are naturally deduped (the stored value moves past
    them); collection health keeps its dedup state in settings.
    """
    lines: list[str] = []
    if await monitors.is_on(db, config, "collection"):
        lines += await collection.alert_lines(db, outcome)
    if await monitors.is_on(db, config, "followers"):
        lines += followers.alert_lines(outcome)
    return lines


async def send_alerts(bot: Bot, config: Config, db: Database, outcome: CollectOutcome) -> None:
    """Send proactive alerts for a collection pass, scheduled or manual (/now).

    Must run after every collect: the next pass compares against the stored
    value, so a drop or spike that isn't alerted now is never alerted.
    """
    try:
        alerts = await _build_alerts(db, config, outcome)
        if alerts:
            await bot.send_message(chat_id=config.admin_chat_id, text="\n".join(alerts))
            logger.info("Sent %d proactive alert(s)", len(alerts))
    except Exception:
        logger.exception("Alert send failed")


async def _build_chart_png(db: Database, days: int = 30) -> bytes | None:
    series: dict[str, list[tuple[datetime, int]]] = {}
    for platform in PLATFORM_IDS:
        rows = await db.get_history(platform, days)
        points = []
        for row in rows:
            try:
                points.append((parse_utc(row["collected_at"]), row["count"]))
            except (ValueError, TypeError):
                continue
        series[LABELS[platform]] = points
    # Rendering is sync CPU work — keep the event loop free.
    return await asyncio.to_thread(render_chart, series)


async def _send_backup(bot: Bot, config: Config, db: Database) -> None:
    """Weekly DB backup straight into the admin chat — free offsite storage.

    The LinkedIn cookie is wiped from the copy: /setcookie deletes it from the
    chat, so the backup must not bring it back.
    """
    try:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "backup.db")
            await db.snapshot_without_secrets(path)
            with open(path, "rb") as f:
                data = f.read()
        today = utcnow().date().isoformat()
        await bot.send_document(
            chat_id=config.admin_chat_id,
            document=data,
            filename=f"followers-{today}.db",
            caption="📦 Еженедельный бэкап БД (без LinkedIn cookie — после восстановления /setcookie)",
        )
        logger.info("DB backup sent (%d bytes)", len(data))
    except Exception:
        logger.exception("DB backup failed")


async def _ping_healthcheck(config: Config) -> None:
    """Dead man's switch: no ping today → the watchdog (healthchecks.io, a
    TofsDevOps heartbeat) notifies the admin."""
    if not config.healthcheck_url:
        return
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                config.healthcheck_url, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status < 300:
                    logger.info("Healthcheck ping: HTTP %s", resp.status)
                else:
                    # e.g. 403 from a wrong secret: the watchdog will think the bot is dead.
                    logger.warning("Healthcheck ping rejected: HTTP %s — check HEALTHCHECK_URL", resp.status)
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
        outcome = await collect_and_report(bot, config, db)
    except Exception:
        # No healthcheck ping on failure — the watchdog will fire.
        logger.exception("Scheduled collection failed")
        return

    today = utcnow().date()
    if attempt == 1:
        await db.set_setting(LAST_DAILY_RUN_KEY, today.isoformat())

    # Proactive alerts: sent immediately, not held for the report day.
    await send_alerts(bot, config, db, outcome)

    # Retry failed platforms in an hour (cookie expiry is excluded — retrying won't help).
    failed = [p for p in PLATFORM_IDS if outcome.errors.get(p)]
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
        # Security hygiene reminder rides along with the report: at most
        # monthly, and only when there is something to do.
        if await monitors.is_on(db, config, "hygiene"):
            try:
                nudge = await hygiene.nudge(db, config)
                if nudge:
                    await bot.send_message(chat_id=config.admin_chat_id, text=nudge)
                    logger.info("Hygiene reminder sent")
            except Exception:
                logger.exception("Hygiene reminder failed")
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

    # Weekly on Sundays: DB backup, then vulnerabilities / PRs waiting for a human
    if today.weekday() == 6:
        await _send_backup(bot, config, db)
        try:
            await run_dependency_watch(bot, config, db)
        except Exception:
            logger.exception("Dependency watch failed")

    await _ping_healthcheck(config)


async def _profile_job(bot: Bot, config: Config, db: Database) -> None:
    """Profile integrity check every profile.CHECK_INTERVAL; changes are alerted at once."""
    if not await monitors.is_on(db, config, "profile"):
        return
    try:
        async with aiohttp.ClientSession() as session:
            lines = await profile.check(bot, config, db, session)
        if lines:
            text = "🛡 Профиль\n\n" + "\n".join(lines)
            if any(line.startswith(("🚨", "🟠")) for line in lines):
                text += f"\n\n{profile.ADVICE}"
            await bot.send_message(chat_id=config.admin_chat_id, text=text, link_preview_options=monitors.NO_PREVIEW)
            logger.info("Sent %d profile alert(s)", len(lines))
    except Exception:
        logger.exception("Profile check failed")


async def _mail_job(bot: Bot, config: Config, db: Database) -> None:
    """Poll the mail worker every mail.POLL_INTERVAL; each security email is alerted at once."""
    if not await monitors.is_on(db, config, "mail"):
        return
    try:
        async with aiohttp.ClientSession() as session:
            sent = await mail.check(bot, config, db, session)
        if sent:
            logger.info("Sent %d security mail alert(s)", sent)
    except Exception:
        logger.exception("Mail check failed")


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
        misfire_grace_time=DAILY_MISFIRE_GRACE_S,
        coalesce=True,
    )
    # Hourly: did the newest commit on main fail to deploy?
    scheduler.add_job(
        run_deploy_watch,
        trigger=IntervalTrigger(hours=1, timezone=UTC),
        args=[bot, config, db],
        id="deploy_watch",
        replace_existing=True,
    )
    logger.info("Scheduler started: daily collect at %02d:%02d UTC, push on %s", hour, minute, dow)

    now = utcnow()
    scheduler.add_job(
        _profile_job,
        trigger=IntervalTrigger(seconds=int(profile.CHECK_INTERVAL.total_seconds()), timezone=UTC),
        args=[bot, config, db],
        id="profile_check",
        replace_existing=True,
        next_run_time=now + CATCH_UP_DELAY,  # the first look after a start refreshes the baseline
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        _mail_job,
        trigger=IntervalTrigger(seconds=int(mail.POLL_INTERVAL.total_seconds()), timezone=UTC),
        args=[bot, config, db],
        id="mail_check",
        replace_existing=True,
        next_run_time=now + CATCH_UP_DELAY,
        coalesce=True,
        max_instances=1,
    )

    # A freshly added cron job only fires in the future: if the bot was down at
    # today's run time, run it shortly instead of losing the day.
    due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now >= due and await db.get_setting(LAST_DAILY_RUN_KEY) != now.date().isoformat():
        run_at = now + CATCH_UP_DELAY
        scheduler.add_job(
            _scheduled_job,
            trigger=DateTrigger(run_date=run_at, timezone=UTC),
            args=[bot, config, db, scheduler],
            id="collect_catch_up",
            replace_existing=True,
        )
        logger.info(
            "Missed today's %02d:%02d UTC run — catching up at %s",
            hour, minute, run_at.strftime("%H:%M:%S UTC"),
        )
    return scheduler

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from telegram import Bot

from bot import monitors, notifier, platforms, reputation, tofs_status, watchdog
from bot.callbacks import CHANNEL, CONNECTIONS, DYNAMICS, SECURITY, WATCHDOG
from bot.chart import render_chart
from bot.config import DOW_ORDER, Config, normalize_tz
from bot.db import Database, parse_utc, utcnow
from bot.i18n import t
from bot.monitors import channel, collection, followers, hygiene, links, mail, outgoing, profile
from bot.notifier import Priority
from bot.platforms import BY_ID, LABELS, PLATFORM_IDS
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

# Translated where it is sent: t(CHART_CAPTION).
CHART_CAPTION = "📉 Подписчики за 30 дней"

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


def _today_matches_dow(dow_expr: str, now: datetime | None = None) -> bool:
    """Return True if today, in the zone of `now` (UTC by default), matches the
    cron day-of-week expression."""
    if dow_expr == "*":
        return True
    today_idx = (now or utcnow()).weekday()  # 0=Mon..6=Sun
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
        await _push_subscribers(session, config, db, bot)

    outcome.report, outcome.has_change = await build_stats(db, config, outcome.errors)
    return outcome


async def build_stats(
    db: Database, config: Config, errors: dict[str, bool | int] | None = None
) -> tuple[str, bool]:
    """The follower report, the channel's week (when the channel monitor is
    on and has data) and the security score line (when hygiene is on)."""
    tz = await get_report_tz(db, config)
    report, has_change = await build_report(
        db,
        errors=errors,
        linkedin_stale_days=config.linkedin_stale_days,
        platforms=config.enabled_platforms,
        shown_date=utcnow().astimezone(tz).date(),
    )
    channel_line = await channel.report_line(db, config)
    if channel_line:
        report += f"\n\n{channel_line}"
    if await monitors.is_on(db, config, "hygiene"):
        line = await hygiene.report_line(db, config)
        if line:
            report += f"\n\n{line}"
    return report, has_change


async def _push_subscribers(
    session: aiohttp.ClientSession, config: Config, db: Database, bot: Bot | None = None,
) -> None:
    """Push finalized subscriber counts to the website's ingest endpoint.

    Never raises, so the report flow is unaffected; every attempt goes to the
    outgoing monitor, which says so after a day without one that landed
    (bot/monitors/outgoing.py). Reads the authoritative latest count per
    platform from the DB, so a transient collection miss on one platform
    still pushes the last good numbers. Skips entirely until every enabled
    platform has data — a skip is not a failure.
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
    error: str | None = None
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
                error = f"rejected:{resp.status}"
    except Exception as e:
        logger.warning("Site push errored: %s", type(e).__name__)
        error = outgoing.error_code(e)
    try:
        await outgoing.record(bot, config, db, outgoing.SITE, error, outgoing.host(config.site_ingest_url))
    except Exception:
        logger.exception("Site push bookkeeping failed")


async def _alert_parts(db: Database, config: Config, outcome: CollectOutcome) -> tuple[list[str], list[str]]:
    """(collection health alerts, follower alerts) of the monitors that are
    switched on — each a message of its own.

    Drops and milestones are naturally deduped (the stored value moves past
    them); collection health keeps its dedup state in settings.
    """
    # Collection health keeps its streaks current even while switched off,
    # so switching it back on doesn't alert on a stale streak.
    collection_lines = await collection.alert_lines(db, outcome, await get_report_tz(db, config))
    if not await monitors.is_on(db, config, "collection"):
        collection_lines = []
    follower_lines = followers.alert_lines(outcome) if await monitors.is_on(db, config, "followers") else []
    return collection_lines, follower_lines


async def _build_alerts(db: Database, config: Config, outcome: CollectOutcome) -> list[str]:
    """Proactive alerts of the monitors that are switched on, one message each."""
    collection_lines, follower_lines = await _alert_parts(db, config, outcome)
    return collection_lines + follower_lines


def _report_actions(config: Config) -> tuple[str, ...]:
    """The row under the report: the screens it leads to."""
    return (DYNAMICS, SECURITY) + ((CHANNEL,) if BY_ID["telegram"].enabled(config) else ())


async def send_alerts(bot: Bot, config: Config, db: Database, outcome: CollectOutcome) -> None:
    """Send proactive alerts for a collection pass, scheduled or manual (/now).

    Must run after every collect: the next pass compares against the stored
    value, so a drop or spike that isn't alerted now is never alerted.
    """
    try:
        collection_lines, follower_lines = await _alert_parts(db, config, outcome)
        # One message per problem (BOT_PRINCIPLES §3), each with the screen it
        # leads to and its own monitor's «⚙️ Не присылать такие».
        batch = [(text, "collection", CONNECTIONS) for text in collection_lines]
        batch += [(text, "followers", DYNAMICS) for text in follower_lines]
        for text, monitor, screen in batch:
            await notifier.send(bot, config, db, text, notifier.priority_for(text), actions=(screen,), monitor=monitor)
        if batch:
            logger.info("Sent %d proactive alert(s)", len(batch))
    except Exception:
        logger.exception("Alert send failed")
    try:
        await offer_watchdog(bot, config, db, outcome)
    except Exception:
        logger.exception("Watchdog offer failed")


# Offered once, as soon as there is something to watch (BOT_PRINCIPLES §6).
WATCHDOG_OFFER = (
    "⏱ Ещё один шаг — сторож. Пока я работаю, о проблемах пишу сам; если остановлюсь — упадёт сервер, "
    "кончится место, отзовут токен — сказать об этом будет некому. Сторож — бесплатный healthchecks.io: "
    "я отмечаюсь у него после каждого ежедневного сбора, а не отметился — он пишет тебе. Две минуты, кнопка ниже."
)


async def offer_watchdog(bot: Bot, config: Config, db: Database, outcome: CollectOutcome) -> bool:
    """After the first collection that read a network: the watchdog, once,
    unless one is already set (in the chat or in HEALTHCHECK_URL)."""
    if not outcome.collected or await db.get_setting(watchdog.OFFERED_KEY) == "1":
        return False
    if await watchdog.url(db, config):
        return False
    if await notifier.send(bot, config, db, t(WATCHDOG_OFFER), Priority.DIGEST, actions=(WATCHDOG,)):
        await db.set_setting(watchdog.OFFERED_KEY, "1")
        return True
    return False


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


async def _send_backup(bot: Bot, config: Config, db: Database, today: date | None = None) -> None:
    """Weekly DB backup straight into the admin chat — free offsite storage;
    today (the owner's local date) names the file.

    The LinkedIn cookie and the Instagram token are wiped from the copy:
    /setcookie and /igtoken delete them from the chat, so the backup must not
    bring them back.
    """
    try:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "backup.db")
            await db.snapshot_without_secrets(path)
            with open(path, "rb") as f:
                data = f.read()
        await notifier.send_document(
            bot, config, db, data, f"followers-{(today or utcnow().date()).isoformat()}.db",
            t(
                "📦 Еженедельный бэкап базы. Чтобы вернуть из него историю, ответь на это сообщение "
                "командой /restore. LinkedIn cookie и токен Instagram в копию не входят: после "
                "восстановления пришли их заново через /setcookie и /igtoken."
            ),
        )
        logger.info("DB backup sent (%d bytes)", len(data))
    except Exception:
        logger.exception("DB backup failed")


def _bot_username(bot) -> str | None:
    try:
        return bot.username if bot is not None else None
    except Exception:   # not initialised yet (tests, early start)
        return None


async def _ping_healthcheck(config: Config, db: Database | None = None, bot=None,
                            errors: dict | None = None) -> None:
    """Dead man's switch: no ping today → the watchdog (healthchecks.io, a
    TofsDevOps heartbeat) notifies the admin. The address set in the chat
    wins over HEALTHCHECK_URL (bot/watchdog.py); the answer's body is read —
    healthchecks.io says «OK (not found)» with HTTP 200 for a deleted check —
    and the outcome is kept for the ⏱ Сторож screen. To TofsDevOps the ping
    carries a line per network for its main screen (bot.tofs_status)."""
    address = await watchdog.url(db, config)
    if not address:
        return
    if db is not None and tofs_status.is_tofs_url(address):
        payload = await tofs_status.build(db, config, errors, _bot_username(bot))
        delivery = await tofs_status.send(address, payload, mark=True)
        error = None if delivery.landed else "tofs"
        # The lines are what TofsDevOps shows: a day of refused lines is told
        # even while the plain mark still lands.
        await outgoing.record(bot, config, db, outgoing.TOFS, delivery.lines_error)
    else:
        error = await watchdog.probe(address)
        if db is not None:
            await outgoing.record(bot, config, db, outgoing.WATCHDOG, error, watchdog.name(address))
    if error is None:
        logger.info("Watchdog ping: %s took the mark", watchdog.name(address))
    else:
        # e.g. a deleted check or a wrong secret: the watchdog will think the bot is dead.
        logger.warning("Watchdog ping to %s did not land: %s — check the address", watchdog.name(address), error)
    if db is not None:
        await watchdog.record(db, error)


def _schedule_retry(
    scheduler: AsyncIOScheduler, bot: Bot, config: Config, db: Database, lock: asyncio.Lock | None, attempt: int
) -> datetime:
    """The next attempt of today's collect, an hour from now; replaces a pending one."""
    run_at = utcnow() + COLLECT_RETRY_DELAY
    scheduler.add_job(
        _scheduled_job,
        trigger=DateTrigger(run_date=run_at, timezone=UTC),
        args=[bot, config, db, scheduler, lock],
        kwargs={"attempt": attempt + 1},
        id="collect_retry",
        replace_existing=True,
    )
    return run_at


async def _scheduled_job(
    bot: Bot, config: Config, db: Database, scheduler: AsyncIOScheduler, lock: asyncio.Lock | None = None,
    attempt: int = 1,
) -> None:
    """Daily collect. Pushes the report only on configured report day(s); other
    daily outputs: instant problem alerts, retries for failed platforms, monthly
    digest (1st), weekly DB backup (Sunday), watchdog ping.

    lock is handlers.collect_lock: a /now in progress is waited for, never
    doubled.
    """
    lock = lock or asyncio.Lock()
    try:
        async with lock:
            outcome = await collect_and_report(bot, config, db)
    except Exception:
        # No healthcheck ping on failure — the watchdog will fire. The whole run
        # is retried like a failed platform, and an owner without a watchdog
        # hears on the second day in a row (bot/monitors/collection.py).
        logger.exception("Scheduled collection failed")
        if attempt < COLLECT_MAX_ATTEMPTS:
            _schedule_retry(scheduler, bot, config, db, lock, attempt)
        if attempt == 1:
            try:
                lines = await collection.run_failed(db)
                if lines and await monitors.is_on(db, config, "collection"):
                    await notifier.send(
                        bot, config, db, "\n".join(lines), notifier.priority_for(lines), monitor="collection"
                    )
            except Exception:
                logger.exception("Collection failure notice failed")
        return

    # The report time and days, the 1st of the month and the Sunday of the
    # backup are in the owner's zone; the follower rows stay on UTC days.
    local_now = utcnow().astimezone(await get_report_tz(db, config))
    today = local_now.date()
    if attempt == 1:
        await db.set_setting(LAST_DAILY_RUN_KEY, local_now.date().isoformat())
    await tofs_status.remember_errors(db, outcome.errors)

    # Proactive alerts: sent immediately, not held for the report day.
    await send_alerts(bot, config, db, outcome)

    # Retry failed platforms in an hour (cookie expiry is excluded — retrying won't help).
    failed = [p for p in PLATFORM_IDS if outcome.errors.get(p)]
    if failed and attempt < COLLECT_MAX_ATTEMPTS:
        run_at = _schedule_retry(scheduler, bot, config, db, lock, attempt)
        logger.info(
            "Collection failed for %s — retry %d/%d at %s",
            failed, attempt + 1, COLLECT_MAX_ATTEMPTS, run_at.strftime("%H:%M UTC"),
        )

    if attempt > 1:
        return  # retries only fill data and alert; the rest already ran today

    # What no screen reads any more goes (bot/db.py, the retention constants).
    try:
        removed = await db.prune()
        if any(removed.values()):
            logger.info("Pruned old rows: %s", removed)
    except Exception:
        logger.exception("Prune failed")

    # Report push on configured day(s)
    dow = await db.get_setting("report_dow") or config.report_dow
    if _today_matches_dow(dow, local_now):
        quiet = await is_quiet_mode(db, config)
        try:
            if quiet and not outcome.has_change:
                await notifier.send(
                    bot, config, db, t("😴 Без изменений за неделю — всё стабильно ✅"), Priority.DIGEST,
                    actions=(DYNAMICS,),
                )
                logger.info("Quiet mode: sent no-change one-liner")
            else:
                # The chart only follows a report delivered now: a digest can't hold it.
                held = await notifier.deferred(db, config, Priority.DIGEST)
                await notifier.send(bot, config, db, outcome.report, Priority.DIGEST, actions=_report_actions(config))
                chart = None if held else await _build_chart_png(db)
                if chart:
                    await notifier.send_photo(bot, config, db, chart, t(CHART_CAPTION))
                logger.info("Scheduled report sent to admin")
        except Exception:
            logger.exception("Scheduled report send failed")
        # Security hygiene reminder rides along with the report: at most
        # monthly, and only when there is something to do.
        if await monitors.is_on(db, config, "hygiene"):
            try:
                nudge = await hygiene.nudge(db, config)
                if nudge:
                    await notifier.send(bot, config, db, nudge, Priority.DIGEST, actions=(SECURITY,))
                    logger.info("Hygiene reminder sent")
            except Exception:
                logger.exception("Hygiene reminder failed")
    else:
        logger.info("Today is not a report day (dow=%s) — collected, no push", dow)

    # Monthly digest on the 1st
    if today.day == 1:
        try:
            digest = await build_month_report(db, today)
            if digest:
                await notifier.send(bot, config, db, digest, Priority.DIGEST, actions=(DYNAMICS,))
                logger.info("Monthly digest sent")
        except Exception:
            logger.exception("Monthly digest failed")

    # Weekly on Sundays: DB backup, then vulnerabilities / PRs waiting for a human
    if today.weekday() == 6:
        await _send_backup(bot, config, db, today)
        try:
            await run_dependency_watch(bot, config, db)
        except Exception:
            logger.exception("Dependency watch failed")

    await _ping_healthcheck(config, db, bot, outcome.errors)

    # Weekly, counted from the last check (the first one with the first run):
    # where the links in the profile descriptions lead. After the mark, so a
    # slow site never delays it.
    try:
        sent = await links.run(bot, config, db)
        if sent:
            logger.info("Sent %d profile link message(s)", sent)
    except Exception:
        logger.exception("Profile link check failed")

    # Weekly, counted from the last one: the reputation report (bot/reputation/).
    try:
        if await reputation.run(bot, config, db):
            logger.info("Reputation report sent")
    except Exception:
        logger.exception("Reputation report failed")


async def _profile_job(bot: Bot, config: Config, db: Database) -> None:
    """Profile integrity check every profile.CHECK_INTERVAL; changes are alerted at once."""
    if not await monitors.is_on(db, config, "profile"):
        return
    try:
        async with aiohttp.ClientSession() as session:
            sent = await profile.check(bot, config, db, session)
        if sent:
            logger.info("Sent %d profile alert(s)", sent)
    except Exception:
        logger.exception("Profile check failed")
        return
    # A channel that stopped being readable shows on the TofsDevOps screen
    # within half an hour, not at tomorrow's collection; not a mark.
    address = await watchdog.url(db, config)
    if tofs_status.is_tofs_url(address):
        payload = await tofs_status.build(db, config, None, _bot_username(bot))
        delivery = await tofs_status.send(address, payload, mark=False)
        await outgoing.record(bot, config, db, outgoing.TOFS, delivery.lines_error)


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
    return dow, config.report_hour, config.report_minute


async def get_report_tz(db: Database, config: Config) -> ZoneInfo:
    """The zone the report time and days are in."""
    stored = await db.get_setting("report_tz")
    if stored:
        try:
            return ZoneInfo(normalize_tz(stored))
        except ValueError:
            logger.warning("Unknown report_tz %r in settings — using UTC", stored)
            return UTC
    if await db.get_setting("report_time") or await db.get_setting("report_dow"):
        return UTC  # saved by a version without the zone setting, which kept them in UTC
    return ZoneInfo(config.report_tz)


async def save_schedule(
    db: Database, config: Config, *, dow: str | None = None, time: tuple[int, int] | None = None
) -> None:
    """Store the report day(s) and/or time together with the zone they are in,
    so a TIMEZONE changed later can't move a schedule already set."""
    tz = await get_report_tz(db, config)  # before the write: a stored schedule changes the answer
    if dow is not None:
        await db.set_setting("report_dow", dow)
    if time is not None:
        await db.set_setting("report_time", f"{time[0]:02d}:{time[1]:02d}")
    await db.set_setting("report_tz", tz.key)


async def is_quiet_mode(db: Database, config: Config) -> bool:
    stored = await db.get_setting("quiet_if_no_change")
    if stored is not None:
        return stored == "1"
    return config.quiet_if_no_change


async def reschedule(scheduler: AsyncIOScheduler, db: Database, config: Config) -> None:
    """Move the daily job to the stored report time. Job fires daily; dow filter is
    applied inside the job so we always have daily data for trends, but push only
    on report day(s).
    """
    dow, hour, minute = await get_report_schedule(db, config)
    tz = await get_report_tz(db, config)
    scheduler.reschedule_job(
        "scheduled_report",
        trigger=CronTrigger(hour=hour, minute=minute, timezone=tz),
    )
    logger.info("Rescheduled daily collect to %02d:%02d %s (push dow=%s)", hour, minute, tz.key, dow)


async def setup_scheduler(
    bot: Bot, config: Config, db: Database, lock: asyncio.Lock | None = None
) -> AsyncIOScheduler:
    """lock: handlers.collect_lock, so the daily run and /now never collect at once."""
    dow, hour, minute = await get_report_schedule(db, config)
    tz = await get_report_tz(db, config)
    scheduler = AsyncIOScheduler(timezone=UTC)
    scheduler.add_job(
        _scheduled_job,
        trigger=CronTrigger(hour=hour, minute=minute, timezone=tz),
        args=[bot, config, db, scheduler, lock],
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
    # Every minute: what quiet hours or /mute held back goes out as one digest.
    scheduler.add_job(
        notifier.flush_queue,
        trigger=IntervalTrigger(minutes=1, timezone=UTC),
        args=[bot, config, db],
        id="flush_queue",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    logger.info("Scheduler started: daily collect at %02d:%02d %s, push on %s", hour, minute, tz.key, dow)

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
    local_now = now.astimezone(tz)
    due = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if local_now >= due and await db.get_setting(LAST_DAILY_RUN_KEY) != local_now.date().isoformat():
        run_at = now + CATCH_UP_DELAY
        scheduler.add_job(
            _scheduled_job,
            trigger=DateTrigger(run_date=run_at, timezone=UTC),
            args=[bot, config, db, scheduler, lock],
            id="collect_catch_up",
            replace_existing=True,
        )
        logger.info(
            "Missed today's %02d:%02d %s run — catching up at %s",
            hour, minute, tz.key, run_at.strftime("%H:%M:%S UTC"),
        )
    return scheduler

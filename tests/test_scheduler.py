import dataclasses
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from conftest import COOKIE

from bot import scheduler
from bot.db import utcnow
from bot.platforms import linkedin as linkedin_platform
from bot.platforms import telegram as telegram_platform
from bot.platforms import youtube as youtube_platform
from bot.scheduler import (
    CollectOutcome,
    _build_alerts,
    _push_subscribers,
    _scheduled_job,
    _send_backup,
    _today_matches_dow,
    collect_and_report,
    get_report_tz,
    save_schedule,
    send_alerts,
    setup_scheduler,
)

SATURDAY = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("expr", "day", "expected"),
    [
        ("*", 0, True),
        ("sat", 5, True),
        ("sat", 4, False),
        ("mon,thu", 3, True),
        ("mon-fri", 2, True),
        ("mon-fri", 6, False),
        ("fri-mon", 6, True),       # wrap-around
        ("fri-mon", 2, False),
    ],
)
def test_today_matches_dow(expr, day, expected):
    monday = datetime(2026, 11, 2, tzinfo=UTC)
    assert _today_matches_dow(expr, monday + timedelta(days=day)) is expected


@pytest.fixture
def collectors(monkeypatch):
    """Replace the network collectors; tests set the values they return."""
    values = {"telegram": 1000, "youtube": 128, "linkedin": (4520, "cookie")}
    seen: dict = {}

    async def telegram(bot, channel_id):
        return values["telegram"]

    async def youtube(session, api_key, channel_id):
        return values["youtube"]

    async def linkedin(session, profile_url, li_at=None, prev=None):
        seen["linkedin_prev"] = prev
        return values["linkedin"]

    monkeypatch.setattr(telegram_platform, "collect_telegram", telegram)
    monkeypatch.setattr(youtube_platform, "collect_youtube", youtube)
    monkeypatch.setattr(linkedin_platform, "collect_linkedin", linkedin)
    values["seen"] = seen
    return values


# --- collect_and_report ------------------------------------------------------

async def test_first_collect_records_everything(bot, config, db, collectors):
    outcome = await collect_and_report(bot, config, db)
    assert set(outcome.collected) == {"telegram", "youtube", "linkedin"}
    assert not outcome.errors and not outcome.drops and not outcome.milestones
    assert "Telegram — 1 000" in outcome.report


async def test_drop_spike_and_milestone(bot, config, db, insert, collectors):
    for day in range(14, 0, -1):                       # steady +2/day on YouTube
        insert("youtube", 100 + (14 - day) * 2, day)
    insert("telegram", 1000, 1)
    insert("linkedin", 995, 1)
    collectors.update(telegram=950, youtube=226, linkedin=(1003, "cookie"))

    outcome = await collect_and_report(bot, config, db)

    assert outcome.drops == {"telegram": (1000, 950)}
    assert outcome.spikes == {"youtube": (126, 226)}
    assert outcome.milestones == [("linkedin", 1000)]


async def test_implausible_linkedin_value_is_rejected(bot, config, db, insert, collectors):
    insert("linkedin", 4500, 1)
    collectors["linkedin"] = (120000, "cookie")
    outcome = await collect_and_report(bot, config, db)
    assert collectors["seen"]["linkedin_prev"] == 4500  # parser got the baseline
    assert outcome.errors == {"linkedin": True}
    assert (await db.get_latest("linkedin"))["count"] == 4500


async def test_failures_and_cookie_state(bot, config, db, collectors):
    collectors.update(telegram=None, linkedin=(None, "cookie_expired"))
    await db.set_setting("linkedin_li_at", COOKIE)
    await db.set_setting("linkedin_li_at_set_at", (utcnow() - timedelta(days=340)).isoformat())
    outcome = await collect_and_report(bot, config, db)
    assert outcome.errors == {
        "telegram": True,
        "linkedin_cookie_expired": True,
        "linkedin_cookie_aging": 340,
    }
    assert "cookie истёк" in outcome.report


async def test_disabled_platform_is_not_collected(bot, config, db, collectors):
    config = dataclasses.replace(config, linkedin_profile_url=None)
    outcome = await collect_and_report(bot, config, db)
    assert "linkedin" not in outcome.collected and "linkedin_prev" not in collectors["seen"]


async def test_linkedin_without_cookie_is_manual_not_an_error(bot, config, db, collectors):
    collectors["linkedin"] = (None, None)
    outcome = await collect_and_report(bot, config, db)
    assert "linkedin" not in outcome.errors


# --- alerts ------------------------------------------------------------------

async def test_cookie_expiry_alerted_once_until_it_works_again(config, db):
    expired = CollectOutcome(report="", has_change=False, errors={"linkedin_cookie_expired": True})
    assert any("cookie истёк" in line for line in await _build_alerts(db, config, expired))
    assert await _build_alerts(db, config, expired) == []
    working = CollectOutcome(report="", has_change=False, collected={"linkedin": (4520, "cookie")})
    await _build_alerts(db, config, working)
    assert await _build_alerts(db, config, expired) != []


async def test_failure_streak_alerts_on_day_two_then_weekly(config, db):
    failed = CollectOutcome(report="", has_change=False, errors={"youtube": True})
    yesterday = (utcnow().date() - timedelta(days=1)).isoformat()

    async def next_day():
        await db.set_setting("fail_last_date_youtube", yesterday)
        return await _build_alerts(db, config, failed)

    assert await _build_alerts(db, config, failed) == []       # day 1
    assert await _build_alerts(db, config, failed) == []       # same-day retry doesn't count
    assert "2 дн. подряд" in (await next_day())[0]     # day 2
    for _ in range(4):                                 # days 3..6
        assert await next_day() == []
    assert "7 дн. подряд" in (await next_day())[0]
    recovered = CollectOutcome(report="", has_change=False, collected={"youtube": (128, "api")})
    await _build_alerts(db, config, recovered)
    assert await db.get_setting("fail_streak_youtube") == "0"


async def test_send_alerts(bot, config, db):
    await send_alerts(bot, config, db, CollectOutcome(report="", has_change=False))
    assert bot.messages == []
    outcome = CollectOutcome(
        report="", has_change=True,
        drops={"telegram": (1000, 950)}, spikes={"youtube": (126, 226)}, milestones=[("linkedin", 1000)],
    )
    await send_alerts(bot, config, db, outcome)
    text = bot.messages[0]
    assert "−50" in text and "наплыв ботов" in text and "LinkedIn перешагнул 1 000" in text


# --- the daily job -----------------------------------------------------------

@pytest.fixture
def job_scheduler():
    return scheduler.AsyncIOScheduler(timezone=scheduler.UTC)


@pytest.fixture
def fake_collect(monkeypatch, db):
    """collect_and_report that only builds the report from what's in the DB."""
    state = {"errors": {}}

    async def _collect(bot, config, database):
        report, has_change = await scheduler.build_report(database)
        return CollectOutcome(report=report, has_change=has_change, errors=dict(state["errors"]))

    monkeypatch.setattr(scheduler, "collect_and_report", _collect)
    return state


async def test_report_day_sends_report_and_chart(bot, config, db, insert, fake_collect, job_scheduler):
    insert("telegram", 1000, 1)
    insert("telegram", 1010, 0)
    await db.set_setting("report_dow", "*")
    await _scheduled_job(bot, config, db, job_scheduler)
    assert bot.messages[0].startswith("📊 Подписчики")
    assert bot.photos and bot.photos[0]["photo"][:4] == b"\x89PNG"
    assert await db.get_setting("last_daily_run") == utcnow().date().isoformat()


async def test_quiet_mode_sends_one_liner(bot, config, db, insert, fake_collect, job_scheduler):
    insert("telegram", 1000, 7)
    insert("telegram", 1000, 0)
    await db.set_setting("report_dow", "*")
    await db.set_setting("quiet_if_no_change", "1")
    await db.set_setting("hygiene_nudged_at", utcnow().date().isoformat())  # no reminder due
    await _scheduled_job(bot, config, db, job_scheduler)
    assert bot.messages == ["😴 Без изменений за неделю — всё стабильно ✅"] and bot.photos == []


async def test_hygiene_reminder_rides_with_the_report(bot, config, db, insert, fake_collect, job_scheduler):
    insert("telegram", 1000, 0)
    await db.set_setting("report_dow", "*")
    await _scheduled_job(bot, config, db, job_scheduler)
    assert bot.messages[-1].startswith("🛡 Безопасность") and "/security" in bot.messages[-1]
    bot.messages.clear()
    await _scheduled_job(bot, config, db, job_scheduler)  # next day: not again for a month
    assert not any(m.startswith("🛡") for m in bot.messages)


async def test_not_a_report_day_stays_silent(bot, config, db, insert, fake_collect, job_scheduler, monkeypatch):
    monkeypatch.setattr(scheduler, "_today_matches_dow", lambda *_: False)
    insert("telegram", 1000, 0)
    await _scheduled_job(bot, config, db, job_scheduler)
    assert bot.messages == [] and bot.documents == []


async def test_report_day_is_the_owners_local_day(bot, config, db, insert, fake_collect, job_scheduler, monkeypatch):
    """A Saturday 01:00 report in Moscow runs on Friday 22:00 UTC: it must still go out."""
    insert("telegram", 1000, 0)
    await db.set_setting("report_dow", "sat")
    await db.set_setting("report_time", "01:00")
    await db.set_setting("report_tz", "Europe/Moscow")
    friday_utc = datetime(2026, 11, 6, 22, 0, tzinfo=UTC)
    monkeypatch.setattr(scheduler, "utcnow", lambda: friday_utc)
    await _scheduled_job(bot, config, db, job_scheduler)
    assert bot.messages and bot.messages[0].startswith("📊 Подписчики")
    assert await db.get_setting("last_daily_run") == "2026-11-07"              # the local date

    bot.messages.clear()
    await db.set_setting("report_dow", "fri")                                   # Friday in UTC, not in Moscow
    await _scheduled_job(bot, config, db, job_scheduler)
    assert not any(m.startswith("📊") for m in bot.messages)


async def test_failed_platform_is_retried_up_to_the_limit(bot, config, db, fake_collect, job_scheduler):
    fake_collect["errors"] = {"youtube": True}
    await _scheduled_job(bot, config, db, job_scheduler)
    retry = job_scheduler.get_job("collect_retry")
    assert retry is not None and retry.kwargs == {"attempt": 2}

    job_scheduler.remove_job("collect_retry")
    bot.messages.clear()
    await _scheduled_job(bot, config, db, job_scheduler, attempt=scheduler.COLLECT_MAX_ATTEMPTS)
    assert job_scheduler.get_job("collect_retry") is None
    assert bot.messages == []                          # retries never re-send the report


async def test_monthly_digest_and_sunday_backup(bot, config, db, insert, fake_collect, job_scheduler, monkeypatch):
    insert("telegram", 1000, 0)
    first_sunday = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
    monkeypatch.setattr(scheduler, "utcnow", lambda: first_sunday)
    monkeypatch.setattr(scheduler, "_today_matches_dow", lambda *_: False)
    await _scheduled_job(bot, config, db, job_scheduler)
    assert any(m.startswith("🗓 Итоги месяца") for m in bot.messages)
    assert bot.documents and bot.documents[0]["filename"] == "followers-2026-11-01.db"


async def test_backup_has_no_cookie(bot, config, db):
    await db.set_setting("linkedin_li_at", COOKIE)
    await db.upsert("telegram", 1000)
    await _send_backup(bot, config, db)
    document = bot.documents[0]["document"]
    assert document.startswith(b"SQLite format 3") and COOKIE.encode() not in document


# --- startup catch-up --------------------------------------------------------

async def test_catch_up_after_a_missed_run(bot, config, db, monkeypatch):
    monkeypatch.setattr(scheduler, "utcnow", lambda: SATURDAY)          # 12:00, run time 08:00
    sched = await setup_scheduler(bot, config, db)
    assert sched.get_job("collect_catch_up") is not None
    assert sched.get_job("scheduled_report").misfire_grace_time == scheduler.DAILY_MISFIRE_GRACE_S


async def test_no_catch_up_when_today_already_ran(bot, config, db, monkeypatch):
    monkeypatch.setattr(scheduler, "utcnow", lambda: SATURDAY)
    await db.set_setting("last_daily_run", SATURDAY.date().isoformat())
    assert (await setup_scheduler(bot, config, db)).get_job("collect_catch_up") is None


async def test_no_catch_up_before_run_time(bot, config, db, monkeypatch):
    monkeypatch.setattr(scheduler, "utcnow", lambda: SATURDAY)
    await db.set_setting("report_time", "13:00")
    assert (await setup_scheduler(bot, config, db)).get_job("collect_catch_up") is None


async def test_catch_up_uses_the_local_run_time(bot, config, db, monkeypatch):
    """02:00 in Moscow is 23:00 UTC the day before: at 00:30 UTC today's run has passed."""
    await db.set_setting("report_time", "02:00")
    await db.set_setting("report_tz", "Europe/Moscow")
    after_midnight = datetime(2026, 11, 7, 0, 30, tzinfo=UTC)
    monkeypatch.setattr(scheduler, "utcnow", lambda: after_midnight)
    assert (await setup_scheduler(bot, config, db)).get_job("collect_catch_up") is not None

    await db.set_setting("last_daily_run", "2026-11-07")
    assert (await setup_scheduler(bot, config, db)).get_job("collect_catch_up") is None


# --- time zones --------------------------------------------------------------

async def test_daily_run_follows_the_local_clock_across_dst(bot, config, db):
    await db.set_setting("report_time", "09:00")
    await db.set_setting("report_tz", "Europe/Berlin")
    trigger = (await setup_scheduler(bot, config, db)).get_job("scheduled_report").trigger
    winter = trigger.get_next_fire_time(None, datetime(2026, 1, 15, tzinfo=UTC))
    summer = trigger.get_next_fire_time(None, datetime(2026, 7, 15, tzinfo=UTC))
    assert winter.astimezone(UTC).hour == 8 and summer.astimezone(UTC).hour == 7


async def test_zone_comes_from_settings_then_env(config, db):
    assert (await get_report_tz(db, config)).key == "UTC"
    moscow = dataclasses.replace(config, report_tz="Europe/Moscow")
    assert (await get_report_tz(db, moscow)).key == "Europe/Moscow"
    await db.set_setting("report_tz", "Asia/Almaty")
    assert (await get_report_tz(db, moscow)).key == "Asia/Almaty"
    await db.set_setting("report_tz", "Mars/Olympus")                          # never written by the bot
    assert await get_report_tz(db, moscow) == ZoneInfo("UTC")


async def test_a_schedule_saved_before_zones_stays_in_utc(config, db):
    await db.set_setting("report_time", "08:00")                               # no report_tz: an older version
    moscow = dataclasses.replace(config, report_tz="Europe/Moscow")
    assert (await get_report_tz(db, moscow)).key == "UTC"


async def test_saving_the_schedule_pins_its_zone(config, db):
    moscow = dataclasses.replace(config, report_tz="Europe/Moscow")
    await save_schedule(db, moscow, time=(11, 0))
    assert await db.get_setting("report_tz") == "Europe/Moscow"
    berlin = dataclasses.replace(config, report_tz="Europe/Berlin")             # REPORT_TZ changed later
    assert (await get_report_tz(db, berlin)).key == "Europe/Moscow"


# --- outbound pushes ---------------------------------------------------------

@pytest.fixture
async def receiver():
    """Local endpoint that records requests (stands in for the site and healthchecks)."""
    received: list[dict] = []

    async def handle(request):
        body = await request.json() if request.method == "POST" else None
        received.append({"method": request.method, "auth": request.headers.get("Authorization"), "body": body})
        return web.Response(text="ok")

    async def forbidden(request):
        received.append({"method": request.method, "auth": None, "body": None})
        return web.Response(status=403, text="Forbidden")

    app = web.Application()
    app.router.add_route("*", "/hook", handle)
    app.router.add_get("/wrong-secret", forbidden)
    server = TestServer(app)
    await server.start_server()
    yield server, received
    await server.close()


async def test_site_push_waits_for_all_platforms(config, db, receiver):
    import aiohttp

    server, received = receiver
    cfg = dataclasses.replace(config, site_ingest_url=str(server.make_url("/hook")), site_ingest_token="t0k")
    await db.upsert("telegram", 1000)
    await db.upsert("youtube", 128)
    async with aiohttp.ClientSession() as session:
        await _push_subscribers(session, cfg, db)
        assert received == []
        await db.upsert("linkedin", 4520)
        await _push_subscribers(session, cfg, db)
    body = received[0]["body"]
    assert received[0]["auth"] == "Bearer t0k"
    assert (body["telegram"], body["youtube"], body["linkedin"]) == (1000, 128, 4520)
    assert body["updatedAt"].endswith("Z")


async def test_healthcheck_ping(config, receiver):
    server, received = receiver
    await scheduler._ping_healthcheck(dataclasses.replace(config, healthcheck_url=str(server.make_url("/hook"))))
    assert received == [{"method": "GET", "auth": None, "body": None}]


async def test_unconfigured_platforms_are_skipped_silently(bot, config, db, collectors):
    only_telegram = dataclasses.replace(config, youtube_api_key=None, linkedin_profile_url=None)
    outcome = await collect_and_report(bot, only_telegram, db)
    assert set(outcome.collected) == {"telegram"} and not outcome.errors
    assert "YouTube" not in outcome.report and "LinkedIn" not in outcome.report
    assert "linkedin_prev" not in collectors["seen"]


async def test_site_push_counts_only_enabled_platforms(config, db, receiver):
    import aiohttp

    server, received = receiver
    cfg = dataclasses.replace(
        config, linkedin_profile_url=None,
        site_ingest_url=str(server.make_url("/hook")), site_ingest_token="t0k",
    )
    await db.upsert("telegram", 1000)
    await db.upsert("youtube", 128)
    async with aiohttp.ClientSession() as session:
        await _push_subscribers(session, cfg, db)
    assert set(received[0]["body"]) == {"telegram", "youtube", "updatedAt"}


async def test_rejected_healthcheck_ping_is_a_warning(config, receiver, caplog):
    server, _ = receiver
    await scheduler._ping_healthcheck(dataclasses.replace(config, healthcheck_url=str(server.make_url("/wrong-secret"))))
    assert "rejected: HTTP 403" in caplog.text


# --- profile watch -----------------------------------------------------------

async def test_profile_and_mail_jobs_respect_the_switch(bot, config, db, monkeypatch):
    calls = []

    async def check(*args):
        calls.append(args)
        return 0

    monkeypatch.setattr(scheduler.profile, "check", check)
    monkeypatch.setattr(scheduler.mail, "check", check)
    mail_config = dataclasses.replace(config, security_mail_url="https://w", security_mail_token="t")
    await scheduler._profile_job(bot, config, db)
    await scheduler._mail_job(bot, mail_config, db)
    assert len(calls) == 2

    await db.set_setting("monitor_profile", "off")
    await db.set_setting("monitor_mail", "off")
    await scheduler._profile_job(bot, config, db)
    await scheduler._mail_job(bot, mail_config, db)
    assert len(calls) == 2


async def test_collection_streak_stays_current_while_switched_off(config, db):
    await db.set_setting("monitor_collection", "off")
    failed = CollectOutcome(report="", has_change=False, errors={"youtube": True})
    assert await _build_alerts(db, config, failed) == []
    recovered = CollectOutcome(report="", has_change=False, collected={"youtube": (128, "api")})
    await _build_alerts(db, config, recovered)
    assert await db.get_setting("fail_streak_youtube") == "0"


async def test_profile_watch_is_scheduled_soon_after_start(bot, config, db):
    job = (await setup_scheduler(bot, config, db)).get_job("profile_check")
    assert job is not None and job.next_run_time <= utcnow() + timedelta(minutes=1)

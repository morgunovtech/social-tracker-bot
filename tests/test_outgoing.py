"""What the bot sends out is watched too (bot/monitors/outgoing.py): the
counts to the site, the lines to TofsDevOps, the watchdog's mark."""

from __future__ import annotations

import dataclasses
from datetime import timedelta

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from conftest import buttons

from bot import monitors, scheduler, tofs_status, ui, watchdog
from bot.monitors import outgoing
from bot.monitors.outgoing import ALERT_AFTER, SITE, TOFS, WATCHDOG, record


@pytest.fixture
async def site():
    """A site's ingest endpoint and a TofsDevOps heartbeat: .status says what they answer."""
    state = {"status": 200, "received": []}

    async def handle(request):
        state["received"].append(request.method)
        return web.Response(status=state["status"], text="ok" if state["status"] < 300 else "nope")

    app = web.Application()
    app.router.add_route("*", "/api/ingest/subscribers", handle)
    app.router.add_route("*", "/api/heartbeat/s3cr3t/socialtracker", handle)
    server = TestServer(app)
    await server.start_server()
    yield server, state
    await server.close()


async def _age(db, target: str, by: timedelta) -> None:
    """Move the first failure of the series back in time."""
    import json

    data = await outgoing.state(db, target)
    since = outgoing._when(data["fail_since"]) - by
    data["fail_since"] = since.isoformat()
    await db.set_setting(outgoing._key(target), json.dumps(data))


async def test_a_day_without_a_landed_push_is_one_warning_and_its_end_one_recovery(bot, config, db):
    await record(bot, config, db, SITE, None, "s.example.com")
    await record(bot, config, db, SITE, "rejected:401", "s.example.com")
    assert bot.messages == []                                   # one failure is not a day
    await _age(db, SITE, ALERT_AFTER)
    await record(bot, config, db, SITE, "rejected:401", "s.example.com")
    (text,) = bot.messages
    assert text.startswith("🟠 s.example.com не принимает цифры подписчиков уже 23 ч: отвечает ошибкой 401")
    assert "SOCIALBOT_INGEST_TOKEN" in text and "Тех.: последняя удачная" in text and "rejected:401" in text
    assert bot.silent == [True]
    assert buttons(bot.markups[0]) == {
        "open:set": "⚙️ Настройки", "mute:8h": "🔕 Тихо 8 ч", "mod:outgoing:off": "⚙️ Не присылать такие",
    }
    await record(bot, config, db, SITE, "timeout", "s.example.com")
    assert len(bot.messages) == 1                               # once until it recovers
    await record(bot, config, db, SITE, None, "s.example.com")
    assert bot.messages[-1].startswith("✅ s.example.com снова принимает цифры подписчиков. Не принимал 23 ч")
    await record(bot, config, db, SITE, None, "s.example.com")
    assert len(bot.messages) == 2


async def test_a_short_failure_that_recovered_says_nothing(bot, config, db):
    await record(bot, config, db, TOFS, "rejected:400")
    await record(bot, config, db, TOFS, None)
    assert bot.messages == []


async def test_switched_off_it_keeps_count_but_says_nothing(bot, config, db):
    await monitors.set_switch(db, "outgoing", False)
    await record(bot, config, db, WATCHDOG, "not_found", "healthchecks.io")
    await _age(db, WATCHDOG, ALERT_AFTER)
    await record(bot, config, db, WATCHDOG, "not_found", "healthchecks.io")
    assert bot.messages == []
    await monitors.set_switch(db, "outgoing", True)            # on again: the day is already there
    await record(bot, config, db, WATCHDOG, "not_found", "healthchecks.io")
    assert bot.messages[-1].startswith("🟠 Сторож healthchecks.io не принимает отметки уже 23 ч: check не найден")


async def test_the_site_push_is_recorded(bot, config, db, site):
    server, state = site
    cfg = dataclasses.replace(config, site_ingest_url=str(server.make_url("/api/ingest/subscribers")),
                              site_ingest_token="t0k", linkedin_profile_url=None)
    await db.upsert("telegram", 1000)
    await db.upsert("youtube", 128)
    async with aiohttp.ClientSession() as session:
        await scheduler._push_subscribers(session, cfg, db, bot)
        assert (await outgoing.state(db, SITE))["ok_at"]
        state["status"] = 401
        await scheduler._push_subscribers(session, cfg, db, bot)
    data = await outgoing.state(db, SITE)
    assert data["error"] == "rejected:401" and data["where"] == "127.0.0.1"
    screen = await ui.settings(db, cfg)
    assert "📤 <b>Отправки</b>" in screen.text
    assert "⚠️ Цифры на сайт (127.0.0.1): не доходят с сегодня" in screen.text and "отвечает ошибкой 401" in screen.text


async def test_lines_tofsdevops_refuses_are_counted_even_when_the_mark_lands(bot, config, db, site, insert):
    server, state = site
    insert("telegram", 1000)
    address = str(server.make_url("/api/heartbeat/s3cr3t/socialtracker"))
    cfg = dataclasses.replace(config, healthcheck_url=address)
    state["status"] = 400                                       # a format TofsDevOps does not take; GET also 400 here
    delivery = await tofs_status.send(address, await tofs_status.build(db, cfg, {}), mark=True)
    assert delivery.lines_error == "rejected:400" and not delivery
    await scheduler._ping_healthcheck(cfg, db, bot, {})
    assert (await outgoing.state(db, TOFS))["error"] == "rejected:400"
    assert (await watchdog.last(db))["error"] == "tofs"
    state["status"] = 200
    await scheduler._ping_healthcheck(cfg, db, bot, {})
    assert (await outgoing.state(db, TOFS)).get("error") is None
    screen = await ui.settings(db, cfg)
    assert "✅ Строки в TofsDevOps: последняя удачная сегодня" in screen.text


async def test_a_healthchecks_mark_is_recorded(bot, config, db, site):
    server, _ = site
    cfg = dataclasses.replace(config, healthcheck_url=str(server.make_url("/api/ingest/subscribers")))
    await scheduler._ping_healthcheck(cfg, db, bot, {})
    assert (await outgoing.state(db, WATCHDOG))["ok_at"]
    assert "✅ Отметки сторожу (127.0.0.1): последняя удачная" in (await ui.settings(db, cfg)).text


async def test_settings_say_nothing_about_what_is_not_sent(config, db):
    assert "Отправки" not in (await ui.settings(db, config)).text


def test_the_host_never_carries_the_path_or_the_query():
    assert outgoing.host("https://s.morgunov.tech/api/ingest/subscribers?key=x") == "s.morgunov.tech"
    assert outgoing.host(None) == ""

"""⏱ Сторож from the chat (BOT_PRINCIPLES §6): the address is set with a live
test ping that reads the answer's body, kept in the DB and out of the backup;
HEALTHCHECK_URL is the fallback; the daily ping uses the DB first; the
watchdog is offered once after the first collection."""

import dataclasses
import json

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from conftest import buttons
from telegram.ext import ConversationHandler

from bot import callbacks as cb
from bot import handlers, main, scheduler, ui, watchdog
from bot.config import first_url
from bot.db import Database
from bot.scheduler import CollectOutcome, send_alerts


@pytest.fixture
async def hc():
    """A fake healthchecks.io: /ok takes the ping, /gone is a deleted check
    (HTTP 200 «OK (not found)»), /forbidden a wrong secret."""
    pings: list[str] = []

    async def ok(request):
        pings.append(request.path)
        return web.Response(text="OK")

    async def gone(request):
        pings.append(request.path)
        return web.Response(text="OK (not found)")

    async def forbidden(request):
        pings.append(request.path)
        return web.Response(status=403, text="Forbidden")

    app = web.Application()
    app.router.add_get("/ok", ok)
    app.router.add_get("/gone", gone)
    app.router.add_get("/forbidden", forbidden)
    server = TestServer(app)
    await server.start_server()
    yield server, pings
    await server.close()


def _url(server, path: str) -> str:
    return str(server.make_url(path))


# --- the address and the ping --------------------------------------------------

def test_parse_takes_only_an_https_address_out_of_a_pasted_line():
    assert watchdog.parse("&& curl -fsS https://hc-ping.com/1b2c3d4e-5f60") == "https://hc-ping.com/1b2c3d4e-5f60"
    assert watchdog.parse("http://hc-ping.com/1b2c3d4e-5f60") is None          # §3: the owner's input is https only
    assert watchdog.parse("not a link") is None
    assert watchdog.name("https://hc-ping.com/x") == "healthchecks.io"
    assert watchdog.name("https://tofs.example/api/heartbeat/s3cr3t/social") == "TofsDevOps"


async def test_probe_reads_the_body_not_only_the_status(hc):
    server, _ = hc
    assert await watchdog.probe(_url(server, "/ok")) is None
    assert await watchdog.probe(_url(server, "/gone")) == "not_found"           # 200 «OK (not found)»
    assert await watchdog.probe(_url(server, "/forbidden")) == "rejected:403"
    assert await watchdog.probe("http://127.0.0.1:9/") == "connect"
    assert watchdog.reason("rejected:403") == "отвечает ошибкой 403"
    assert watchdog.reason("not_found").startswith("check не найден")


async def test_the_address_from_the_chat_wins_over_the_variable(config, db, hc):
    server, pings = hc
    cfg = dataclasses.replace(config, healthcheck_url=_url(server, "/forbidden"))
    assert await watchdog.url(db, cfg) == cfg.healthcheck_url and await watchdog.source(db, cfg) == "env"
    await watchdog.save(db, _url(server, "/ok"))
    assert await watchdog.source(db, cfg) == "chat"
    await scheduler._ping_healthcheck(cfg, db)
    assert pings == ["/ok"] and (await watchdog.last(db))["error"] is None
    await watchdog.forget(db)                                                   # the variable takes over again
    await scheduler._ping_healthcheck(cfg, db)
    assert pings == ["/ok", "/forbidden"] and (await watchdog.last(db))["error"] == "rejected:403"


async def test_a_deleted_check_is_noticed_by_the_daily_ping(config, db, hc, caplog):
    server, _ = hc
    await watchdog.save(db, _url(server, "/gone"))
    await scheduler._ping_healthcheck(config, db)
    assert "did not land: not_found" in caplog.text
    assert "/gone" not in caplog.text                                           # the address never reaches a log line
    line = await ui.watchdog_line(db, config)
    assert line.startswith("🟠 ⏱ Сторож — 127.0.0.1: check не найден")


async def test_the_stored_address_is_a_secret(config, db, tmp_path, monkeypatch):
    address = "https://hc-ping.com/1b2c3d4e-5f60-7182-93a4-b5c6d7e8f901"
    await watchdog.save(db, address)
    monkeypatch.setattr(main, "_config", config)
    assert address in main.secret_values()                                       # masked in every log line
    copy = str(tmp_path / "backup.db")
    await db.snapshot_without_secrets(copy)
    assert await Database(copy).get_setting(watchdog.URL_KEY) is None           # not in the Sunday backup
    restored = Database(str(tmp_path / "fresh.db"))
    await restored.init()
    await restored.set_setting(watchdog.URL_KEY, "https://hc-ping.com/live-one-0000")
    await restored.restore_from(copy)
    assert await restored.get_setting(watchdog.URL_KEY) == "https://hc-ping.com/live-one-0000"


# --- the screen and the step --------------------------------------------------

async def test_connections_show_the_watchdog_and_lead_to_its_screen(config, db, hc):
    server, _ = hc
    screen = await ui.connections(db, config)
    assert "➖ ⏱ Сторож — не подключён" in screen.text and cb.WATCHDOG in buttons(screen.keyboard)
    screen = await ui.watchdog_screen(db, config)
    assert set(buttons(screen.keyboard)) == {cb.WD_URL, cb.CONNECTIONS}         # nothing to test or switch off yet
    await watchdog.save(db, _url(server, "/ok"))
    screen = await ui.watchdog_screen(db, config)
    assert "✅ ⏱ Сторож — 127.0.0.1, отметка сегодня" in screen.text
    assert "/ok" not in screen.text                                             # never the address itself
    assert {"wd:test", "wd:off"} <= set(buttons(screen.keyboard))


async def test_a_link_by_message_is_tested_before_it_is_kept(make_update, make_context, db, hc, monkeypatch):
    server, pings = hc
    https_only = watchdog.parse
    # The local server speaks plain http; everything else still goes through the https-only parser.
    monkeypatch.setattr(watchdog, "parse", lambda text: first_url(text) if "127.0.0.1" in text else https_only(text))
    update, context = make_update(callback=cb.WD_URL), make_context()
    assert await handlers.input_conv_start(update, context) == handlers.AWAITING_INPUT
    assert update.callback_query.edits[0].startswith("🔗 Пришли ссылку сторожа")

    deleted = make_update(text=f"&& curl -fsS {_url(server, '/gone')}")
    assert await handlers.input_conv_value(deleted, context) == handlers.AWAITING_INPUT    # the step stays open
    assert deleted.message.deleted and "check не найден" in deleted.effective_chat.sent[-1]
    assert await db.get_setting(watchdog.URL_KEY) is None

    plain = make_update(text="http://hc-ping.com/nope")
    assert await handlers.input_conv_value(plain, context) == handlers.AWAITING_INPUT
    assert plain.effective_chat.sent[-1].startswith("❌ Нужна ссылка https://")

    good = make_update(text=_url(server, "/ok"))
    assert await handlers.input_conv_value(good, context) == ConversationHandler.END
    assert good.message.deleted and await db.get_setting(watchdog.URL_KEY) == _url(server, "/ok")
    assert "✅ Сторож подключён и на связи (127.0.0.1)" in good.effective_chat.sent[-1]
    assert pings == ["/gone", "/ok"]


async def test_check_again_and_switch_off_after_a_question(make_update, make_context, db, hc):
    server, pings = hc
    await watchdog.save(db, _url(server, "/ok"))
    update = make_update(callback="wd:test")
    await handlers.on_callback(update, make_context())
    assert update.callback_query.answers[0]["text"] == "✅ Сторож на связи" and pings == ["/ok"]

    update = make_update(callback="wd:off")
    await handlers.on_callback(update, make_context())
    assert update.callback_query.edits[0].startswith("<b>⏏ Отключить сторожа?</b>")
    assert await db.get_setting(watchdog.URL_KEY)                               # nothing removed before «yes»
    update = make_update(callback="wd:off:yes")
    await handlers.on_callback(update, make_context())
    assert await watchdog.url(db, make_context().bot_data["config"]) is None
    assert update.callback_query.answers[0]["text"] == "Сторож отключён"


# --- offered once ---------------------------------------------------------------

async def test_the_watchdog_is_offered_once_after_the_first_collection(bot, config, db):
    await send_alerts(bot, config, db, CollectOutcome(report="", has_change=False))   # nothing collected yet
    assert bot.messages == []
    first = CollectOutcome(report="", has_change=False, collected={"telegram": (1000, "api")})
    await send_alerts(bot, config, db, first)
    assert len(bot.messages) == 1 and bot.messages[0].startswith("⏱ Ещё один шаг — сторож")
    assert buttons(bot.markups[0]) == {"open:wd": "⏱ Сторож"}
    await send_alerts(bot, config, db, first)
    assert len(bot.messages) == 1                                               # once


async def test_no_offer_when_a_watchdog_is_already_set(bot, config, db):
    with_env = dataclasses.replace(config, healthcheck_url="https://hc-ping.com/already-there")
    outcome = CollectOutcome(report="", has_change=False, collected={"telegram": (1000, "api")})
    await send_alerts(bot, with_env, db, outcome)
    assert bot.messages == []
    assert json.loads(await db.get_setting(watchdog.LAST_KEY) or "{}") == {}

"""Instagram: the official API behind a token the bot keeps fresh itself."""

import dataclasses
from datetime import timedelta

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from conftest import FakeBot

from bot import handlers, tofs_status, ui
from bot.config import Config
from bot.db import utcnow
from bot.monitors import collection, mail, profile
from bot.platforms import BY_ID
from bot.platforms import instagram as ig
from bot.platforms.base import Context
from bot.reporter import build_report
from bot.scheduler import CollectOutcome

TOKEN = "IGAA" + "x" * 120
USER = {"user_id": "17841400000", "username": "semyon", "name": "Семён", "biography": "о себе",
        "followers_count": 1234, "media_count": 56}


@pytest.fixture
def config(tmp_path) -> Config:
    return dataclasses.replace(Config.from_env(), db_path=str(tmp_path / "followers.db"), instagram_username="semyon")


@pytest.fixture
async def graph(monkeypatch):
    """A stand-in for graph.instagram.com: `state` controls what it answers."""
    state = {"user": dict(USER), "status": 200, "refresh": {"access_token": "IGnew" + "y" * 120, "expires_in": 5184000},
             "refresh_status": 200, "calls": []}

    async def me(request):
        state["calls"].append(("me", request.query.get("access_token")))
        if state["status"] == 190:
            return web.json_response({"error": {"message": "Invalid OAuth access token", "type": "OAuthException", "code": 190}},
                                     status=400)
        if state["status"] != 200:
            return web.json_response({"error": {"message": "rate limit", "code": 4}}, status=state["status"])
        return web.json_response(state["user"])

    async def refresh(request):
        state["calls"].append(("refresh", request.query.get("access_token")))
        if state["refresh_status"] != 200:
            return web.json_response({"error": {"message": "too young", "type": "OAuthException", "code": 190}}, status=400)
        return web.json_response(state["refresh"])

    app = web.Application()
    app.router.add_get("/me", me)
    app.router.add_get("/refresh_access_token", refresh)
    server = TestServer(app)
    await server.start_server()
    monkeypatch.setattr(ig, "_GRAPH_URL", str(server.make_url("")).rstrip("/"))
    yield state
    await server.close()


# --- the API --------------------------------------------------------------------

async def test_collect_reads_followers_count(graph):
    async with aiohttp.ClientSession() as session:
        assert await ig.collect_instagram(session, TOKEN) == (1234, "api")


@pytest.mark.parametrize(("status", "expected"), [(190, (None, "token_expired")), (500, (None, None))])
async def test_collect_tells_a_dead_token_from_an_outage(graph, status, expected):
    graph["status"] = status
    async with aiohttp.ClientSession() as session:
        assert await ig.collect_instagram(session, TOKEN) == expected


async def test_collect_without_token_is_a_skip(graph):
    async with aiohttp.ClientSession() as session:
        assert await ig.collect_instagram(session, None) == (None, None)
    assert graph["calls"] == []


async def test_profile_fields(graph):
    async with aiohttp.ClientSession() as session:
        assert await ig.fetch_instagram_profile(session, TOKEN) == {
            "username": "semyon", "name": "Семён", "biography": "о себе", "media": "56",
        }
        # No token / a dead token: nothing to compare, but not «unreachable».
        assert await ig.fetch_instagram_profile(session, None) == {}
        graph["status"] = 190
        assert await ig.fetch_instagram_profile(session, TOKEN) == {}
        graph["status"] = 500
        assert await ig.fetch_instagram_profile(session, TOKEN) is None


# --- the token's life -------------------------------------------------------------

async def test_a_young_token_is_left_alone(graph, config, db):
    await ig.store_token(db, TOKEN)
    async with aiohttp.ClientSession() as session:
        assert await ig.ensure_fresh_token(db, config, session) == TOKEN
    assert graph["calls"] == []
    assert 58 <= await ig.get_token_days_left(db) <= 60


async def test_a_token_past_its_first_month_is_refreshed(graph, config, db):
    await ig.store_token(db, TOKEN)
    await db.set_setting(ig.TOKEN_EXPIRES_AT_KEY, (utcnow() + timedelta(days=20)).isoformat())
    async with aiohttp.ClientSession() as session:
        token = await ig.ensure_fresh_token(db, config, session)
    assert token == graph["refresh"]["access_token"]
    assert await db.get_setting(ig.TOKEN_KEY) == token
    assert 59 <= await ig.get_token_days_left(db) <= 60


async def test_a_failed_refresh_keeps_the_old_token(graph, config, db):
    await ig.store_token(db, TOKEN)
    await db.set_setting(ig.TOKEN_EXPIRES_AT_KEY, (utcnow() + timedelta(days=20)).isoformat())
    graph["refresh_status"] = 400
    async with aiohttp.ClientSession() as session:
        assert await ig.ensure_fresh_token(db, config, session) == TOKEN
    assert await db.get_setting(ig.TOKEN_KEY) == TOKEN


async def test_an_env_token_is_refreshed_into_the_db(graph, db):
    config = dataclasses.replace(Config.from_env(), instagram_username="semyon", instagram_access_token=TOKEN)
    async with aiohttp.ClientSession() as session:
        token = await ig.ensure_fresh_token(db, config, session)
    assert token == graph["refresh"]["access_token"] and await ig.get_token_days_left(db) is not None


# --- the connector ---------------------------------------------------------------

async def _collect(config, db):
    async with aiohttp.ClientSession() as session:
        return await BY_ID["instagram"].collect(Context(FakeBot(), session, config, db))


async def test_connector_flags(graph, config, db):
    assert BY_ID["instagram"].enabled(config) and BY_ID["instagram"].target(config) == "@semyon"
    snap = await _collect(config, db)
    assert snap.count is None and not snap.error and snap.flags == {"instagram_token_missing": True}

    await ig.store_token(db, TOKEN)
    snap = await _collect(config, db)
    assert (snap.count, snap.source, snap.flags) == (1234, "api", {})

    await db.set_setting(ig.TOKEN_EXPIRES_AT_KEY, (utcnow() + timedelta(days=3)).isoformat())
    graph["refresh_status"] = 400
    snap = await _collect(config, db)
    assert snap.count == 1234 and snap.flags == {"instagram_token_expiring": 2}

    graph["status"] = 190
    snap = await _collect(config, db)
    assert snap.count is None and not snap.error and snap.flags == {"instagram_token_expired": True}

    graph["status"] = 500
    snap = await _collect(config, db)
    assert snap.count is None and snap.error


async def test_profile_monitor_watches_instagram(graph, config, db):
    config = dataclasses.replace(config, telegram_channel_id=None, youtube_api_key=None)  # Instagram alone
    await ig.store_token(db, TOKEN)
    bot = FakeBot()
    async with aiohttp.ClientSession() as session:
        assert await profile.check(bot, config, db, session) == 0  # baseline
        graph["user"]["biography"] = "crypto giveaway https://evil.example"
        graph["user"]["media_count"] = 10
        assert await profile.check(bot, config, db, session) == 1
    alert = bot.messages[-1]
    assert "🚨 Instagram: описание профиля" in alert and "hxxps://evil[.]example" in alert
    assert "публикаций — было 56, стало 10" in alert


# --- what the user sees ---------------------------------------------------------------

async def test_report_and_status_lines(config, db, insert):
    text, _ = await build_report(db, errors={"instagram_token_missing": True}, platforms=["instagram"])
    assert "токена нет — пришли его через /igtoken" in text and "Instagram — пока нет данных: нужен токен" in text
    text, _ = await build_report(db, errors={"instagram_token_expired": True}, platforms=["instagram"])
    assert "Instagram отклонил токен" in text
    insert("instagram", 1234)
    text, _ = await build_report(db, errors={"instagram_token_expiring": 3}, platforms=["instagram"])
    assert "истекает через 3 дн." in text

    items = {i["name"]: i for i in (await tofs_status.build(db, config, {"instagram_token_expiring": 3}))["items"]}
    assert items["Instagram"]["level"] == "warning" and "токен истекает через 3 дн." in items["Instagram"]["text"]
    items = {i["name"]: i for i in (await tofs_status.build(db, config, {"instagram_token_expired": True}))["items"]}
    assert items["Instagram"]["text"] == "токен истёк — пришли новый через /igtoken"


async def test_collection_alerts_once_until_a_token_works(db):
    missing = CollectOutcome(report="", has_change=False, errors={"instagram_token_missing": True})
    assert any("токена нет" in line for line in await collection.alert_lines(db, missing))
    assert await collection.alert_lines(db, missing) == []
    ok = CollectOutcome(report="", has_change=False, collected={"instagram": (1234, "api")})
    assert await collection.alert_lines(db, ok) == []
    dead = CollectOutcome(report="", has_change=False, errors={"instagram_token_expired": True})
    assert any("отклонил токен" in line for line in await collection.alert_lines(db, dead))


async def test_settings_and_instagram_screen(config, db):
    screen = await ui.settings(db, config)
    assert "📸 Instagram" in [b.text for row in screen.keyboard.inline_keyboard for b in row]
    screen = await ui.instagram(db, config)
    assert "Аккаунт: @semyon" in screen.text and "Токена нет" in screen.text
    await ig.store_token(db, TOKEN)
    screen = await ui.instagram(db, config)
    assert "действует ещё 59 дн." in screen.text or "действует ещё 60 дн." in screen.text


async def test_igtoken_command(graph, make_update, make_context, db):
    update = make_update()
    await handlers.cmd_igtoken(update, make_context("short"))
    assert update.message.deleted and "слишком короткое" in update.effective_chat.sent[-1]

    graph["user"]["username"] = "someone_else"
    update = make_update()
    await handlers.cmd_igtoken(update, make_context(TOKEN))
    assert "от аккаунта @someone_else" in update.effective_chat.sent[-1]
    assert await db.get_setting(ig.TOKEN_KEY) is None

    graph["user"]["username"] = "Semyon"
    await db.set_setting("instagram_token_alerted", "1")
    update = make_update()
    await handlers.cmd_igtoken(update, make_context(TOKEN))
    assert update.message.deleted and "✅ Токен сохранён" in update.effective_chat.sent[-1]
    assert "1\u00a0234 подписчиков" in update.effective_chat.sent[-1]
    assert await db.get_setting(ig.TOKEN_KEY) == TOKEN
    assert await db.get_setting("instagram_token_alerted") == "0"
    assert (await db.get_latest("instagram"))["count"] == 1234

    graph["status"] = 190
    update = make_update()
    await handlers.cmd_igtoken(update, make_context("IGdead" + "z" * 100))
    assert "Instagram отклонил токен" in update.effective_chat.sent[-1]
    assert await db.get_setting(ig.TOKEN_KEY) == TOKEN  # the working one stays


async def test_token_stays_out_of_backups(db, tmp_path):
    await ig.store_token(db, TOKEN)
    await db.snapshot_without_secrets(str(tmp_path / "copy.db"))
    import sqlite3
    with sqlite3.connect(tmp_path / "copy.db") as conn:
        keys = {k for (k,) in conn.execute("SELECT key FROM settings")}
    assert ig.TOKEN_KEY not in keys and ig.TOKEN_SET_AT_KEY in keys


def test_security_mail_from_instagram_links_the_connector():
    assert ("instagram.com", "Instagram", "instagram") in mail.SENDERS

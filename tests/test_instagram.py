"""Instagram: the official API behind a system-user token of the owner's Meta app."""

import dataclasses
import sqlite3

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from conftest import FakeBot

from bot import handlers, tofs_status, ui
from bot.config import Config
from bot.monitors import collection, mail, profile
from bot.platforms import BY_ID
from bot.platforms import instagram as ig
from bot.platforms.base import Context
from bot.reporter import build_report
from bot.scheduler import CollectOutcome

TOKEN = "EAAB" + "x" * 150
USER_ID = "17841400000000000"
USER = {"id": USER_ID, "username": "semyon", "name": "Семён", "biography": "о себе",
        "followers_count": 1234, "media_count": 56}


@pytest.fixture
def config(tmp_path) -> Config:
    return dataclasses.replace(Config.from_env(), db_path=str(tmp_path / "followers.db"), instagram_username="semyon")


@pytest.fixture
async def graph(monkeypatch):
    """A stand-in for graph.facebook.com: `state` controls what it answers."""
    state = {"user": dict(USER), "status": 200, "assigned": [{"id": USER_ID, "username": "semyon"}], "calls": []}

    def _error(request):
        if state["status"] == 190:
            return web.json_response(
                {"error": {"message": "Invalid OAuth access token", "type": "OAuthException", "code": 190}}, status=400
            )
        if state["status"] != 200:
            return web.json_response({"error": {"message": "rate limit", "code": 4}}, status=state["status"])
        return None

    async def assigned(request):
        state["calls"].append(("assigned", request.query.get("access_token")))
        return _error(request) or web.json_response({"data": state["assigned"], "paging": {}})

    async def me(request):
        state["calls"].append(("me", request.query.get("access_token")))
        return _error(request) or web.json_response({"error": {"message": "/me is the system user", "code": 100}}, status=400)

    async def user(request):
        state["calls"].append(("user", request.match_info["id"]))
        if request.match_info["id"] != USER_ID:
            return web.json_response({"error": {"message": "Unsupported get request", "code": 100}}, status=400)
        return _error(request) or web.json_response(state["user"])

    app = web.Application()
    app.router.add_get("/me/assigned_instagram_accounts", assigned)
    app.router.add_get("/me", me)
    app.router.add_get("/{id}", user)
    server = TestServer(app)
    await server.start_server()
    monkeypatch.setattr(ig, "_GRAPH_URL", str(server.make_url("")).rstrip("/"))
    yield state
    await server.close()


# --- the API --------------------------------------------------------------------

async def test_collect_reads_followers_count(graph):
    async with aiohttp.ClientSession() as session:
        assert await ig.collect_instagram(session, TOKEN, USER_ID) == (1234, "api")


@pytest.mark.parametrize(("status", "expected"), [(190, (None, "token_expired")), (500, (None, None))])
async def test_collect_tells_a_dead_token_from_an_outage(graph, status, expected):
    graph["status"] = status
    async with aiohttp.ClientSession() as session:
        assert await ig.collect_instagram(session, TOKEN, USER_ID) == expected


async def test_collect_without_token_is_a_skip(graph):
    async with aiohttp.ClientSession() as session:
        assert await ig.collect_instagram(session, None, USER_ID) == (None, None)
        assert await ig.collect_instagram(session, TOKEN, None) == (None, None)
    assert graph["calls"] == []


async def test_resolve_account_matches_the_username(graph):
    graph["assigned"] = [{"id": "1", "username": "other"}, {"id": USER_ID, "username": "Semyon"}]
    async with aiohttp.ClientSession() as session:
        assert await ig.resolve_account(session, TOKEN, "semyon") == USER_ID
        assert await ig.resolve_account(session, TOKEN, "nobody") is None
        graph["status"] = 190
        with pytest.raises(ig.InstagramAuthError):
            await ig.resolve_account(session, TOKEN, "semyon")


async def test_profile_fields(graph):
    async with aiohttp.ClientSession() as session:
        assert await ig.fetch_instagram_profile(session, TOKEN, USER_ID) == {
            "username": "semyon", "name": "Семён", "biography": "о себе", "media": "56",
        }
        # No token / a dead token: nothing to compare, but not «unreachable».
        assert await ig.fetch_instagram_profile(session, None, USER_ID) == {}
        graph["status"] = 190
        assert await ig.fetch_instagram_profile(session, TOKEN, USER_ID) == {}
        graph["status"] = 500
        assert await ig.fetch_instagram_profile(session, TOKEN, USER_ID) is None


# --- the connector ---------------------------------------------------------------

async def _collect(config, db):
    async with aiohttp.ClientSession() as session:
        return await BY_ID["instagram"].collect(Context(FakeBot(), session, config, db))


async def test_connector_flags(graph, config, db):
    assert BY_ID["instagram"].enabled(config) and BY_ID["instagram"].target(config) == "@semyon"
    snap = await _collect(config, db)
    assert snap.count is None and not snap.error and snap.flags == {"instagram_token_missing": True}

    await ig.store_token(db, TOKEN, USER_ID)
    snap = await _collect(config, db)
    assert (snap.count, snap.source, snap.flags) == (1234, "api", {})

    graph["status"] = 190
    snap = await _collect(config, db)
    assert snap.count is None and not snap.error and snap.flags == {"instagram_token_expired": True}

    graph["status"] = 500
    snap = await _collect(config, db)
    assert snap.count is None and snap.error


async def test_an_env_token_looks_its_account_up_once(graph, db):
    config = dataclasses.replace(Config.from_env(), instagram_username="semyon", instagram_access_token=TOKEN)
    snap = await _collect(config, db)
    assert snap.count == 1234 and await db.get_setting(ig.USER_ID_KEY) == USER_ID
    await _collect(config, db)
    assert [c[0] for c in graph["calls"]] == ["assigned", "user", "user"]

    # The token was granted for another account: a failure, not a skip.
    await db.set_setting(ig.USER_ID_KEY, "")
    graph["assigned"] = [{"id": "1", "username": "other"}]
    snap = await _collect(config, db)
    assert snap.count is None and snap.error


async def test_a_changed_username_is_resolved_again(graph, db):
    """INSTAGRAM_USERNAME changed in .env: the stored id is another account's, so it is looked up anew."""
    config = dataclasses.replace(Config.from_env(), instagram_username="semyon", instagram_access_token=TOKEN)
    await _collect(config, db)
    assert await db.get_setting(ig.USERNAME_KEY) == "semyon"
    graph["assigned"] = [{"id": USER_ID, "username": "semyon"}, {"id": "2", "username": "other"}]
    snap = await _collect(dataclasses.replace(config, instagram_username="Other"), db)
    assert (await db.get_setting(ig.USER_ID_KEY), await db.get_setting(ig.USERNAME_KEY)) == ("2", "other")
    assert [c[0] for c in graph["calls"]].count("assigned") == 2
    assert snap.count is None and snap.error            # the fake Graph serves USER_ID only


async def test_profile_monitor_watches_instagram(graph, config, db):
    config = dataclasses.replace(config, telegram_channel_id=None, youtube_api_key=None)  # Instagram alone
    await ig.store_token(db, TOKEN, USER_ID)
    bot = FakeBot()
    async with aiohttp.ClientSession() as session:
        assert await profile.check(bot, config, db, session) == 0  # baseline
        graph["user"]["biography"] = "crypto giveaway https://evil.example"
        graph["user"]["media_count"] = 10
        assert await profile.check(bot, config, db, session) == 1
    alert = bot.messages[-1]
    assert "🔴 Instagram: похоже на взлом — описание профиля" in alert and "hxxps://evil[.]example" in alert
    assert "публикаций: было 56, стало 10" in alert


# --- what the user sees ---------------------------------------------------------------

async def test_report_and_status_lines(config, db, insert):
    text, _ = await build_report(db, errors={"instagram_token_missing": True}, platforms=["instagram"])
    assert "токена нет — пришли его через /igtoken" in text and "Instagram — пока нет данных: нужен токен" in text
    text, _ = await build_report(db, errors={"instagram_token_expired": True}, platforms=["instagram"])
    assert "Instagram отклонил токен" in text

    items = {i["name"]: i for i in (await tofs_status.build(db, config, {"instagram_token_missing": True}))["items"]}
    assert items["Instagram"]["level"] == "warning" and items["Instagram"]["text"] == "нет токена — пришли его через /igtoken"
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


async def test_connections_and_instagram_screen(config, db):
    screen = await ui.connections(db, config)
    assert "📸 Instagram" in [b.text for row in screen.keyboard.inline_keyboard for b in row]
    assert "Instagram — @semyon · 🟠 нужен токен" in screen.text
    screen = await ui.instagram(db, config)
    assert "Аккаунт: @semyon" in screen.text and "Токена нет" in screen.text
    await ig.store_token(db, TOKEN, USER_ID)
    screen = await ui.instagram(db, config)
    assert "задан 0 дн. назад и бессрочный" in screen.text


async def test_igtoken_command(graph, make_update, make_context, db):
    update = make_update()
    await handlers.cmd_igtoken(update, make_context("short"))
    assert update.message.deleted and "слишком короткое" in update.effective_chat.sent[-1]

    graph["assigned"] = [{"id": "1", "username": "someone_else"}]
    update = make_update()
    await handlers.cmd_igtoken(update, make_context(TOKEN))
    assert "токен выдан не для @semyon" in update.effective_chat.sent[-1]
    assert await db.get_setting(ig.TOKEN_KEY) is None

    graph["assigned"] = [{"id": USER_ID, "username": "Semyon"}]
    graph["user"]["username"] = "Semyon"
    await db.set_setting("instagram_token_alerted", "1")
    update = make_update()
    await handlers.cmd_igtoken(update, make_context(TOKEN))
    assert update.message.deleted and "✅ Токен сохранён" in update.effective_chat.sent[-1]
    assert "@Semyon, 1 234 подписчиков" in update.effective_chat.sent[-1]
    assert await db.get_setting(ig.TOKEN_KEY) == TOKEN and await db.get_setting(ig.USER_ID_KEY) == USER_ID
    assert await db.get_setting("instagram_token_alerted") == "0"
    assert (await db.get_latest("instagram"))["count"] == 1234

    graph["status"] = 190
    update = make_update()
    await handlers.cmd_igtoken(update, make_context("EAAdead" + "z" * 100))
    assert "Instagram отклонил токен" in update.effective_chat.sent[-1]
    assert await db.get_setting(ig.TOKEN_KEY) == TOKEN  # the working one stays


async def test_token_stays_out_of_backups(db, tmp_path):
    await ig.store_token(db, TOKEN, USER_ID)
    await db.snapshot_without_secrets(str(tmp_path / "copy.db"))
    with sqlite3.connect(tmp_path / "copy.db") as conn:
        keys = {k for (k,) in conn.execute("SELECT key FROM settings")}
    assert ig.TOKEN_KEY not in keys and ig.USER_ID_KEY in keys


def test_security_mail_from_instagram_links_the_connector():
    assert ("instagram.com", "Instagram", "instagram") in mail.SENDERS

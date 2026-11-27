"""Instagram: the official API behind a system-user token of the owner's Meta app."""

import dataclasses
import logging
import sqlite3
from datetime import UTC, datetime, timedelta

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
from bot.scheduler import CollectOutcome, get_report_tz

TOKEN = "EAAB" + "x" * 150
USER_ID = "17841400000000000"
USER = {"id": USER_ID, "username": "semyon", "name": "Семён", "biography": "о себе",
        "website": "https://s.morgunov.tech/", "followers_count": 1234, "media_count": 56}


@pytest.fixture
def config(tmp_path) -> Config:
    return dataclasses.replace(Config.from_env(), db_path=str(tmp_path / "followers.db"), instagram_username="semyon")


@pytest.fixture
async def graph(monkeypatch):
    """A stand-in for graph.facebook.com: `state` controls what it answers."""
    state = {"user": dict(USER), "status": 200, "assigned": [{"id": USER_ID, "username": "semyon"}], "calls": [],
             # debug_token's answer: a token without a term, as Meta's default configuration issues.
             "debug": {"data": {"app_id": "1", "is_valid": True, "expires_at": 0, "data_access_expires_at": 0}},
             "debug_status": 200}

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

    async def debug_token(request):
        state["calls"].append(("debug", request.query.get("input_token") == request.query.get("access_token")))
        return web.json_response(state["debug"], status=state["debug_status"])

    app = web.Application()
    app.router.add_get("/me/assigned_instagram_accounts", assigned)
    app.router.add_get("/me", me)
    app.router.add_get("/debug_token", debug_token)  # before /{id}, which would take it
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
            "username": "semyon", "name": "Семён", "biography": "о себе", "website": "https://s.morgunov.tech/",
            "media": "56",
        }
        # No token / a dead token: nothing to compare, but not «unreachable».
        assert await ig.fetch_instagram_profile(session, None, USER_ID) == {}
        graph["status"] = 190
        assert await ig.fetch_instagram_profile(session, TOKEN, USER_ID) == {}
        graph["status"] = 500
        assert await ig.fetch_instagram_profile(session, TOKEN, USER_ID) is None


def _stamp(days: float) -> int:
    return int((utcnow() + timedelta(days=days)).timestamp())


async def test_token_expiry_reads_debug_token(graph):
    async with aiohttp.ClientSession() as session:
        assert await ig.token_expiry(session, TOKEN) == ig.NEVER
        assert graph["calls"] == [("debug", True)]  # the token inspects itself: the bot has no app token

        at = _stamp(60)
        graph["debug"] = {"data": {"is_valid": True, "expires_at": at, "data_access_expires_at": 0}}
        assert await ig.token_expiry(session, TOKEN) == datetime.fromtimestamp(at, UTC).isoformat()
        # Data access that ends first ends the reading first.
        early = _stamp(20)
        graph["debug"] = {"data": {"is_valid": True, "expires_at": at, "data_access_expires_at": early}}
        assert await ig.token_expiry(session, TOKEN) == datetime.fromtimestamp(early, UTC).isoformat()
        graph["debug"] = {"data": {"is_valid": True, "expires_at": 0, "data_access_expires_at": early}}
        assert await ig.token_expiry(session, TOKEN) == datetime.fromtimestamp(early, UTC).isoformat()


@pytest.mark.parametrize("answer", [
    # Meta won't let the token inspect itself: an OAuthException that is not a dead token.
    ({"error": {"message": "(#100) You must provide an app access token", "type": "OAuthException", "code": 100}}, 400),
    ({"data": {"is_valid": False, "expires_at": 0}}, 200),
    ({"data": {"is_valid": True}}, 200),
    ({"unexpected": True}, 200),
    ("not json", 502),
])
async def test_token_expiry_unknown_is_none_never_an_auth_error(graph, caplog, answer):
    graph["debug"], graph["debug_status"] = answer
    caplog.set_level(logging.INFO, logger="bot.platforms.instagram")
    async with aiohttp.ClientSession() as session:
        assert await ig.token_expiry(session, TOKEN) is None
    assert TOKEN not in caplog.text


async def test_token_expiry_survives_an_unreachable_meta(monkeypatch):
    monkeypatch.setattr(ig, "_GRAPH_URL", "http://127.0.0.1:9")  # nothing listens there
    async with aiohttp.ClientSession() as session:
        assert await ig.token_expiry(session, TOKEN) is None


def test_days_left_rounds_up():
    assert ig.days_left(utcnow() + timedelta(hours=1)) == 1
    assert ig.days_left(utcnow() + timedelta(days=7)) == 7
    assert ig.days_left(utcnow() - timedelta(days=1)) == 0


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


async def test_the_collect_keeps_the_expiry_and_warns_a_week_ahead(graph, config, db):
    await ig.store_token(db, TOKEN, USER_ID)
    assert await ig.get_expiry(db) is None                   # stored, not yet asked
    snap = await _collect(config, db)
    assert snap.flags == {} and await ig.get_expiry(db) == ig.NEVER

    graph["debug"] = {"data": {"is_valid": True, "expires_at": _stamp(30)}}
    snap = await _collect(config, db)
    assert snap.flags == {} and isinstance(await ig.get_expiry(db), datetime)

    graph["debug"] = {"data": {"is_valid": True, "expires_at": _stamp(6.5)}}
    snap = await _collect(config, db)
    assert snap.count == 1234 and snap.flags == {"instagram_token_expiring": 7}

    # Meta stops saying: the old date is not kept, and nothing is flagged.
    graph["debug_status"], graph["debug"] = 400, {"error": {"type": "OAuthException", "code": 100}}
    snap = await _collect(config, db)
    assert snap.count == 1234 and snap.flags == {} and await ig.get_expiry(db) is None

    # A dead token is the collect's to report; debug_token is not asked.
    graph["status"], graph["calls"] = 190, []
    snap = await _collect(config, db)
    assert snap.flags == {"instagram_token_expired": True} and "debug" not in [c[0] for c in graph["calls"]]


async def test_a_new_token_forgets_the_old_ones_date(db):
    await db.set_setting(ig.EXPIRES_KEY, (utcnow() + timedelta(days=2)).isoformat())
    await ig.store_token(db, TOKEN, USER_ID)
    assert await ig.get_expiry(db) is None


async def test_an_env_token_looks_its_account_up_once(graph, db):
    config = dataclasses.replace(Config.from_env(), instagram_username="semyon", instagram_access_token=TOKEN)
    snap = await _collect(config, db)
    assert snap.count == 1234 and await db.get_setting(ig.USER_ID_KEY) == USER_ID
    await _collect(config, db)
    assert [c[0] for c in graph["calls"]] == ["assigned", "user", "debug", "user", "debug"]

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

    text, _ = await build_report(db, errors={"instagram_token_expiring": 3}, platforms=["instagram"])
    assert "🟠 Токен Instagram истекает через 3 дн. — пришли новый через /igtoken" in text
    insert("instagram", 1234, 0)
    items = {i["name"]: i for i in (await tofs_status.build(db, config, {"instagram_token_expiring": 3}))["items"]}
    assert items["Instagram"]["level"] == "warning" and items["Instagram"]["text"] == "1\xa0234 — токен истекает через 3 дн."


async def test_collection_alerts_once_until_a_token_works(db):
    missing = CollectOutcome(report="", has_change=False, errors={"instagram_token_missing": True})
    assert any("токена нет" in line for line in await collection.alert_lines(db, missing))
    assert await collection.alert_lines(db, missing) == []
    ok = CollectOutcome(report="", has_change=False, collected={"instagram": (1234, "api")})
    assert await collection.alert_lines(db, ok) == []
    dead = CollectOutcome(report="", has_change=False, errors={"instagram_token_expired": True})
    assert any("отклонил токен" in line for line in await collection.alert_lines(db, dead))


async def test_expiring_token_alerts_once_per_token(db):
    await db.set_setting(ig.EXPIRES_KEY, datetime(2026, 12, 3, 12, tzinfo=UTC).isoformat())
    soon = CollectOutcome(report="", has_change=False, errors={"instagram_token_expiring": 6},
                          collected={"instagram": (1234, "api")})
    lines = await collection.alert_lines(db, soon)
    assert len(lines) == 1 and lines[0].startswith("🟠 Токен Instagram истекает через 6 дн. — пришли новый через /igtoken")
    assert "Generate token" in lines[0] and "debug_token: действует до 03.12.2026" in lines[0]
    soon.errors["instagram_token_expiring"] = 5
    assert await collection.alert_lines(db, soon) == []      # once, not daily
    # A token that works past the window re-arms it.
    ok = CollectOutcome(report="", has_change=False, collected={"instagram": (1234, "api")})
    assert await collection.alert_lines(db, ok) == []
    assert await db.get_setting(ig.EXPIRY_ALERTED_KEY) == "0"
    assert len(await collection.alert_lines(db, soon)) == 1


async def test_connections_and_instagram_screen(config, db):
    screen = await ui.connections(db, config)
    assert "📸 Instagram" in [b.text for row in screen.keyboard.inline_keyboard for b in row]
    assert "Instagram — @semyon · 🟠 нужен токен" in screen.text
    screen = await ui.instagram(db, config)
    assert "Аккаунт: @semyon" in screen.text and "Токена нет" in screen.text
    await ig.store_token(db, TOKEN, USER_ID)
    screen = await ui.instagram(db, config)
    assert "задан 0 дн. назад." in screen.text and "бессрочный:" not in screen.text
    assert "Срок токена Meta мне не сообщила" in screen.text

    await db.set_setting(ig.EXPIRES_KEY, ig.NEVER)
    assert "По данным Meta, срока у токена нет" in (await ui.instagram(db, config)).text

    tz = await get_report_tz(db, config)  # the screen dates are in the owner's zone
    later = (utcnow() + timedelta(days=40)).astimezone(tz)
    await db.set_setting(ig.EXPIRES_KEY, later.isoformat())
    text = (await ui.instagram(db, config)).text
    assert f"Действует до {later.strftime('%d.%m.%Y')}" in text and "продлить токен сам я не могу" in text
    assert "🟠" not in (await ui.connections(db, config)).text.split("Instagram — @semyon")[1].split("\n")[0]

    soon = (utcnow() + timedelta(days=3)).astimezone(tz)
    await db.set_setting(ig.EXPIRES_KEY, soon.isoformat())
    text = (await ui.instagram(db, config)).text
    assert f"🟠 Токен истекает {soon.strftime('%d.%m.%Y')}" in text and "✅" not in text
    assert f"Instagram — @semyon · 🟠 токен истекает {soon.strftime('%d.%m')}" in (await ui.connections(db, config)).text


async def test_igtoken_command(graph, config, make_update, make_context, db):
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
    assert await ig.get_expiry(db) == ig.NEVER and "По данным Meta, срока у токена нет" in update.effective_chat.sent[-1]

    # A token with a term: its date is on the screen at once, and the week-ahead alert is re-armed.
    at = _stamp(59.5)
    graph["debug"] = {"data": {"is_valid": True, "expires_at": at}}
    await db.set_setting(ig.EXPIRY_ALERTED_KEY, "1")
    update = make_update()
    await handlers.cmd_igtoken(update, make_context(TOKEN))
    date = datetime.fromtimestamp(at, await get_report_tz(db, config)).strftime("%d.%m.%Y")
    assert f"Действует до {date}" in update.effective_chat.sent[-1]
    assert await db.get_setting(ig.EXPIRY_ALERTED_KEY) == "0"

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
    # The date stays: it is not a secret, and a restore brings it only with a live token (db._SECRET_KEYS).


def test_security_mail_from_instagram_links_the_connector():
    assert ("instagram.com", "Instagram", "instagram") in mail.SENDERS

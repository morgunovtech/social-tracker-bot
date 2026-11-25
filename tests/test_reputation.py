"""The weekly reputation report (bot/reputation/): the sources against local
servers that play Google, Yandex, Cloudflare and Bing, the report and its
silence, the keys from the chat."""

from __future__ import annotations

import base64
import dataclasses
import json
from datetime import UTC, date, datetime, timedelta

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from conftest import buttons
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from bot import monitors, reputation, ui
from bot.db import utcnow
from bot.reputation import google
from bot.reputation.base import Failure, Week


def _unb64(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


@pytest.fixture(scope="module")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
async def gsc(rsa_key, monkeypatch):
    """Google's token endpoint and Search Console API: the JWT's signature is
    checked with the key's public half; .queries is what each query asked."""
    state = {"token_status": 200, "sites": ["sc-domain:morgunov.tech", "https://foundyou.morgunov.tech/"],
             "rows": {}, "bodies": []}

    async def token(request):
        form = await request.post()
        assert form["grant_type"] == "urn:ietf:params:oauth:grant-type:jwt-bearer"
        head, claims, signature = form["assertion"].split(".")
        rsa_key.public_key().verify(_unb64(signature), f"{head}.{claims}".encode(), padding.PKCS1v15(), hashes.SHA256())
        payload = json.loads(_unb64(claims))
        assert payload["scope"] == google.SCOPE and payload["iss"] == "bot@project.iam.gserviceaccount.com"
        if state["token_status"] != 200:
            return web.json_response({"error": "invalid_grant"}, status=state["token_status"])
        return web.json_response({"access_token": "ya29.test", "expires_in": 3600})

    async def sites(request):
        assert request.headers["Authorization"] == "Bearer ya29.test"
        return web.json_response({"siteEntry": [{"siteUrl": s, "permissionLevel": "siteRestrictedUser"}
                                                for s in state["sites"]]})

    async def query(request):
        body = await request.json()
        state["bodies"].append((request.match_info["site"], body))
        return web.json_response({"rows": state["rows"].get(request.match_info["site"], [])})

    app = web.Application()
    app.router.add_post("/token", token)
    app.router.add_get("/webmasters/v3/sites", sites)
    app.router.add_post("/webmasters/v3/sites/{site}/searchAnalytics/query", query)
    server = TestServer(app)
    await server.start_server()
    monkeypatch.setattr(google, "API", str(server.make_url("/webmasters/v3")))
    pem = rsa_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()).decode()
    key = json.dumps({"type": "service_account", "client_email": "bot@project.iam.gserviceaccount.com",
                      "private_key": pem, "token_uri": str(server.make_url("/token")), "project_id": "p"})
    yield state, key
    await server.close()


def test_brand_words_and_the_regex():
    words = reputation.parse_words("Семён Моргунов, FoundYou; good pass\nfoundyou, x")
    assert words == ["семён моргунов", "foundyou", "good pass"]
    assert google.brand_regex(words) == r"(?i)(семён\s*моргунов|foundyou|good\s*pass)"


def test_a_key_is_a_service_account_key_or_nothing():
    assert google.parse_key('{"type": "authorized_user", "client_email": "a", "private_key": "b"}') is None
    assert google.parse_key("not json") is None
    assert google.parse_key('{"type": "service_account", "client_email": "a", "private_key": "b"}')["token_uri"] \
        == google.TOKEN_URL


async def test_google_sums_brand_queries_over_every_property(gsc):
    state, key = gsc
    state["rows"] = {
        "sc-domain:morgunov.tech": [{"keys": ["good pass"], "impressions": 40, "clicks": 3},
                                    {"keys": ["семён моргунов"], "impressions": 12, "clicks": 2}],
        "https://foundyou.morgunov.tech/": [{"keys": ["foundyou"], "impressions": 30, "clicks": 3}],
    }
    async with aiohttp.ClientSession() as session:
        week = await google.week(session, key, ["foundyou", "good pass"], date(2026, 11, 15), date(2026, 11, 21))
    assert (week.total, week.clicks, week.places) == (82, 8, 2)
    assert week.top(2) == [("good pass", 40), ("foundyou", 30)]
    site, body = state["bodies"][0]
    assert site == "sc-domain:morgunov.tech"
    assert body["startDate"] == "2026-11-15" and body["endDate"] == "2026-11-21" and body["dimensions"] == ["query"]
    assert body["dimensionFilterGroups"][0]["filters"][0] == {
        "dimension": "query", "operator": "includingRegex", "expression": "(?i)(foundyou|good\\s*pass)"}


async def test_google_check_says_what_the_key_sees(gsc):
    state, key = gsc
    async with aiohttp.ClientSession() as session:
        assert await google.check(session, key) == (None, "sc-domain:morgunov.tech, https://foundyou.morgunov.tech/")
        state["sites"] = []
        assert await google.check(session, key) == ("no_sites", "bot@project.iam.gserviceaccount.com")
        state["token_status"] = 400
        assert (await google.check(session, key))[0] == "rejected:400"
        assert await google.check(session, "{}") == ("key", "")


# --- the report ----------------------------------------------------------------

class FakeSource:
    """A source module: week() answers from .weeks by start date, or raises."""

    def __init__(self, weeks=None, error=None):
        self.weeks, self.error, self.calls = weeks or {}, error, []

    async def week(self, session, secret, words=None, start=None, end=None):
        self.calls.append((secret, words, start, end))
        if self.error:
            raise Failure(self.error)
        return self.weeks.get(start, Week()) if start else self.weeks.get("now", Week())

    async def check(self, session, secret):
        return (None, "seen") if secret != "bad" else ("rejected:401", "")


def _week(total, clicks=0, by=None, where=None):
    w = Week()
    for name, count in (by or {}).items():
        w.add(name, count)
    w.total, w.clicks = total, clicks
    for host, count in (where or {}).items():
        w.where[host] = count
    return w


@pytest.fixture
def sources(monkeypatch):
    fakes = {m: FakeSource() for m in reputation.BY_MONITOR}
    patched = tuple(dataclasses.replace(s, module=fakes[s.monitor]) for s in reputation.SOURCES)
    monkeypatch.setattr(reputation, "SOURCES", patched)
    monkeypatch.setattr(reputation, "BY_MONITOR", {s.monitor: s for s in patched})
    return fakes


async def _connect(db, *monitor_ids):
    for monitor_id in monitor_ids:
        await db.set_setting(monitors.BY_ID[monitor_id].secret, f"key-{monitor_id}")


async def test_the_report_says_what_the_sources_saw(bot, config, db, sources, insert):
    now = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    today = now.date()
    start, _, prev_start, _ = reputation.window(today)
    assert (start, prev_start) == (date(2026, 11, 15), date(2026, 11, 8))
    await _connect(db, "rep_google", "rep_ai")
    await db.set_setting(reputation.WORDS_KEY, "foundyou, good pass")
    sources["rep_google"].weeks = {start: _week(120, 8, {"good pass": 40, "foundyou": 30}),
                                   prev_start: _week(92, 5)}
    sources["rep_ai"].weeks = {start: _week(343, 0, {"ChatGPT-User": 200, "Perplexity-User": 100},
                                            {"foundyou.morgunov.tech": 250}), prev_start: _week(76)}
    # Dated from the same fixed day as the report: by the real clock a row «7 days ago»
    # lands on 18.11 after midnight UTC — past the baseline window of today − 7 days.
    insert("telegram", 1000, 7, now=now)
    insert("telegram", 1120, 0, now=now)
    async with aiohttp.ClientSession() as session:
        text, keep = await reputation.build(db, config, session, today)
    assert text.splitlines()[0] == "🔎 <b>Репутация за неделю</b> · 15.11–21.11"
    assert "🔍 Google: 120 показов, 8 кликов по брендовым запросам (+30 %) · «good pass» 40, «foundyou» 30" in text
    assert "🤖 ИИ-ассистенты открывали твои страницы 343 раза (+351 %) · ChatGPT-User 200, Perplexity-User 100 · " \
           "чаще всего — foundyou.morgunov.tech\n   подсчёт запросов по user-agent ИИ-ассистентов в Cloudflare, " \
           "не «AI Answer retrievals» из его панели" in text
    assert "👥 Подписчики: 1 120, +120 за неделю" in text
    assert "Яндекс" not in text                                            # not connected: not mentioned
    assert keep == {}
    assert sources["rep_google"].calls[0][:2] == ("key-rep_google", ["foundyou", "good pass"])


async def test_nothing_to_say_is_silence(bot, config, db, sources):
    await _connect(db, "rep_google")
    await db.set_setting(reputation.WORDS_KEY, "foundyou")
    assert await reputation.send(bot, config, db) is False
    assert bot.messages == [] and not await reputation.due(db)            # tried, a week until the next


async def test_a_failing_source_and_missing_words_are_said(bot, config, db, sources):
    await _connect(db, "rep_google", "rep_yandex", "rep_ai")
    sources["rep_ai"].error = "rejected:403"
    assert await reputation.send(bot, config, db)
    (text,) = bot.messages
    assert "⚠️ Google: не смог получить данные — не заданы брендовые слова" in text
    assert "⚠️ Cloudflare: не смог получить данные — отвечает ошибкой 403" in text
    assert buttons(bot.markups[0]) == {"open:rep": "🔎 Репутация"}


async def test_run_is_weekly_and_needs_a_source(bot, config, db, sources):
    assert await reputation.run(bot, config, db) is False                   # nothing connected
    await _connect(db, "rep_ai")
    sources["rep_ai"].weeks = {reputation.window(utcnow().date())[0]: _week(5)}
    assert await reputation.run(bot, config, db)
    assert await reputation.run(bot, config, db) is False                   # a week until the next
    await db.set_setting(reputation.SENT_KEY, (utcnow() - timedelta(days=7)).isoformat())
    await monitors.set_switch(db, "rep_ai", False)
    assert await reputation.run(bot, config, db) is False                   # switched off


async def test_the_screen_and_the_keys_from_the_chat(make_update, make_context, bot, config, db, sources):
    from bot import callbacks as cb
    from bot import handlers

    screen = await ui.reputation_screen(db, config)
    assert "🟠 Брендовые слова не заданы" in screen.text and "📨 Отчёт сейчас" not in str(screen.keyboard)
    # The words, then a key that the source refuses, then one it takes.
    context = make_context()
    update = make_update(callback=cb.REP_WORDS)
    assert await handlers.input_conv_start(update, context) == handlers.AWAITING_INPUT
    update = make_update(text="FoundYou, Good Pass")
    await handlers.input_conv_value(update, context)
    assert await db.get_setting(reputation.WORDS_KEY) == "foundyou, good pass"
    update = make_update(callback=cb.REP_KEYS["rep_ai"])
    await handlers.input_conv_start(update, context)
    update = make_update(text="bad")
    assert await handlers.input_conv_value(update, context) == handlers.AWAITING_INPUT
    assert update.message.deleted and await db.get_setting("rep_cloudflare_token") is None
    update = make_update(text="good-key")
    await handlers.input_conv_value(update, context)
    assert await db.get_setting("rep_cloudflare_token") == "good-key"
    assert any("✅ Cloudflare подключён: seen" in text for text in update.effective_chat.sent)
    screen = await ui.reputation_screen(db, config)
    assert "✅ ИИ-ассистенты — Cloudflare" in screen.text and "📨 Отчёт сейчас" in str(screen.keyboard)


async def test_the_keys_never_leave_in_a_backup(db, tmp_path):
    for key in ("rep_google_key", "rep_yandex_token", "rep_cloudflare_token"):
        await db.set_setting(key, "secret")
    path = str(tmp_path / "copy.db")
    await db.snapshot_without_secrets(path)
    import sqlite3

    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM settings WHERE key LIKE 'rep_%_key' OR key LIKE 'rep_%_token'"
                            ).fetchone()[0] == 0


# --- Yandex.Webmaster ------------------------------------------------------------

@pytest.fixture
async def webmaster(monkeypatch):
    from bot.reputation import yandex

    state = {"status": 200, "params": [],
             "queries": [{"query_id": str(i), "query_text": f"запрос {i}", "indicators": {"TOTAL_SHOWS": 5.0}}
                         for i in range(498)]}
    state["queries"] += [
        {"query_id": "a", "query_text": "FoundYou проверка фото", "indicators": {"TOTAL_SHOWS": 10.0, "TOTAL_CLICKS": 2.0}},
        {"query_id": "b", "query_text": "goodpass", "indicators": {"TOTAL_SHOWS": 4.0, "TOTAL_CLICKS": 1.0}},
        {"query_id": "c", "query_text": "семён моргунов", "indicators": {"TOTAL_SHOWS": 3.0}},
    ]

    async def user(request):
        assert request.headers["Authorization"] == "OAuth y0_token_value_long_enough"
        if state["status"] != 200:
            return web.json_response({"error_code": "INVALID_OAUTH_TOKEN"}, status=state["status"])
        return web.json_response({"user_id": 42})

    async def hosts(request):
        return web.json_response({"hosts": [
            {"host_id": "https:foundyou.morgunov.tech:443", "ascii_host_url": "https://foundyou.morgunov.tech/",
             "verified": True},
            {"host_id": "http:old.example:80", "verified": False},
        ]})

    async def popular(request):
        state["params"].append((request.match_info["host"], dict(request.query), request.query.getall("query_indicator")))
        offset, limit = int(request.query["offset"]), int(request.query["limit"])
        return web.json_response({"queries": state["queries"][offset:offset + limit], "count": len(state["queries"])})

    app = web.Application()
    app.router.add_get("/v4/user", user)
    app.router.add_get("/v4/user/42/hosts", hosts)
    app.router.add_get("/v4/user/42/hosts/{host}/search-queries/popular", popular)
    server = TestServer(app)
    await server.start_server()
    monkeypatch.setattr(yandex, "API", str(server.make_url("/v4")))
    yield state, yandex
    await server.close()


async def test_yandex_counts_brand_queries_of_verified_sites(webmaster):
    state, yandex = webmaster
    async with aiohttp.ClientSession() as session:
        week = await yandex.week(session, "y0_token_value_long_enough", ["foundyou", "good pass", "семён моргунов"],
                                 date(2026, 11, 15), date(2026, 11, 21))
        assert (week.total, week.clicks, week.places) == (17, 3, 1)
        assert week.top() == [("foundyou проверка фото", 10), ("goodpass", 4), ("семён моргунов", 3)]
        host, params, indicators = state["params"][0]
        assert host == "https:foundyou.morgunov.tech:443"
        assert params["date_from"] == "2026-11-15" and params["date_to"] == "2026-11-21"
        assert params["order_by"] == "TOTAL_SHOWS" and indicators == ["TOTAL_SHOWS", "TOTAL_CLICKS"]
        assert [p[1]["offset"] for p in state["params"]] == ["0", "500"]          # the second page, then stop
        assert await yandex.check(session, "y0_token_value_long_enough") == (None, "https://foundyou.morgunov.tech/")
        state["status"] = 401
        assert (await yandex.check(session, "y0_token_value_long_enough"))[0] == "rejected:401"
        assert await yandex.check(session, "short") == ("key", "")


# --- Cloudflare --------------------------------------------------------------------

@pytest.fixture
async def cloudflare_api(monkeypatch):
    from bot.reputation import cloudflare

    state = {"asked": [], "errors": None, "counts": {"ChatGPT-User": 3, "Perplexity-User": 1}}

    async def zones(request):
        assert request.headers["Authorization"].startswith("Bearer ")
        return web.json_response({"success": True, "result": [{"id": "z1", "name": "morgunov.tech"}]})

    async def graphql(request):
        body = await request.json()
        variables = body["variables"]
        state["asked"].append(variables)
        if state["errors"]:
            return web.json_response({"data": None, "errors": [{"message": state["errors"]}]})
        agent = variables["agent"].strip("%")
        n = state["counts"].get(agent, 0)
        groups = [{"count": n, "dimensions": {"clientRequestHTTPHost": "foundyou.morgunov.tech"}}] if n else []
        return web.json_response({"data": {"viewer": {"zones": [{"httpRequestsAdaptiveGroups": groups}]}},
                                  "errors": None})

    app = web.Application()
    app.router.add_get("/client/v4/zones", zones)
    app.router.add_post("/client/v4/graphql", graphql)
    server = TestServer(app)
    await server.start_server()
    monkeypatch.setattr(cloudflare, "API", str(server.make_url("/client/v4")))
    monkeypatch.setattr(cloudflare, "PAUSE", 0)
    yield state, cloudflare
    await server.close()


async def test_cloudflare_counts_ai_assistants_by_user_agent_and_day(cloudflare_api):
    state, cloudflare = cloudflare_api
    token = "t" * 40
    async with aiohttp.ClientSession() as session:
        week = await cloudflare.week(session, token, None, date(2026, 11, 15), date(2026, 11, 21), pause=0)
        assert (week.total, week.places) == (7 * 4, 1)
        assert week.top() == [("ChatGPT-User", 21), ("Perplexity-User", 7)]
        assert week.top(1, "where") == [("foundyou.morgunov.tech", 28)]
        assert len(state["asked"]) == len(cloudflare.AGENTS) * 7                 # one agent, one day per query
        first = state["asked"][0]
        assert (first["zone"], first["agent"], first["since"], first["until"]) == (
            "z1", "%ChatGPT-User%", "2026-11-15T00:00:00Z", "2026-11-16T00:00:00Z")
        assert await cloudflare.check(session, token) == (None, "morgunov.tech")
        state["errors"] = "zone does not have access to the path"
        assert await cloudflare.check(session, token) == ("not_available", "")  # said at connection, not in a week
        with pytest.raises(Failure):
            await cloudflare.week(session, token, None, date(2026, 11, 15), date(2026, 11, 15), pause=0)

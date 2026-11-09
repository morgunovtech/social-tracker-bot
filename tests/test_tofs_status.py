"""The lines this bot sends to the TofsDevOps main screen: one per network,
«is the channel there, is it read, are people coming»."""

import dataclasses

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from bot import scheduler, tofs_status

NBSP = " "


@pytest.fixture
async def tofs():
    """A stand-in for TofsDevOps: records marks and statuses; /bad refuses
    any status with 400 the way a format mismatch would."""
    received: list[dict] = []

    async def heartbeat(request):
        body = await request.json() if request.method == "POST" else None
        received.append({"method": request.method, "body": body})
        if request.match_info["job"] == "bad" and request.method == "POST":
            return web.Response(status=400, text="bad status: items[0].level")
        return web.Response(text="ok")

    app = web.Application()
    app.router.add_route("*", "/api/heartbeat/{secret}/{job}", heartbeat)
    server = TestServer(app)
    await server.start_server()
    yield server, received
    await server.close()


def _by_name(payload: dict) -> dict[str, dict]:
    return {i["name"]: i for i in payload["items"]}


async def test_a_line_per_network_says_how_it_is(config, db, insert):
    insert("telegram", 12322, days_ago=1)
    insert("telegram", 12340)
    insert("linkedin", 4520, days_ago=10, source="manual")
    payload = await tofs_status.build(db, config, {}, "social_tracker_bot")
    assert payload["title"] == "📣 Соцсети" and payload["open_url"] == "https://t.me/social_tracker_bot"
    items = _by_name(payload)
    assert list(items) == ["Telegram", "YouTube", "LinkedIn"]
    assert items["Telegram"] == {"name": "Telegram", "level": "ok", "text": f"12{NBSP}340, +18 за сутки"}
    assert items["YouTube"]["level"] == "unknown" and items["YouTube"]["text"] == "пока нет данных"
    assert items["LinkedIn"]["level"] == "warning" and "введено вручную 10 дн. назад" in items["LinkedIn"]["text"]


async def test_problems_are_lines_too(config, db, insert):
    insert("telegram", 12400, days_ago=1)
    insert("telegram", 12000)
    insert("youtube", 1200, days_ago=3)
    await db.set_setting("profile_fail_linkedin", "3")
    items = _by_name(await tofs_status.build(db, config, {"youtube": True}))
    assert items["Telegram"]["level"] == "warning" and f"{chr(0x2212)}400 за сутки" in items["Telegram"]["text"]
    # A small daily dip is not a problem: the same bar as the drop alert.
    await db.upsert("telegram", 11998)                                   # one row per day: update today
    items = _by_name(await tofs_status.build(db, config, {}))
    assert items["Telegram"]["level"] == "warning"                      # still −402 vs yesterday
    insert("youtube", 1159, days_ago=1)
    insert("youtube", 1157)
    assert _by_name(await tofs_status.build(db, config, {}))["YouTube"] == {
        "name": "YouTube", "level": "ok", "text": f"1{NBSP}157, {chr(0x2212)}2 за сутки"}
    assert items["YouTube"]["level"] == "warning" and "свежие данные собрать не удаётся" in items["YouTube"]["text"]
    assert items["LinkedIn"]["level"] == "critical" and "профиль не читается" in items["LinkedIn"]["text"]
    assert "open_url" not in await tofs_status.build(db, config, {})

    # Between two collections the last one's problems are remembered.
    await db.set_setting("profile_fail_linkedin", "0")
    await tofs_status.remember_errors(db, {"linkedin_cookie_expired": True})
    items = _by_name(await tofs_status.build(db, config))
    assert items["LinkedIn"] == {"name": "LinkedIn", "level": "warning", "text": "cookie истёк — обнови через /setcookie"}


async def test_the_daily_mark_carries_the_lines(config, db, insert, tofs):
    server, received = tofs
    insert("telegram", 12340)
    cfg = dataclasses.replace(config, healthcheck_url=str(server.make_url("/api/heartbeat/s3cr3t/socialtracker")))
    await scheduler._ping_healthcheck(cfg, db, None, {})
    assert received[-1]["method"] == "POST" and received[-1]["body"]["heartbeat"] is True
    assert _by_name(received[-1]["body"])["Telegram"]["level"] == "ok"


async def test_a_refused_status_does_not_cost_the_mark(config, db, insert, tofs, caplog):
    server, received = tofs
    insert("telegram", 12340)
    payload = await tofs_status.build(db, config, {})
    url = str(server.make_url("/api/heartbeat/s3cr3t/bad"))
    assert await tofs_status.send(url, payload, mark=True)
    assert [r["method"] for r in received] == ["POST", "GET"]            # the plain mark still went out
    assert "refused the status: HTTP 400" in caplog.text
    received.clear()
    assert not await tofs_status.send(url, payload, mark=False)          # a status-only update has no fallback
    assert [r["method"] for r in received] == ["POST"]


async def test_the_profile_check_refreshes_the_lines_without_a_mark(bot, config, db, insert, tofs, monkeypatch):
    server, received = tofs

    async def check(*args):
        return 0

    monkeypatch.setattr(scheduler.profile, "check", check)
    await scheduler._profile_job(bot, config, db)                         # no TofsDevOps address: nothing sent
    assert received == []
    cfg = dataclasses.replace(config, healthcheck_url=str(server.make_url("/api/heartbeat/s3cr3t/socialtracker")))
    insert("telegram", 12340)
    await scheduler._profile_job(bot, cfg, db)
    assert received[-1]["method"] == "POST" and received[-1]["body"]["heartbeat"] is False

import dataclasses
import json
from datetime import UTC, datetime, timedelta

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from bot import updates
from bot.updates import (
    DEPLOY_ALERTED_KEY,
    SNAPSHOT_KEY,
    installed_versions,
    is_major_bump,
    report_startup_changes,
    run_dependency_watch,
    run_deploy_watch,
    short_bump,
)

RUNNING = "aaaaaaa1111111"
HEAD = "bbbbbbb2222222"


@pytest.fixture
def watch_config(config):
    return dataclasses.replace(config, update_watch=True, app_commit=RUNNING[:12], repo_slug="me/bot")


# --- startup -----------------------------------------------------------------

def test_installed_versions():
    versions = installed_versions()
    assert {"python-telegram-bot", "aiohttp", "matplotlib"} <= set(versions)


async def test_startup_notice_only_on_change(bot, watch_config, db):
    assert await report_startup_changes(bot, watch_config, db) == []        # first boot: snapshot only
    assert await report_startup_changes(bot, watch_config, db) == []        # nothing changed
    assert bot.messages == []

    snapshot = json.loads(await db.get_setting(SNAPSHOT_KEY))
    snapshot["packages"]["aiohttp"] = "3.14.3"
    snapshot["commit"] = "0cccc5f00000"
    await db.set_setting(SNAPSHOT_KEY, json.dumps(snapshot))

    await report_startup_changes(bot, watch_config, db)
    text = bot.messages[-1]
    assert text.startswith("🔄 Бот обновился:")
    assert "сборка 0cccc5f → aaaaaaa" in text and "aiohttp 3.14.3 →" in text


async def test_startup_notice_survives_a_corrupt_snapshot(bot, watch_config, db):
    await db.set_setting(SNAPSHOT_KEY, "{not json")
    assert await report_startup_changes(bot, watch_config, db) == []
    assert json.loads(await db.get_setting(SNAPSHOT_KEY))["commit"] == RUNNING[:12]


def test_bump_titles():
    assert is_major_bump("Bump aiohttp from 3.14.4 to 4.0.0")
    assert not is_major_bump("Bump aiohttp from 3.14.3 to 3.14.4")
    assert not is_major_bump("Bump the python-deps group with 3 updates")
    assert short_bump("Bump aiohttp from 3.14.4 to 4.0.0") == "aiohttp 3.14.4→4.0.0"


# --- a fake GitHub + OSV -----------------------------------------------------

@pytest.fixture
async def github(monkeypatch):
    """Local stand-in for api.github.com and OSV; tests edit `state`."""
    state = {
        "head": HEAD,
        "deploy_state": "failure",
        "pulls": [],
        "vulns": {},
        "down": False,
    }

    async def commit(request):
        if state["down"]:
            return web.Response(status=403)
        return web.json_response({
            "sha": state["head"],
            "html_url": f"https://github.com/me/bot/commit/{state['head']}",
            "commit": {"message": "bump things\n\nbody"},
        })

    async def deployments(request):
        return web.json_response([{"id": 7}] if request.query.get("sha") == state["head"] else [])

    async def statuses(request):
        return web.json_response([{"state": state["deploy_state"], "log_url": "https://railway.com/project/x"}])

    async def pulls(request):
        return web.json_response(state["pulls"])

    async def osv(request):
        names = [q["package"]["name"] for q in (await request.json())["queries"]]
        return web.json_response({"results": [
            {"vulns": [{"id": i} for i in state["vulns"].get(name, [])]} for name in names
        ]})

    app = web.Application()
    app.router.add_get("/repos/me/bot/commits/main", commit)
    app.router.add_get("/repos/me/bot/deployments", deployments)
    app.router.add_get("/repos/me/bot/deployments/7/statuses", statuses)
    app.router.add_get("/repos/me/bot/pulls", pulls)
    app.router.add_post("/osv", osv)
    server = TestServer(app)
    await server.start_server()
    monkeypatch.setattr(updates, "GITHUB_API", str(server.make_url("")).rstrip("/"))
    monkeypatch.setattr(updates, "OSV_BATCH", str(server.make_url("/osv")))
    yield state
    await server.close()


# --- hourly deploy watch -----------------------------------------------------

async def test_failed_deploy_is_alerted_once_per_commit(bot, watch_config, db, github):
    await run_deploy_watch(bot, watch_config, db)
    await run_deploy_watch(bot, watch_config, db)
    assert len(bot.messages) == 1
    assert "Новая версия бота не запустилась" in bot.messages[0] and "bbbbbbb" in bot.messages[0]
    assert await db.get_setting(DEPLOY_ALERTED_KEY) == "bbbbbbb"


@pytest.mark.parametrize(
    "change",
    [
        {"head": RUNNING},                # already running the newest commit
        {"deploy_state": "in_progress"},  # still deploying
        {"deploy_state": "success"},      # deployed; this instance is about to be replaced
        {"down": True},                   # GitHub did not answer: say nothing rather than guess
    ],
)
async def test_deploy_watch_stays_quiet(bot, watch_config, db, github, change):
    github.update(change)
    await run_deploy_watch(bot, watch_config, db)
    assert bot.messages == []


async def test_deploy_watch_needs_a_known_build(bot, config, db, github):
    await run_deploy_watch(bot, dataclasses.replace(config, update_watch=True, repo_slug="me/bot"), db)
    await run_deploy_watch(bot, dataclasses.replace(config, update_watch=False, app_commit=RUNNING), db)
    assert bot.messages == []


# --- weekly dependency watch -------------------------------------------------

def _pr(number, title, days_open):
    opened = (datetime.now(UTC) - timedelta(days=days_open)).isoformat().replace("+00:00", "Z")
    return {"number": number, "title": title, "created_at": opened, "user": {"login": "dependabot[bot]"},
            "html_url": f"https://github.com/me/bot/pull/{number}"}


async def test_vulnerabilities_alerted_once_and_when_gone(bot, watch_config, db, github):
    github["vulns"] = {"aiohttp": ["GHSA-1", "GHSA-2"]}
    await run_dependency_watch(bot, watch_config, db)
    await run_dependency_watch(bot, watch_config, db)
    assert len(bot.messages) == 1 and "aiohttp" in bot.messages[0] and "GHSA-1, GHSA-2" in bot.messages[0]

    github["vulns"] = {}
    await run_dependency_watch(bot, watch_config, db)
    assert bot.messages[-1] == "✅ Уязвимых зависимостей больше нет."
    await run_dependency_watch(bot, watch_config, db)
    assert len(bot.messages) == 2


async def test_prs_waiting_for_a_human(bot, watch_config, db, github):
    github["pulls"] = [
        _pr(10, "Bump aiohttp from 3.14.4 to 4.0.0", 0),          # major: never auto-merged
        _pr(11, "Bump the python-deps group with 2 updates", 3),  # minor, stuck: CI is red
        _pr(12, "Bump matplotlib from 3.11.1 to 3.11.2", 0),      # fresh minor: auto-merge will handle it
        {**_pr(13, "Fix typo", 9), "user": {"login": "someone"}},  # not Dependabot
    ]
    await run_dependency_watch(bot, watch_config, db)
    text = bot.messages[0]
    assert "Ждёт твоего решения: aiohttp 3.14.4→4.0.0" in text and "/pull/10" in text
    assert "тесты не прошли" in text and "/pull/11" in text
    assert "/pull/12" not in text and "/pull/13" not in text


async def test_dependency_watch_silent_when_healthy(bot, watch_config, db, github):
    await run_dependency_watch(bot, watch_config, db)
    assert bot.messages == []

"""Where the links in the profiles lead (bot/monitors/links.py), against a
local web server that plays every host."""

from __future__ import annotations

import json
from datetime import timedelta

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from bot import monitors, scheduler
from bot.db import utcnow
from bot.monitors import links
from bot.monitors.links import BROKEN, OK, REDIRECT, TECHNICAL, UNCHECKED, extract


def test_extract_finds_links_people_write():
    text = ("Сайт: s.morgunov.tech, пароли — https://good-pass.morgunov.tech/check. Канал t.me/morgunov, "
            "www.example.com/a?b=1 (и Node.js, README.md, s@morgunov.tech)")
    assert extract(text) == [
        "https://good-pass.morgunov.tech/check", "https://t.me/morgunov", "https://www.example.com/a?b=1",
        "https://s.morgunov.tech",
    ]
    assert extract("без ссылок") == []


@pytest.fixture
async def web_hosts(monkeypatch):
    """One server for every host: the Host header picks the answer."""
    answers: dict[str, tuple[int, str | None]] = {}

    async def handle(request):
        status, location = answers.get(request.host.split(":")[0], (200, None))
        return web.Response(status=status, headers={"Location": location} if location else None)

    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", handle)
    server = TestServer(app)
    await server.start_server()
    port = server.port

    real = links.follow

    async def public(host, port_):
        return True

    monkeypatch.setattr(links, "_public", public)

    class Session(aiohttp.ClientSession):
        """Sends every host to the local server, keeping its name in the Host header."""

        def _request(self, method, url, **kwargs):
            parts = links.urlsplit(str(url))
            if parts.hostname == "nxdomain.example":
                raise aiohttp.ClientConnectorError(None, OSError("no such host"))
            kwargs.setdefault("headers", {})
            kwargs["headers"] = {**kwargs["headers"], "Host": parts.hostname}
            local = f"http://127.0.0.1:{port}{parts.path or '/'}"
            return super()._request(method, local, **kwargs)

    yield answers, Session, real
    await server.close()


async def _check(Session, url):
    async with Session() as session:
        return (await links.check_links(session, [url], retry_after=0))[url]


async def test_follow_names_what_it_found(web_hosts):
    answers, Session, _ = web_hosts
    answers["morgunov.tech"] = (301, "https://s.morgunov.tech/")
    answers["gpass.morgunov.tech"] = (301, "https://good-pass.morgunov.tech/")
    answers["foundyou.pages.dev"] = (200, None)
    answers["gone.example"] = (404, None)
    answers["down.example"] = (502, None)
    answers["linkedin.com"] = (999, None)
    answers["www.youtube.com"] = (302, "https://consent.youtube.com/m?continue=x")
    answers["loop.example"] = (302, "https://loop.example/")
    assert (await _check(Session, "https://morgunov.tech")).state == REDIRECT
    assert (await _check(Session, "https://morgunov.tech")).final_host == "s.morgunov.tech"
    assert (await _check(Session, "https://gpass.morgunov.tech")).final_host == "good-pass.morgunov.tech"
    assert (await _check(Session, "https://s.morgunov.tech")).state == OK
    assert (await _check(Session, "https://foundyou.pages.dev")).state == TECHNICAL
    gone = await _check(Session, "https://gone.example/page")
    assert (gone.state, gone.tech) == (BROKEN, "HTTP 404") and "страница не найдена (404)" == gone.detail
    assert (await _check(Session, "https://down.example")).tech == "HTTP 502"
    assert (await _check(Session, "https://linkedin.com/in/x")).state == UNCHECKED     # refuses robots
    assert (await _check(Session, "https://www.youtube.com/@chan")).state == OK          # a consent page in front
    assert (await _check(Session, "https://loop.example")).tech == "redirect loop"
    assert (await _check(Session, "ftp://example.com")).state == UNCHECKED


async def test_internal_addresses_are_never_requested():
    async with aiohttp.ClientSession() as session:
        for url in ("http://127.0.0.1:1/x", "http://169.254.169.254/latest/meta-data", "http://10.0.0.1/"):
            assert (await links.follow(session, url)) == links.Result(UNCHECKED, tech="private address")


async def _profiles(db, description: str) -> None:
    await db.set_setting("profile_telegram", json.dumps({"title": "Канал", "description": description}))


async def test_weekly_check_tells_each_change_once(bot, config, db, web_hosts):
    answers, Session, _ = web_hosts
    answers["morgunov.tech"] = (301, "https://s.morgunov.tech/")
    answers["foundyou.pages.dev"] = (200, None)
    answers["gone.example"] = (404, None)
    await _profiles(db, "Сайт morgunov.tech · foundyou.pages.dev · https://gone.example/x · https://s.morgunov.tech")
    async with Session() as session:
        assert await links.check(bot, config, db, session, retry_after=0) == 2
    alert, notes = bot.messages
    assert alert.startswith("🟠 Telegram, описание канала: ссылка не открывается — страница не найдена (404)")
    assert "gone[.]example/x" in alert and "Тех.: HTTP 404 · проверка ссылок раз в неделю" in alert
    assert notes.startswith("ℹ️ Ссылки в профилях — можно лучше:")
    assert "morgunov[.]tech → s[.]morgunov[.]tech — ведёт через переадресацию" in notes
    assert "foundyou[.]pages[.]dev — ведёт на технический адрес" in notes
    assert "s.morgunov.tech —" not in notes                                 # a direct link is fine

    async with Session() as session:                                        # a week later, nothing changed
        assert await links.check(bot, config, db, session, retry_after=0) == 0
    answers["gone.example"] = (200, None)                                   # the page is back
    async with Session() as session:
        assert await links.check(bot, config, db, session, retry_after=0) == 1
    assert bot.messages[-1].startswith("✅ Telegram, описание канала: ссылка снова открывается — gone[.]example/x.")


async def test_a_dead_network_is_not_a_dead_site(bot, config, db, web_hosts):
    _, Session, _ = web_hosts
    await _profiles(db, "https://nxdomain.example/a https://nxdomain.example/b")
    async with Session() as session:
        assert await links.check(bot, config, db, session, retry_after=0) == 0
    assert bot.messages == [] and await links.due(db)                       # tried again tomorrow


async def test_a_site_that_refuses_robots_changes_nothing(bot, config, db, web_hosts):
    answers, Session, _ = web_hosts
    answers["gone.example"] = (404, None)
    await _profiles(db, "https://gone.example/x")
    async with Session() as session:
        await links.check(bot, config, db, session, retry_after=0)
    answers["gone.example"] = (403, None)                                   # now behind a bot wall
    async with Session() as session:
        assert await links.check(bot, config, db, session, retry_after=0) == 0
    assert json.loads(await db.get_setting(links.STATE_KEY))["https://gone.example/x"]["state"] == BROKEN


async def test_run_is_weekly_and_follows_the_switch(bot, config, db, monkeypatch):
    calls = []

    async def check(*args, **kwargs):
        calls.append(1)
        return 0

    monkeypatch.setattr(links, "check", check)
    await links.run(bot, config, db)
    assert calls == [1]                                                     # never checked: due now
    await db.set_setting(links.CHECKED_KEY, utcnow().isoformat())
    await links.run(bot, config, db)
    assert calls == [1]
    await db.set_setting(links.CHECKED_KEY, (utcnow() - timedelta(days=7)).isoformat())
    await monitors.set_switch(db, "links", False)
    await links.run(bot, config, db)
    assert calls == [1]
    await monitors.set_switch(db, "links", True)
    await links.run(bot, config, db)
    assert calls == [1, 1]


async def test_the_daily_job_runs_the_link_check(bot, config, db, monkeypatch):
    import inspect

    assert "links.run(bot, config, db)" in inspect.getsource(scheduler._scheduled_job)


async def test_the_instagram_profile_link_is_followed_too(config, db):
    import dataclasses

    with_ig = dataclasses.replace(config, instagram_username="semyon")
    await db.set_setting("profile_instagram", json.dumps({"biography": "о себе", "website": "https://gpass.morgunov.tech"}))
    found = await links.links_in_profiles(db, with_ig)
    assert [(f.url, f.platform, f.field) for f in found] == [
        ("https://gpass.morgunov.tech", "Instagram", "ссылка в профиле"),
    ]

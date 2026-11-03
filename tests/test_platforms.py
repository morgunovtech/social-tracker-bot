import json
from types import SimpleNamespace

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from conftest import COOKIE

from bot.platforms import telegram, youtube
from bot.platforms.linkedin import _parse_follower_count, collect_linkedin, plausible_count

# --- LinkedIn parsing --------------------------------------------------------

PAGE = '{"followerCount": 4520} {"followerCount": 120000} {"numFollowers": 87}'


def test_parse_without_baseline_takes_the_largest():
    assert _parse_follower_count(PAGE) == 120000


def test_parse_with_baseline_takes_the_closest():
    # The largest number is a suggested profile's counter, not ours.
    assert _parse_follower_count(PAGE, prev=4500) == 4520


@pytest.mark.parametrize(
    ("html", "prev", "expected"),
    [
        ("<p>4,520 followers</p>", None, 4520),
        ("<p>4 520 followers</p>", None, 4520),                         # NBSP separator
        ("<p>1 234 567 подписчиков</p>", None, 1234567),           # narrow NBSP
        ("<p>4,520 followers</p><p>98,000 followers</p>", None, 4520),       # first = own profile
        ("<p>98,000 followers</p><p>4,520 followers</p>", 4500, 4520),
    ],
)
def test_parse_text_fallback(html, prev, expected):
    assert _parse_follower_count(html, prev) == expected


def test_parse_nothing():
    assert _parse_follower_count("<html>no counters here</html>") is None


@pytest.mark.parametrize(
    ("prev", "new", "ok"),
    [(None, 120000, True), (50, 5000, True), (4500, 4520, True), (4500, 2000, False), (4500, 120000, False)],
)
def test_plausible_count(prev, new, ok):
    assert plausible_count(prev, new) is ok


# --- LinkedIn fetch: auth detection ------------------------------------------

async def _serve(routes: dict[str, web.Response | str]):
    """Local HTTP server: a str value is a redirect target, a Response is returned as is."""
    app = web.Application()

    for path, target in routes.items():
        async def handler(request, target=target):
            if isinstance(target, str):
                raise web.HTTPFound(target)
            return target

        app.router.add_get(path, handler)
    server = TestServer(app)
    await server.start_server()
    return server


@pytest.fixture
async def linkedin_server():
    page = web.Response(text='{"followerCount": 4520}', content_type="text/html")
    server = await _serve({
        "/in/johnlogin/": page,
        "/in/expired/": "/authwall?trk=x",
        "/in/challenged/": "/checkpoint/challenge/abc",
        "/in/blocked/": web.Response(status=999),
        "/in/forbidden/": web.Response(status=403),
        "/in/broken/": web.Response(status=500),
        "/authwall": web.Response(text="login"),
        "/checkpoint/challenge/abc": web.Response(text="challenge"),
    })
    yield server
    await server.close()


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/in/johnlogin/", (4520, "cookie")),      # "login" in the username is fine
        ("/in/expired/", (None, "cookie_expired")),
        ("/in/challenged/", (None, "cookie_expired")),
        ("/in/forbidden/", (None, "cookie_expired")),
        ("/in/blocked/", (None, None)),            # 999 = bot block, not an expired cookie
        ("/in/broken/", (None, None)),
    ],
)
async def test_fetch_outcomes(linkedin_server, path, expected):
    async with aiohttp.ClientSession() as session:
        result = await collect_linkedin(session, str(linkedin_server.make_url(path)), COOKIE)
    assert result == expected


async def test_linkedin_skipped_without_url_or_cookie():
    async with aiohttp.ClientSession() as session:
        assert await collect_linkedin(session, None, COOKIE) == (None, None)
        assert await collect_linkedin(session, "https://www.linkedin.com/in/x/", None) == (None, None)


# --- YouTube -----------------------------------------------------------------

@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (web.json_response({"items": [{"statistics": {"subscriberCount": "129"}}]}), 129),
        (web.json_response({"items": []}), None),
        (web.json_response({"error": "quota"}, status=403), None),
        (web.json_response({"items": [{"statistics": {"hiddenSubscriberCount": True}}]}), None),
    ],
)
async def test_youtube(monkeypatch, response, expected):
    server = await _serve({"/channels": response})
    monkeypatch.setattr(youtube, "_YOUTUBE_API_URL", str(server.make_url("/channels")))
    try:
        async with aiohttp.ClientSession() as session:
            assert await youtube.collect_youtube(session, "key", "UCx") == expected
    finally:
        await server.close()


async def test_youtube_profile(monkeypatch):
    channel = {
        "snippet": {
            "title": "Канал",
            "customUrl": "@chan",
            "description": "о канале",
            "thumbnails": {"default": {"url": "https://yt3.example/a"}},
        },
        "statistics": {"videoCount": "42"},
    }
    server = await _serve({"/channels": web.json_response({"items": [channel]})})
    monkeypatch.setattr(youtube, "_YOUTUBE_API_URL", str(server.make_url("/channels")))
    try:
        async with aiohttp.ClientSession() as session:
            fields = await youtube.fetch_youtube_channel(session, "key", "UCx")
    finally:
        await server.close()
    assert fields == {
        "title": "Канал", "handle": "@chan", "description": "о канале",
        "avatar": "https://yt3.example/a", "videos": "42",
    }
    assert set(fields) == set(youtube.YouTube.profile_fields)


# --- Telegram ----------------------------------------------------------------

class ChannelBot:
    def __init__(self, fail=False):
        self.fail = fail

    async def get_chat(self, chat_id):
        if self.fail:
            raise RuntimeError("Forbidden: bot is not a member of the channel chat")
        return SimpleNamespace(
            title="Канал", username="chan", description=None, photo=SimpleNamespace(big_file_unique_id="p1")
        )

    async def get_chat_administrators(self, chat_id):
        return [
            SimpleNamespace(user=SimpleNamespace(id=5, full_name="Bot", username=None), status="administrator"),
            SimpleNamespace(user=SimpleNamespace(id=1, full_name="Owner", username="own"), status="creator"),
        ]


async def test_telegram_channel_profile():
    fields = await telegram.fetch_channel(ChannelBot(), "@chan")
    assert fields["title"] == "Канал" and fields["description"] == "" and fields["photo"] == "p1"
    assert json.loads(fields["admins"]) == [
        {"id": 1, "name": "Owner (@own)", "status": "creator"},
        {"id": 5, "name": "Bot", "status": "administrator"},
    ]
    assert set(fields) == set(telegram.Telegram.profile_fields)
    assert await telegram.fetch_channel(ChannelBot(fail=True), "@chan") is None

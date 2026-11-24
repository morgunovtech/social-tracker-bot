"""Yandex.Webmaster: the owner's brand queries in Yandex search.

Read-only through an OAuth token of the owner's own Yandex app with the
«получение информации о сайтах» right (webmaster:hostinfo); the token lives
six months. The API (v4, yandex.ru/dev/webmaster) gives each site's popular
queries of a period — the top 3 000, 500 a page — with their impressions and
clicks; the bot keeps those that match the brand words. A query outside the
top is not seen: said in the README, not guessed.
"""

from __future__ import annotations

import re
from datetime import date
from urllib.parse import quote

import aiohttp

from bot.reputation.base import Failure, Week

API = "https://api.webmaster.yandex.net/v4"
TIMEOUT = aiohttp.ClientTimeout(total=30)
PAGE = 500
TOP = 3000


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"OAuth {token}"}


async def _get(session: aiohttp.ClientSession, token: str, path: str, params=None) -> dict:
    async with session.get(f"{API}{path}", params=params, headers=_headers(token), timeout=TIMEOUT) as resp:
        if resp.status != 200:
            raise Failure(f"rejected:{resp.status}")
        return await resp.json()


async def hosts(session: aiohttp.ClientSession, token: str) -> tuple[str, list[tuple[str, str]]]:
    """(user id, [(host id, site url)]) of the verified sites."""
    user = str((await _get(session, token, "/user")).get("user_id") or "")
    if not user:
        raise Failure("rejected:user")
    data = await _get(session, token, f"/user/{user}/hosts")
    found = [(h["host_id"], h.get("ascii_host_url") or h["host_id"])
             for h in data.get("hosts") or [] if h.get("host_id") and h.get("verified")]
    return user, found


def matcher(words: list[str]) -> re.Pattern:
    """The same brand match as Search Console's: a space inside a word matches a space or nothing."""
    parts = [r"\s*".join(re.escape(piece) for piece in word.split()) for word in words if word.strip()]
    return re.compile("|".join(parts), re.IGNORECASE)


async def week(session: aiohttp.ClientSession, secret: str, words: list[str], start: date, end: date) -> Week:
    """Brand queries of [start, end] summed over every verified site."""
    user, sites = await hosts(session, secret)
    brand = matcher(words)
    result = Week()
    for host_id, _url in sites:
        path = f"/user/{user}/hosts/{quote(host_id, safe='')}/search-queries/popular"
        for offset in range(0, TOP, PAGE):
            data = await _get(session, secret, path, [
                ("order_by", "TOTAL_SHOWS"), ("query_indicator", "TOTAL_SHOWS"), ("query_indicator", "TOTAL_CLICKS"),
                ("date_from", start.isoformat()), ("date_to", end.isoformat()),
                ("limit", str(PAGE)), ("offset", str(offset)),
            ])
            queries = data.get("queries") or []
            for q in queries:
                text = str(q.get("query_text") or "")
                if text and brand.search(text):
                    indicators = q.get("indicators") or {}
                    result.add(text.lower(), int(indicators.get("TOTAL_SHOWS") or 0),
                               int(indicators.get("TOTAL_CLICKS") or 0))
            if len(queries) < PAGE or offset + PAGE >= int(data.get("count") or 0):
                break
        result.places += 1
    return result


async def check(session: aiohttp.ClientSession, secret: str) -> tuple[str | None, str]:
    """A live test of a new token: (None, the sites it sees) or (why not, '')."""
    if len(secret) < 20 or " " in secret:
        return "key", ""
    try:
        _user, sites = await hosts(session, secret)
    except Failure as e:
        return e.code, ""
    except aiohttp.ClientError:
        return "connect", ""
    if not sites:
        return "no_sites", ""
    return None, ", ".join(url for _id, url in sites)

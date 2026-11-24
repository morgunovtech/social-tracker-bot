"""Cloudflare: how often AI assistants opened the owner's pages for people.

The dashboard's AI Crawl Control shows «AI Answer retrievals»; the API has no
metric by that name (developers.cloudflare.com/ai-crawl-control: «for
programmatic access … use the GraphQL Analytics API»). What it does have on
the Free plan is httpRequestsAdaptiveGroups, kept at least 31 days, filtered
by user agent. So the bot counts the requests of the crawlers Cloudflare files
under «AI Assistant» — «automated AI bot driven by user action» — one user
agent and one day per query, the pattern the Free plan is known to answer.
The report says it is a count by user agent: a spoofed agent counts too.

Read-only token of the bot's own: Zone → Zone → Read (to list the zones) and
Zone → Analytics → Read. Not the account's audit log — that is TofsDevOps's.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta

import aiohttp

from bot.reputation.base import Failure, Week

logger = logging.getLogger(__name__)

API = "https://api.cloudflare.com/client/v4"
TIMEOUT = aiohttp.ClientTimeout(total=30)
# The «AI Assistant» category of Cloudflare's bot reference (ai-crawl-control/reference/bots).
AGENTS = ("ChatGPT-User", "Claude-User", "Perplexity-User", "MistralAI-User", "Meta-ExternalFetcher", "DuckAssistBot")
MAX_ZONES = 10
# 300 GraphQL queries per 5 minutes: one a second keeps well inside.
PAUSE = 1.0

QUERY = """
query ($zone: String!, $since: Time!, $until: Time!, $agent: String!) {
  viewer {
    zones(filter: {zoneTag: $zone}) {
      httpRequestsAdaptiveGroups(limit: 100, filter: {
        datetime_geq: $since, datetime_lt: $until, requestSource: "eyeball", userAgent_like: $agent
      }) {
        count
        dimensions { clientRequestHTTPHost }
      }
    }
  }
}
"""


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def zones(session: aiohttp.ClientSession, token: str) -> list[tuple[str, str]]:
    """[(zone id, name)] the token can read."""
    async with session.get(f"{API}/zones", params={"per_page": "50"}, headers=_headers(token),
                           timeout=TIMEOUT) as resp:
        if resp.status != 200:
            raise Failure(f"rejected:{resp.status}")
        data = await resp.json()
    return [(z["id"], z.get("name") or z["id"]) for z in data.get("result") or [] if z.get("id")][:MAX_ZONES]


async def _count(session: aiohttp.ClientSession, token: str, zone: str, agent: str, day: date) -> list[dict]:
    since = datetime(day.year, day.month, day.day, tzinfo=UTC)
    variables = {"zone": zone, "agent": f"%{agent}%", "since": since.isoformat().replace("+00:00", "Z"),
                 "until": (since + timedelta(days=1)).isoformat().replace("+00:00", "Z")}
    async with session.post(f"{API}/graphql", json={"query": QUERY, "variables": variables},
                            headers=_headers(token), timeout=TIMEOUT) as resp:
        if resp.status != 200:
            raise Failure(f"rejected:{resp.status}")
        data = await resp.json()
    if data.get("errors"):
        # The plan refused a field or a range: said as «not available», logged as Cloudflare put it.
        logger.warning("Cloudflare GraphQL refused the query: %s", [e.get("message") for e in data["errors"]][:2])
        raise Failure("not_available")
    found = (((data.get("data") or {}).get("viewer") or {}).get("zones") or [{}])[0]
    return found.get("httpRequestsAdaptiveGroups") or []


async def week(session: aiohttp.ClientSession, secret: str, words=None, start: date | None = None,
               end: date | None = None, pause: float = PAUSE) -> Week:
    """AI-assistant requests of [start, end], by assistant and by host."""
    result = Week()
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    for zone, _name in await zones(session, secret):
        for agent in AGENTS:
            for day in days:
                for group in await _count(session, secret, zone, agent, day):
                    host = str((group.get("dimensions") or {}).get("clientRequestHTTPHost") or "")
                    result.add(agent, int(group.get("count") or 0), host=host)
                if pause:
                    await asyncio.sleep(pause)
        result.places += 1
    return result


async def check(session: aiohttp.ClientSession, secret: str) -> tuple[str | None, str]:
    """A live test of a new token: the zones it reads, and one real query
    for yesterday, so a plan that refuses the data says so now."""
    if len(secret) < 30 or " " in secret:
        return "key", ""
    try:
        found = await zones(session, secret)
        if not found:
            return "no_sites", ""
        await _count(session, secret, found[0][0], AGENTS[0], datetime.now(UTC).date() - timedelta(days=1))
    except Failure as e:
        return e.code, ""
    except aiohttp.ClientError:
        return "connect", ""
    return None, ", ".join(name for _id, name in found)

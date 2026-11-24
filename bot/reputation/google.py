"""Search Console: how often the owner and their products were searched for.

Read-only, through a service account of the bot's own: the owner creates it
in Google Cloud, adds its e-mail as a user of each property in Search
Console, and sends the key file (JSON) to the bot. The bot signs a JWT with
the key (RS256), trades it for an access token with the read-only scope,
lists the properties the account sees and asks each for the brand queries of
a week — the queries that match the owner's brand words.

Only brand queries: the site's clicks and impressions as a whole are a sign
of breakage and belong to TofsDevOps (BOT_PRINCIPLES, «Кто за что отвечает»).
"""

from __future__ import annotations

import base64
import json
import re
import time
from datetime import date
from urllib.parse import quote

import aiohttp

from bot.reputation.base import Failure, Week

TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/webmasters/v3"
SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
TIMEOUT = aiohttp.ClientTimeout(total=30)
ROW_LIMIT = 1000


def parse_key(text: str) -> dict | None:
    """The service account key the owner pasted or sent as a file; None
    when it is not one (the fields the token exchange needs)."""
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or data.get("type") != "service_account":
        return None
    if not all(isinstance(data.get(k), str) and data.get(k) for k in ("client_email", "private_key")):
        return None
    return {"client_email": data["client_email"], "private_key": data["private_key"],
            "token_uri": data.get("token_uri") or TOKEN_URL}


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def assertion(key: dict, now: float | None = None) -> str:
    """The signed JWT the token endpoint takes (RS256, an hour)."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    iat = int(now if now is not None else time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    claims = {"iss": key["client_email"], "scope": SCOPE, "aud": key["token_uri"], "iat": iat, "exp": iat + 3600}
    signing_input = f"{_b64(json.dumps(header).encode())}.{_b64(json.dumps(claims).encode())}"
    private = serialization.load_pem_private_key(key["private_key"].encode(), password=None)
    signature = private.sign(signing_input.encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{signing_input}.{_b64(signature)}"


async def access_token(session: aiohttp.ClientSession, key: dict) -> str:
    try:
        signed = assertion(key)
    except (ValueError, TypeError) as e:
        raise Failure("key") from e
    async with session.post(key["token_uri"], data={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": signed,
    }, timeout=TIMEOUT) as resp:
        if resp.status != 200:
            raise Failure(f"rejected:{resp.status}")
        token = (await resp.json()).get("access_token")
    if not token:
        raise Failure("rejected:token")
    return token


async def sites(session: aiohttp.ClientSession, token: str) -> list[str]:
    """The properties the service account was added to."""
    async with session.get(f"{API}/sites", headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT) as resp:
        if resp.status != 200:
            raise Failure(f"rejected:{resp.status}")
        entries = (await resp.json()).get("siteEntry") or []
    return [e["siteUrl"] for e in entries if e.get("siteUrl") and e.get("permissionLevel") != "siteUnverifiedUser"]


def brand_regex(words: list[str]) -> str:
    """One RE2 expression for the brand words, case-insensitive; a space in a
    word matches a space or nothing («good pass» finds «goodpass» too)."""
    parts = [r"\s*".join(re.escape(piece) for piece in word.split()) for word in words if word.strip()]
    return "(?i)(" + "|".join(parts) + ")"


async def week(session: aiohttp.ClientSession, secret: str, words: list[str], start: date, end: date) -> Week:
    """Brand queries of [start, end] summed over every property the key sees."""
    key = parse_key(secret)
    if key is None:
        raise Failure("key")
    token = await access_token(session, key)
    result = Week()
    body = {
        "startDate": start.isoformat(), "endDate": end.isoformat(), "dimensions": ["query"], "type": "web",
        "rowLimit": ROW_LIMIT,
        "dimensionFilterGroups": [{"filters": [{"dimension": "query", "operator": "includingRegex",
                                                "expression": brand_regex(words)}]}],
    }
    for site in await sites(session, token):
        url = f"{API}/sites/{quote(site, safe='')}/searchAnalytics/query"
        async with session.post(url, json=body, headers={"Authorization": f"Bearer {token}"},
                                timeout=TIMEOUT) as resp:
            if resp.status != 200:
                raise Failure(f"rejected:{resp.status}")
            rows = (await resp.json()).get("rows") or []
        for row in rows:
            query = (row.get("keys") or [""])[0]
            result.add(query, int(row.get("impressions") or 0), int(row.get("clicks") or 0))
        result.places += 1
    return result


async def check(session: aiohttp.ClientSession, secret: str) -> tuple[str | None, str]:
    """A live test of a new key: (None, what it sees) or (why not, '')."""
    key = parse_key(secret)
    if key is None:
        return "key", ""
    try:
        found = await sites(session, await access_token(session, key))
    except Failure as e:
        return e.code, ""
    except aiohttp.ClientError:
        return "connect", ""
    if not found:
        return "no_sites", key["client_email"]
    return None, ", ".join(found)

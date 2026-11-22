"""Instagram: the official Instagram API with Instagram Login.

A professional (Business or Creator) account and a Meta app with the
«Instagram» product: the app dashboard issues a long-lived access token for
your own account, no OAuth flow needed. The token lives 60 days; the bot
refreshes it itself once it is older than a day and past its first month,
so a token pasted once keeps working while the bot runs every day.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import aiohttp

from bot.db import Database, parse_utc, utcnow
from bot.platforms.base import COUNT, TEXT, Context, Platform, Snapshot

logger = logging.getLogger(__name__)

# Unversioned: Meta serves the oldest live version, so a pinned version
# cannot expire under the bot. The fields below exist in every version.
_GRAPH_URL = "https://graph.instagram.com"
_TIMEOUT = aiohttp.ClientTimeout(total=20)

# A long-lived token: 60 days from issue or refresh; refreshable once it is
# 24 hours old. Refreshing from the half-way point leaves a month of daily
# retries before the token dies.
TOKEN_LIFETIME = timedelta(days=60)
REFRESH_BEFORE_DAYS = 30
# Fewer days left than this (the refresh keeps failing): warn in the report.
TOKEN_EXPIRING_DAYS = 7

# Settings keys. The token is a secret: wiped from backups (db._SECRET_SETTINGS).
TOKEN_KEY = "instagram_token"
TOKEN_SET_AT_KEY = "instagram_token_set_at"
TOKEN_EXPIRES_AT_KEY = "instagram_token_expires_at"
TOKEN_KEYS = (TOKEN_KEY, TOKEN_SET_AT_KEY, TOKEN_EXPIRES_AT_KEY)

_PROFILE_FIELDS = "user_id,username,name,biography,followers_count,media_count"


class InstagramAuthError(Exception):
    """The token is expired, revoked or lacks the permission."""


def _auth_error(status: int, data: dict) -> bool:
    """Meta's token errors: HTTP 401/403, or OAuthException / code 190 in the body."""
    error = data.get("error") if isinstance(data, dict) else None
    if not isinstance(error, dict):
        return status in (401, 403)
    return status in (401, 403) or error.get("type") == "OAuthException" or error.get("code") == 190


async def _get(session: aiohttp.ClientSession, path: str, params: dict) -> dict | None:
    """One Graph call. Raises InstagramAuthError for a dead token; None on any
    other failure (rate limit, outage), which is retried later."""
    async with session.get(f"{_GRAPH_URL}/{path}", params=params, timeout=_TIMEOUT) as resp:
        try:
            data = await resp.json(content_type=None)
        except ValueError:
            data = {}
        if resp.status == 200 and isinstance(data, dict) and "error" not in data:
            return data
        if _auth_error(resp.status, data):
            raise InstagramAuthError(f"Instagram API returned {resp.status}: token rejected")
        detail = data.get("error", {}) if isinstance(data, dict) else {}
        logger.error(
            "Instagram API %s returned status %d (code %s): %s",
            path, resp.status, detail.get("code"), str(detail.get("message", ""))[:200],
        )
        return None


async def fetch_user(session: aiohttp.ClientSession, token: str) -> dict | None:
    """The account behind the token: user_id, username, name, biography,
    followers_count, media_count. Raises InstagramAuthError for a dead token."""
    return await _get(session, "me", {"fields": _PROFILE_FIELDS, "access_token": token})


async def collect_instagram(session: aiohttp.ClientSession, token: str | None) -> tuple[int | None, str | None]:
    """Returns (count, 'api'), (None, 'token_expired') or (None, None) for a failure to retry."""
    if not token:
        logger.warning("Instagram skipped: no token (set via /igtoken or INSTAGRAM_ACCESS_TOKEN)")
        return None, None
    try:
        user = await fetch_user(session, token)
    except InstagramAuthError as e:
        logger.error("Instagram auth error: %s", e)
        return None, "token_expired"
    except Exception:
        logger.exception("Failed to collect Instagram followers")
        return None, None
    if user is None:
        return None, None
    try:
        count = int(user["followers_count"])
    except (KeyError, TypeError, ValueError):
        logger.error("Instagram API returned no followers_count: %s", sorted(user))
        return None, None
    logger.info("Instagram followers: %d", count)
    return count, "api"


async def fetch_instagram_profile(session: aiohttp.ClientSession, token: str | None) -> dict[str, str] | None:
    """Current watched profile fields. Without a working token there is
    nothing to compare, not a failure: an empty dict, so no «unreachable» alert
    (the collect reports the token). The avatar is left out on purpose: its CDN
    URL changes without the picture changing."""
    if not token:
        return {}
    try:
        user = await fetch_user(session, token)
    except InstagramAuthError:
        return {}
    except Exception:
        logger.exception("Failed to fetch Instagram profile")
        return None
    if user is None:
        return None
    fields = {
        "username": user.get("username"),
        "name": user.get("name"),
        "biography": user.get("biography"),
        "media": user.get("media_count"),
    }
    # A field the API left out this time is unknown, not emptied: no alert.
    return {name: str(value) for name, value in fields.items() if value is not None}


async def refresh_token(session: aiohttp.ClientSession, token: str) -> tuple[str, int] | None:
    """A fresh 60-day token and its lifetime in seconds, or None: Meta refuses
    a token younger than 24 hours, and a dead one — the collect reports that."""
    try:
        data = await _get(
            session, "refresh_access_token", {"grant_type": "ig_refresh_token", "access_token": token}
        )
    except InstagramAuthError:
        return None
    except Exception:
        logger.exception("Instagram token refresh failed")
        return None
    if not data or not data.get("access_token"):
        return None
    try:
        expires_in = int(data.get("expires_in") or TOKEN_LIFETIME.total_seconds())
    except (TypeError, ValueError):
        expires_in = int(TOKEN_LIFETIME.total_seconds())
    return str(data["access_token"]), expires_in


# ---------------------------------------------------------------------------
# Token storage: DB (set via /igtoken or refreshed) > env (INSTAGRAM_ACCESS_TOKEN)
# ---------------------------------------------------------------------------

async def get_active_token(db: Database, config) -> str | None:
    return (await db.get_setting(TOKEN_KEY)) or config.instagram_access_token


async def get_token_expiry(db: Database) -> datetime | None:
    """When the stored token dies; None for an env token the bot has not refreshed yet."""
    raw = await db.get_setting(TOKEN_EXPIRES_AT_KEY)
    if not raw:
        return None
    try:
        return parse_utc(raw)
    except (ValueError, TypeError):
        return None


async def get_token_days_left(db: Database) -> int | None:
    expires_at = await get_token_expiry(db)
    if expires_at is None:
        return None
    return (expires_at - utcnow()).days


async def store_token(db: Database, token: str, expires_in: int | None = None) -> None:
    """Remember a token and when it dies: a pasted one lives the full 60 days."""
    now = utcnow()
    lifetime = timedelta(seconds=expires_in) if expires_in else TOKEN_LIFETIME
    await db.set_setting(TOKEN_KEY, token)
    await db.set_setting(TOKEN_SET_AT_KEY, now.isoformat())
    await db.set_setting(TOKEN_EXPIRES_AT_KEY, (now + lifetime).isoformat())


async def ensure_fresh_token(db: Database, config, session: aiohttp.ClientSession) -> str | None:
    """The token to collect with, refreshed when it is past its first month
    (or came from env, with an unknown age). A failed refresh keeps the old one."""
    token = await get_active_token(db, config)
    if not token:
        return None
    days_left = await get_token_days_left(db)
    if days_left is not None and days_left > REFRESH_BEFORE_DAYS:
        return token
    refreshed = await refresh_token(session, token)
    if refreshed is None:
        return token
    new_token, expires_in = refreshed
    await store_token(db, new_token, expires_in)
    logger.info("Instagram token refreshed for %d days", expires_in // 86400)
    return new_token


class Instagram(Platform):
    id = "instagram"
    label = "Instagram"
    short = "IG"
    account = "аккаунт Instagram"
    profile_fields = {
        "username": ("@username", TEXT),
        "name": ("имя профиля", TEXT),
        "biography": ("описание профиля", TEXT),
        "media": ("публикаций", COUNT),
    }

    def enabled(self, config) -> bool:
        return bool(config.instagram_username)

    def target(self, config) -> str:
        return f"@{config.instagram_username}" if config.instagram_username else ""

    async def collect(self, ctx: Context) -> Snapshot:
        token = await ensure_fresh_token(ctx.db, ctx.config, ctx.session)
        if not token:
            # Not an error: retrying won't help until /igtoken, which the report asks for.
            return Snapshot(None, flags={"instagram_token_missing": True})
        count, source = await collect_instagram(ctx.session, token)
        if source == "token_expired":
            return Snapshot(None, flags={"instagram_token_expired": True})
        flags: dict[str, bool | int] = {}
        days_left = await get_token_days_left(ctx.db)
        if days_left is not None and days_left <= TOKEN_EXPIRING_DAYS:
            flags["instagram_token_expiring"] = max(days_left, 0)
        return Snapshot(count, source or "api", error=count is None, flags=flags)

    async def fetch_profile(self, ctx: Context) -> dict[str, str] | None:
        return await fetch_instagram_profile(ctx.session, await get_active_token(ctx.db, ctx.config))

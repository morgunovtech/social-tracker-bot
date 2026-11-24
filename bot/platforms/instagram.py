"""Instagram: the official Instagram API with Unified login.

A professional (Business or Creator) account, a Meta app with the Instagram
use case and a business portfolio: the app dashboard («API setup with Unified
login» → Generate token) issues a system-user access token for your own
account, no OAuth flow needed. The token does not expire: Meta revokes it
only when the account leaves the business portfolio or the app is removed.

Requests go to graph.facebook.com by the Instagram account's id: with this
token /me is the system user, not the account, so the id is looked up once
among the accounts the token was granted (/me/assigned_instagram_accounts).
"""

from __future__ import annotations

import logging

import aiohttp

from bot.db import Database, parse_utc, utcnow
from bot.platforms.base import COUNT, TEXT, Context, Platform, Snapshot

logger = logging.getLogger(__name__)

# Unversioned: Meta serves the oldest live version, so a pinned version
# cannot expire under the bot. The fields below exist in every version.
_GRAPH_URL = "https://graph.facebook.com"
_TIMEOUT = aiohttp.ClientTimeout(total=20)

# Settings keys. The token is a secret: wiped from backups (db._SECRET_SETTINGS).
TOKEN_KEY = "instagram_token"
TOKEN_SET_AT_KEY = "instagram_token_set_at"
USER_ID_KEY = "instagram_user_id"
# Whose account USER_ID_KEY is: a changed INSTAGRAM_USERNAME must not keep collecting the old one.
USERNAME_KEY = "instagram_username"
TOKEN_KEYS = (TOKEN_KEY, TOKEN_SET_AT_KEY, USER_ID_KEY, USERNAME_KEY)

# `website` — the link under the bio, the first thing a hijacker replaces; a
# documented public field of the IG User node, same permission as biography.
_PROFILE_FIELDS = "username,name,biography,website,followers_count,media_count"


class InstagramAuthError(Exception):
    """The token is revoked, expired or lacks the permission."""


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


async def resolve_account(session: aiohttp.ClientSession, token: str, username: str) -> str | None:
    """The id of the account with this username among those the token was
    granted, or None when it is not among them (or the call failed).
    Raises InstagramAuthError for a dead token."""
    data = await _get(session, "me/assigned_instagram_accounts", {"fields": "id,username", "access_token": token})
    if data is None:
        return None
    accounts = data.get("data") or []
    for account in accounts:
        if str(account.get("username", "")).lower() == username.lower():
            return str(account["id"])
    logger.error(
        "Instagram token is not granted for @%s (granted: %s)",
        username, ", ".join(f"@{a.get('username')}" for a in accounts) or "none",
    )
    return None


async def fetch_user(session: aiohttp.ClientSession, token: str, user_id: str) -> dict | None:
    """The account: username, name, biography, website, followers_count, media_count.
    Raises InstagramAuthError for a dead token."""
    return await _get(session, user_id, {"fields": _PROFILE_FIELDS, "access_token": token})


async def collect_instagram(
    session: aiohttp.ClientSession, token: str | None, user_id: str | None
) -> tuple[int | None, str | None]:
    """Returns (count, 'api'), (None, 'token_expired') or (None, None) for a failure to retry."""
    if not token or not user_id:
        logger.warning("Instagram skipped: no token (set via /igtoken or INSTAGRAM_ACCESS_TOKEN)")
        return None, None
    try:
        user = await fetch_user(session, token, user_id)
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


async def fetch_instagram_profile(
    session: aiohttp.ClientSession, token: str | None, user_id: str | None
) -> dict[str, str] | None:
    """Current watched profile fields. Without a working token there is
    nothing to compare, not a failure: an empty dict, so no «unreachable» alert
    (the collect reports the token). The avatar is left out on purpose: its CDN
    URL changes without the picture changing."""
    if not token or not user_id:
        return {}
    try:
        user = await fetch_user(session, token, user_id)
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
        "website": user.get("website"),
        "media": user.get("media_count"),
    }
    # A field the API left out this time is unknown, not emptied: no alert.
    return {name: str(value) for name, value in fields.items() if value is not None}


# ---------------------------------------------------------------------------
# Token storage: DB (set via /igtoken) > env (INSTAGRAM_ACCESS_TOKEN)
# ---------------------------------------------------------------------------

async def get_active_token(db: Database, config) -> str | None:
    return (await db.get_setting(TOKEN_KEY)) or config.instagram_access_token


async def get_token_age_days(db: Database) -> int | None:
    """Days since the token was set via /igtoken (None if from env or unset)."""
    set_at = await db.get_setting(TOKEN_SET_AT_KEY)
    if not set_at:
        return None
    try:
        return (utcnow() - parse_utc(set_at)).days
    except (ValueError, TypeError):
        return None


async def store_token(db: Database, token: str, user_id: str, username: str | None = None) -> None:
    await db.set_setting(TOKEN_KEY, token)
    await db.set_setting(TOKEN_SET_AT_KEY, utcnow().isoformat())
    await db.set_setting(USER_ID_KEY, user_id)
    if username:
        await db.set_setting(USERNAME_KEY, username.lower())


async def get_account_id(db: Database, config, session: aiohttp.ClientSession, token: str) -> str | None:
    """The account id for the token: stored by /igtoken, or looked up once for
    an env token and remembered — together with the username it was looked
    up for, so a changed INSTAGRAM_USERNAME is resolved again rather than
    collecting the old account for ever. Raises InstagramAuthError for a dead token."""
    user_id = await db.get_setting(USER_ID_KEY)
    known = (await db.get_setting(USERNAME_KEY) or "").lower()
    if user_id and known == config.instagram_username.lower():
        return user_id
    user_id = await resolve_account(session, token, config.instagram_username)
    if user_id:
        await db.set_setting(USER_ID_KEY, user_id)
        await db.set_setting(USERNAME_KEY, config.instagram_username.lower())
    return user_id


class Instagram(Platform):
    id = "instagram"
    label = "Instagram"
    short = "IG"
    account = "аккаунт Instagram"
    profile_fields = {
        "username": ("@username", TEXT),
        "name": ("имя профиля", TEXT),
        "biography": ("описание профиля", TEXT),
        "website": ("ссылка в профиле", TEXT),
        "media": ("публикаций", COUNT),
    }

    def enabled(self, config) -> bool:
        return bool(config.instagram_username)

    def target(self, config) -> str:
        return f"@{config.instagram_username}" if config.instagram_username else ""

    async def collect(self, ctx: Context) -> Snapshot:
        token = await get_active_token(ctx.db, ctx.config)
        if not token:
            # Not an error: retrying won't help until /igtoken, which the report asks for.
            return Snapshot(None, flags={"instagram_token_missing": True})
        try:
            user_id = await get_account_id(ctx.db, ctx.config, ctx.session, token)
        except InstagramAuthError:
            return Snapshot(None, flags={"instagram_token_expired": True})
        except Exception:
            logger.exception("Instagram account lookup failed")
            return Snapshot(None, error=True)
        if not user_id:
            return Snapshot(None, error=True)
        count, source = await collect_instagram(ctx.session, token, user_id)
        if source == "token_expired":
            return Snapshot(None, flags={"instagram_token_expired": True})
        return Snapshot(count, source or "api", error=count is None)

    async def fetch_profile(self, ctx: Context) -> dict[str, str] | None:
        token = await get_active_token(ctx.db, ctx.config)
        return await fetch_instagram_profile(ctx.session, token, await ctx.db.get_setting(USER_ID_KEY))

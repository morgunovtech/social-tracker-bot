from __future__ import annotations

import logging
import re

import aiohttp
from bs4 import BeautifulSoup

from bot.db import Database, parse_utc, utcnow
from bot.platforms.base import Context, Platform, Snapshot

logger = logging.getLogger(__name__)

# Warn user when cookie has been in use longer than this (LinkedIn lifetime ~12 months)
COOKIE_AGING_DAYS = 330

# Cookie-based fetch
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
_BROWSER_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ru;q=0.7",
}

# Patterns ordered by reliability
_FOLLOWER_PATTERNS = [
    re.compile(r'"followerCount"\s*:\s*(\d+)'),
    re.compile(r'"numFollowers"\s*:\s*(\d+)'),
    re.compile(r'"followers"\s*:\s*\{\s*"count"\s*:\s*(\d+)'),
]

# Text fallback: "1,234 followers" / "1 234 подписчика"
_FOLLOWER_TEXT_PATTERN = re.compile(
    r"([\d][\d\s, ]*)\s*(?:followers?|подписчик(?:а|ов)?)",
    re.IGNORECASE,
)


# Redirect targets meaning the session is gone: login wall or a security challenge.
_AUTH_PATHS = ("/authwall", "/login", "/uas/login", "/checkpoint")


class LinkedInAuthError(Exception):
    """Raised when the li_at cookie is rejected or expired."""


def plausible_count(prev: int | None, new: int) -> bool:
    """Guard against scraping someone else's counter off the page.

    Profile pages embed follower counts of suggested/viewed profiles too, so a
    parsed value that jumps wildly vs the last stored one is treated as suspect.
    Small baselines (<100) are exempt — relative jumps are normal there.
    """
    if prev is None or prev < 100:
        return True
    return prev * 0.5 <= new <= prev * 1.5


def _closest(candidates: list[int], prev: int) -> int:
    return min(candidates, key=lambda c: abs(c - prev))


def _parse_follower_count(html: str, prev: int | None = None) -> int | None:
    """Extract follower count from LinkedIn HTML using multiple strategies.

    Pages embed follower counts of suggested/viewed profiles too. With a known
    previous value the candidate closest to it wins; the largest number would
    often be a bigger profile's counter.
    """
    # JSON-embedded counters (most reliable when authenticated)
    candidates: list[int] = []
    for pattern in _FOLLOWER_PATTERNS:
        for m in pattern.finditer(html):
            try:
                candidates.append(int(m.group(1)))
            except (ValueError, IndexError):
                continue

    if candidates:
        # Without a baseline: the total profile follower count is typically the largest.
        return _closest(candidates, prev) if prev is not None else max(candidates)

    # Visible text fallback: "1,234 followers"
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    counts: list[int] = []
    for match in _FOLLOWER_TEXT_PATTERN.finditer(text):
        # Drops thousands separators of any kind: ',', ' ', U+00A0, U+202F.
        digits = re.sub(r"\D", "", match.group(1))
        if digits:
            counts.append(int(digits))

    if counts:
        # Without a baseline: the profile's own counter comes first on the page.
        return _closest(counts, prev) if prev is not None else counts[0]

    return None


async def _fetch_via_cookie(
    session: aiohttp.ClientSession,
    profile_url: str,
    li_at: str,
    prev: int | None = None,
) -> int | None:
    cookies = {"li_at": li_at}
    try:
        async with session.get(
            profile_url,
            headers=_BROWSER_HEADERS,
            cookies=cookies,
            allow_redirects=True,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            final_url = str(resp.url)
            if resp.status in (401, 403):
                raise LinkedInAuthError(f"LinkedIn returned {resp.status} — cookie likely expired")
            # Match the path, not the whole URL: a username may contain "login".
            if resp.url.path.startswith(_AUTH_PATHS):
                raise LinkedInAuthError(f"LinkedIn redirected to {final_url} — cookie expired or invalid")
            if resp.status == 999:
                logger.error("LinkedIn returned 999 — request blocked as automated traffic (%s)", final_url)
                return None
            if resp.status != 200:
                logger.error("LinkedIn cookie fetch returned status %d (%s)", resp.status, final_url)
                return None

            html = await resp.text()

        count = _parse_follower_count(html, prev)
        if count is None:
            logger.error(
                "LinkedIn cookie fetch: parse failed (html length=%d, url=%s)",
                len(html),
                final_url,
            )
            return None

        logger.info("LinkedIn followers (cookie): %d", count)
        return count

    except LinkedInAuthError:
        raise
    except Exception:
        logger.exception("LinkedIn cookie fetch failed")
        return None


async def collect_linkedin(
    session: aiohttp.ClientSession,
    profile_url: str | None,
    li_at: str | None = None,
    prev: int | None = None,
) -> tuple[int | None, str | None]:
    """Collect LinkedIn follower count via the li_at cookie.

    prev is the last stored count; it picks the profile's own counter among
    the numbers on the page (callers still apply plausible_count).
    Returns (count, source) where source is 'cookie' or None.
    Returns (None, 'cookie_expired') as a special signal when the cookie is rejected.
    """
    if not profile_url:
        logger.warning("LinkedIn skipped: LINKEDIN_PROFILE_URL not set")
        return None, None

    if not li_at:
        logger.warning("LinkedIn skipped: no cookie (set via /setcookie or LINKEDIN_LI_AT)")
        return None, None

    try:
        count = await _fetch_via_cookie(session, profile_url, li_at, prev)
    except LinkedInAuthError as e:
        logger.error("LinkedIn auth error: %s", e)
        return None, "cookie_expired"

    if count is not None:
        return count, "cookie"
    return None, None


async def get_active_cookie(db: Database, config) -> str | None:
    """Cookie precedence: DB (set via /setcookie) > env (LINKEDIN_LI_AT)."""
    return (await db.get_setting("linkedin_li_at")) or config.linkedin_li_at


async def get_cookie_age_days(db: Database) -> int | None:
    """Days since the active cookie was set via /setcookie (None if from env or unset)."""
    set_at = await db.get_setting("linkedin_li_at_set_at")
    if not set_at:
        return None
    try:
        return (utcnow() - parse_utc(set_at)).days
    except (ValueError, TypeError):
        return None


class LinkedIn(Platform):
    """Followers only: the profile is read with a session cookie, and its page
    layout is too unstable for change alerts without false alarms."""

    id = "linkedin"
    label = "LinkedIn"
    short = "LI"
    account = "аккаунт LinkedIn"

    def enabled(self, config) -> bool:
        return bool(config.linkedin_profile_url)

    def target(self, config) -> str:
        return config.linkedin_profile_url or ""

    async def collect(self, ctx: Context) -> Snapshot:
        li_at = await get_active_cookie(ctx.db, ctx.config)
        count, source = await collect_linkedin(
            ctx.session, ctx.config.linkedin_profile_url, li_at=li_at, prev=ctx.prev
        )
        flags: dict[str, bool | int] = {}
        # Proactive aging warning (only meaningful when cookie was set via /setcookie)
        age = await get_cookie_age_days(ctx.db)
        if age is not None and age >= COOKIE_AGING_DAYS:
            flags["linkedin_cookie_aging"] = age

        if count is not None and source is not None:
            if plausible_count(ctx.prev, count):
                return Snapshot(count, source, flags=flags)
            logger.warning(
                "LinkedIn count %d rejected as implausible (previous: %s) — "
                "likely parsed someone else's counter; reset baseline via /linkedin <N>",
                count,
                ctx.prev,
            )
            return Snapshot(None, error=True, flags=flags)
        if source == "cookie_expired":
            # Not an error: retrying won't help until /setcookie, which has its own alert.
            flags["linkedin_cookie_expired"] = True
            return Snapshot(None, flags=flags)
        # Without a cookie the number is entered by hand: nothing failed.
        return Snapshot(None, error=bool(li_at), flags=flags)

from __future__ import annotations

import logging
import re
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# RapidAPI fallback
_RAPIDAPI_URL = "https://linkedin-data-scraper1.p.rapidapi.com/get_user_exact_connections.php"
_FOLLOWER_FIELDS = ("followers", "follower_count", "followersCount", "connections", "connectionsCount")

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


class LinkedInAuthError(Exception):
    """Raised when the li_at cookie is rejected or expired."""


def plausible_count(prev: Optional[int], new: int) -> bool:
    """Guard against scraping someone else's counter off the page.

    Profile pages embed follower counts of suggested/viewed profiles too, so a
    parsed value that jumps wildly vs the last stored one is treated as suspect.
    Small baselines (<100) are exempt — relative jumps are normal there.
    """
    if prev is None or prev < 100:
        return True
    return prev * 0.5 <= new <= prev * 1.5


def _parse_follower_count(html: str) -> Optional[int]:
    """Extract follower count from LinkedIn HTML using multiple strategies."""
    # JSON-embedded counters (most reliable when authenticated)
    candidates: list[int] = []
    for pattern in _FOLLOWER_PATTERNS:
        for m in pattern.finditer(html):
            try:
                candidates.append(int(m.group(1)))
            except (ValueError, IndexError):
                continue

    if candidates:
        # Pick the maximum — pages may embed several counts (post followers, etc.);
        # the total profile follower count is typically the largest.
        return max(candidates)

    # Visible text fallback: "1,234 followers"
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    match = _FOLLOWER_TEXT_PATTERN.search(text)
    if match:
        raw = match.group(1).replace(",", "").replace(" ", "").replace(" ", "")
        try:
            return int(raw)
        except ValueError:
            return None

    return None


async def _fetch_via_cookie(
    session: aiohttp.ClientSession,
    profile_url: str,
    li_at: str,
) -> Optional[int]:
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
            if "authwall" in final_url or "login" in final_url:
                raise LinkedInAuthError(f"LinkedIn redirected to {final_url} — cookie expired or invalid")
            if resp.status != 200:
                logger.error("LinkedIn cookie fetch returned status %d (%s)", resp.status, final_url)
                return None

            html = await resp.text()

        count = _parse_follower_count(html)
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


async def _fetch_via_rapidapi(
    session: aiohttp.ClientSession,
    rapidapi_key: str,
    profile_url: str,
) -> Optional[int]:
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "x-rapidapi-host": "linkedin-data-scraper1.p.rapidapi.com",
        "x-rapidapi-key": rapidapi_key,
    }
    data = {"username_or_url": profile_url}

    try:
        async with session.post(
            _RAPIDAPI_URL,
            headers=headers,
            data=data,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                logger.error("LinkedIn RapidAPI returned status %d", resp.status)
                return None

            payload = await resp.json(content_type=None)

            if isinstance(payload, dict):
                for field in _FOLLOWER_FIELDS:
                    value = payload.get(field)
                    if value is not None:
                        try:
                            count = int(str(value).replace(",", "").replace("+", "").strip())
                            logger.info("LinkedIn followers (rapidapi): %d (field: %s)", count, field)
                            return count
                        except (ValueError, TypeError):
                            continue

            logger.error("LinkedIn RapidAPI: no follower field in response")
            return None

    except Exception:
        logger.exception("LinkedIn RapidAPI fetch failed")
        return None


async def collect_linkedin(
    session: aiohttp.ClientSession,
    rapidapi_key: Optional[str],
    profile_url: Optional[str],
    li_at: Optional[str] = None,
) -> tuple[Optional[int], Optional[str]]:
    """Collect LinkedIn follower count.

    Returns (count, source) where source is one of: 'cookie', 'rapidapi', None.
    Tries the cookie path first if li_at is provided, then falls back to RapidAPI.
    Returns (None, 'cookie_expired') as a special signal when the cookie is rejected.
    """
    if not profile_url:
        logger.warning("LinkedIn skipped: LINKEDIN_PROFILE_URL not set")
        return None, None

    if li_at:
        try:
            count = await _fetch_via_cookie(session, profile_url, li_at)
            if count is not None:
                return count, "cookie"
            logger.warning("LinkedIn cookie returned no count, trying RapidAPI fallback")
        except LinkedInAuthError as e:
            logger.error("LinkedIn auth error: %s", e)
            # Don't try RapidAPI — surface the cookie problem clearly
            return None, "cookie_expired"

    if rapidapi_key:
        count = await _fetch_via_rapidapi(session, rapidapi_key, profile_url)
        if count is not None:
            return count, "rapidapi"

    if not li_at and not rapidapi_key:
        logger.warning("LinkedIn skipped: no LINKEDIN_LI_AT or RAPIDAPI_KEY")

    return None, None

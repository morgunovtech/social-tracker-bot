from __future__ import annotations

import logging
import re

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Matches strings like "4,520 followers" or "4520 followers"
_FOLLOWERS_RE = re.compile(r"([\d,]+)\s+followers", re.IGNORECASE)


async def collect_linkedin(
    session: aiohttp.ClientSession,
    rapidapi_key: str | None,
    profile_url: str | None,
) -> int | None:
    if not profile_url:
        logger.warning("LinkedIn collection skipped: missing LINKEDIN_PROFILE_URL")
        return None

    try:
        async with session.get(profile_url, headers=_HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                logger.error("LinkedIn page returned status %d", resp.status)
                return None

            html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")

        # Try meta tag first (most reliable)
        for meta in soup.find_all("meta"):
            content = meta.get("content", "")
            match = _FOLLOWERS_RE.search(content)
            if match:
                count = int(match.group(1).replace(",", ""))
                logger.info("LinkedIn followers (meta): %d", count)
                return count

        # Fallback: search all text
        text = soup.get_text(" ", strip=True)
        match = _FOLLOWERS_RE.search(text)
        if match:
            count = int(match.group(1).replace(",", ""))
            logger.info("LinkedIn followers (text): %d", count)
            return count

        logger.error("LinkedIn: followers count not found in page")
        return None

    except Exception:
        logger.exception("Failed to collect LinkedIn followers")
        return None

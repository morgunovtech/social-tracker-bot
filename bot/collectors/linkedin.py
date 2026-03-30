from __future__ import annotations

import logging

import aiohttp

logger = logging.getLogger(__name__)

_RAPIDAPI_URL = "https://linkedin-data-scraper1.p.rapidapi.com/get_user_exact_connections.php"
_FOLLOWER_FIELDS = ("followers", "follower_count", "followersCount", "connections", "connectionsCount")


async def collect_linkedin(
    session: aiohttp.ClientSession,
    rapidapi_key: str | None,
    profile_url: str | None,
) -> int | None:
    if not rapidapi_key or not profile_url:
        logger.warning("LinkedIn collection skipped: missing RAPIDAPI_KEY or LINKEDIN_PROFILE_URL")
        return None

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
                logger.error("LinkedIn Data Scraper API returned status %d", resp.status)
                return None

            payload = await resp.json(content_type=None)
            logger.info("LinkedIn API raw response keys: %s", list(payload.keys()) if isinstance(payload, dict) else type(payload))

            if isinstance(payload, dict):
                for field in _FOLLOWER_FIELDS:
                    value = payload.get(field)
                    if value is not None:
                        try:
                            count = int(str(value).replace(",", "").replace("+", "").strip())
                            logger.info("LinkedIn followers: %d (field: %s)", count, field)
                            return count
                        except (ValueError, TypeError):
                            continue

            logger.error("LinkedIn API: no follower field found in response: %s", payload)
            return None

    except Exception:
        logger.exception("Failed to collect LinkedIn followers")
        return None

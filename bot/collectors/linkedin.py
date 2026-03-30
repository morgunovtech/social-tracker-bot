from __future__ import annotations

import logging

import aiohttp

logger = logging.getLogger(__name__)

_RAPIDAPI_URL = "https://fresh-linkedin-profile-data.p.rapidapi.com/get-linkedin-profile"
_FOLLOWER_FIELDS = ("followers", "follower_count", "followersCount", "follower")


async def collect_linkedin(
    session: aiohttp.ClientSession,
    rapidapi_key: str | None,
    profile_url: str | None,
) -> int | None:
    if not rapidapi_key or not profile_url:
        logger.warning("LinkedIn collection skipped: missing RAPIDAPI_KEY or LINKEDIN_PROFILE_URL")
        return None

    headers = {
        "X-RapidAPI-Key": rapidapi_key,
        "X-RapidAPI-Host": "fresh-linkedin-profile-data.p.rapidapi.com",
    }
    params = {"linkedin_url": profile_url}

    try:
        async with session.get(_RAPIDAPI_URL, headers=headers, params=params) as resp:
            if resp.status != 200:
                logger.error("LinkedIn RapidAPI returned status %d", resp.status)
                return None
            data = await resp.json()

            # Handle nested response (some endpoints wrap in "data")
            payload = data.get("data", data) if isinstance(data, dict) else data

            for field in _FOLLOWER_FIELDS:
                value = payload.get(field)
                if value is not None:
                    count = int(value)
                    logger.info("LinkedIn followers: %d (field: %s)", count, field)
                    return count

            logger.error(
                "LinkedIn API response has no follower field. Available keys: %s",
                list(payload.keys()) if isinstance(payload, dict) else type(payload),
            )
            return None
    except Exception:
        logger.exception("Failed to collect LinkedIn followers")
        return None

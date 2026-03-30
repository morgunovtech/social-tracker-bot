from __future__ import annotations

import logging

import aiohttp

logger = logging.getLogger(__name__)

_YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/channels"


async def collect_youtube(
    session: aiohttp.ClientSession,
    api_key: str,
    channel_id: str,
) -> int | None:
    params = {
        "part": "statistics",
        "id": channel_id,
        "key": api_key,
    }
    try:
        async with session.get(_YOUTUBE_API_URL, params=params) as resp:
            if resp.status != 200:
                logger.error("YouTube API returned status %d", resp.status)
                return None
            data = await resp.json()
            items = data.get("items", [])
            if not items:
                logger.error("YouTube API returned no items for channel %s", channel_id)
                return None
            count = int(items[0]["statistics"]["subscriberCount"])
            logger.info("YouTube subscribers: %d", count)
            return count
    except Exception:
        logger.exception("Failed to collect YouTube subscribers")
        return None

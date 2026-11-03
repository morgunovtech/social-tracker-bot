from __future__ import annotations

import logging

import aiohttp

from bot.platforms.base import COUNT, IMAGE, TEXT, Context, Platform, Snapshot

logger = logging.getLogger(__name__)

_YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/channels"


async def _get_channel(
    session: aiohttp.ClientSession, api_key: str, channel_id: str, part: str
) -> dict | None:
    """The channel resource with the requested parts, or None. Costs 1 quota unit."""
    params = {"part": part, "id": channel_id, "key": api_key}
    async with session.get(_YOUTUBE_API_URL, params=params) as resp:
        if resp.status != 200:
            logger.error("YouTube API returned status %d", resp.status)
            return None
        data = await resp.json()
    items = data.get("items", [])
    if not items:
        # Also what a terminated or hidden channel looks like.
        logger.error("YouTube API returned no items for channel %s", channel_id)
        return None
    return items[0]


async def collect_youtube(
    session: aiohttp.ClientSession,
    api_key: str,
    channel_id: str,
) -> int | None:
    try:
        channel = await _get_channel(session, api_key, channel_id, "statistics")
        if channel is None:
            return None
        count = int(channel["statistics"]["subscriberCount"])
        logger.info("YouTube subscribers: %d", count)
        return count
    except Exception:
        logger.exception("Failed to collect YouTube subscribers")
        return None


async def fetch_youtube_channel(
    session: aiohttp.ClientSession, api_key: str, channel_id: str
) -> dict[str, str] | None:
    try:
        channel = await _get_channel(session, api_key, channel_id, "snippet,statistics")
        if channel is None:
            return None
        snippet = channel["snippet"]
        return {
            "title": snippet.get("title", ""),
            "handle": snippet.get("customUrl", ""),
            "description": snippet.get("description", ""),
            "avatar": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
            "videos": channel["statistics"].get("videoCount", "0"),
        }
    except Exception:
        logger.exception("Failed to fetch YouTube channel profile")
        return None


class YouTube(Platform):
    id = "youtube"
    label = "YouTube"
    short = "YT"
    account = "Google-аккаунт канала"
    profile_fields = {
        "title": ("название канала", TEXT),
        "handle": ("@handle канала", TEXT),
        "description": ("описание канала", TEXT),
        "avatar": ("аватарка канала", IMAGE),
        "videos": ("видео на канале", COUNT),
    }

    def enabled(self, config) -> bool:
        return bool(config.youtube_api_key and config.youtube_channel_id)

    def target(self, config) -> str:
        return config.youtube_channel_id or ""

    async def collect(self, ctx: Context) -> Snapshot:
        count = await collect_youtube(ctx.session, ctx.config.youtube_api_key, ctx.config.youtube_channel_id)
        return Snapshot(count, error=count is None)

    async def fetch_profile(self, ctx: Context) -> dict[str, str] | None:
        return await fetch_youtube_channel(
            ctx.session, ctx.config.youtube_api_key, ctx.config.youtube_channel_id
        )

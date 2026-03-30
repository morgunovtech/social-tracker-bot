from __future__ import annotations

import logging

from telegram import Bot

logger = logging.getLogger(__name__)


async def collect_telegram(bot: Bot, channel_id: str) -> int | None:
    try:
        count = await bot.get_chat_member_count(chat_id=channel_id)
        logger.info("Telegram subscribers: %d", count)
        return count
    except Exception:
        logger.exception("Failed to collect Telegram subscribers")
        return None

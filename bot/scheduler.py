from __future__ import annotations

import logging

import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot

from bot.collectors.linkedin import collect_linkedin
from bot.collectors.telegram import collect_telegram
from bot.collectors.youtube import collect_youtube
from bot.config import Config
from bot.db import Database
from bot.reporter import build_report

logger = logging.getLogger(__name__)


async def collect_and_report(bot: Bot, config: Config, db: Database) -> str:
    errors: dict[str, bool] = {}

    async with aiohttp.ClientSession() as session:
        # Telegram
        tg_count = await collect_telegram(bot, config.telegram_channel_id)
        if tg_count is not None:
            await db.upsert("telegram", tg_count)
        else:
            errors["telegram"] = True

        # YouTube
        yt_count = await collect_youtube(session, config.youtube_api_key, config.youtube_channel_id)
        if yt_count is not None:
            await db.upsert("youtube", yt_count)
        else:
            errors["youtube"] = True

        # LinkedIn
        li_count = await collect_linkedin(session, config.rapidapi_key, config.linkedin_profile_url)
        if li_count is not None:
            await db.upsert("linkedin", li_count)
        else:
            # Only mark error if keys are configured
            if config.rapidapi_key and config.linkedin_profile_url:
                errors["linkedin"] = True

    report = await build_report(db, errors=errors)
    return report


async def _scheduled_job(bot: Bot, config: Config, db: Database) -> None:
    logger.info("Running scheduled data collection")
    try:
        report = await collect_and_report(bot, config, db)
        await bot.send_message(chat_id=config.admin_chat_id, text=report)
        logger.info("Daily report sent to admin")
    except Exception:
        logger.exception("Scheduled job failed")


def setup_scheduler(bot: Bot, config: Config, db: Database) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _scheduled_job,
        trigger=CronTrigger(hour=config.report_hour_utc, minute=config.report_minute),
        args=[bot, config, db],
        id="daily_report",
        replace_existing=True,
    )
    return scheduler

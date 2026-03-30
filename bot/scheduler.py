from __future__ import annotations

import logging
from datetime import datetime

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


def _is_monday() -> bool:
    return datetime.utcnow().weekday() == 0


async def collect_and_report(bot: Bot, config: Config, db: Database, force_linkedin: bool = False) -> str:
    errors: dict[str, bool] = {}

    async with aiohttp.ClientSession() as session:
        tg_count = await collect_telegram(bot, config.telegram_channel_id)
        if tg_count is not None:
            await db.upsert("telegram", tg_count)
        else:
            errors["telegram"] = True

        yt_count = await collect_youtube(session, config.youtube_api_key, config.youtube_channel_id)
        if yt_count is not None:
            await db.upsert("youtube", yt_count)
        else:
            errors["youtube"] = True

        if force_linkedin or _is_monday():
            li_count = await collect_linkedin(session, config.rapidapi_key, config.linkedin_profile_url)
            if li_count is not None:
                await db.upsert("linkedin", li_count)
            elif config.rapidapi_key and config.linkedin_profile_url:
                errors["linkedin"] = True

    report = await build_report(db, errors=errors)
    return report


async def _scheduled_job(bot: Bot, config: Config, db: Database) -> None:
    logger.info("Running scheduled data collection (Monday LinkedIn: %s)", _is_monday())
    try:
        report = await collect_and_report(bot, config, db)
        await bot.send_message(chat_id=config.admin_chat_id, text=report)
        logger.info("Daily report sent to admin")
    except Exception:
        logger.exception("Scheduled job failed")


async def get_report_time(db: Database, config: Config) -> tuple[int, int]:
    """Return (hour, minute) from DB, falling back to config."""
    stored = await db.get_setting("report_time")
    if stored:
        try:
            h, m = stored.split(":")
            return int(h), int(m)
        except (ValueError, AttributeError):
            pass
    return config.report_hour_utc, config.report_minute


def reschedule(scheduler: AsyncIOScheduler, bot: Bot, config: Config, db: Database, hour: int, minute: int) -> None:
    scheduler.reschedule_job(
        "daily_report",
        trigger=CronTrigger(hour=hour, minute=minute),
    )
    logger.info("Rescheduled daily report to %02d:%02d UTC", hour, minute)


async def setup_scheduler(bot: Bot, config: Config, db: Database) -> AsyncIOScheduler:
    hour, minute = await get_report_time(db, config)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _scheduled_job,
        trigger=CronTrigger(hour=hour, minute=minute),
        args=[bot, config, db],
        id="daily_report",
        replace_existing=True,
    )
    logger.info("Scheduler started: daily report at %02d:%02d UTC", hour, minute)
    return scheduler

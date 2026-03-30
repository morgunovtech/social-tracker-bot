from __future__ import annotations

import asyncio
import logging

from telegram.ext import Application

from bot.config import Config
from bot.db import Database
from bot.handlers import register_handlers
from bot.scheduler import setup_scheduler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    config = Config.from_env()
    db = Database(config.db_path)

    # Init DB synchronously before starting
    asyncio.get_event_loop().run_until_complete(db.init())

    app = Application.builder().token(config.bot_token).build()
    register_handlers(app, config, db)

    scheduler = asyncio.get_event_loop().run_until_complete(setup_scheduler(app.bot, config, db))
    scheduler.start()
    app.bot_data["scheduler"] = scheduler

    logger.info("Bot starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

from __future__ import annotations

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


async def _post_init(app: Application) -> None:
    config: Config = app.bot_data["config"]
    db: Database = app.bot_data["db"]

    await db.init()

    scheduler = await setup_scheduler(app.bot, config, db)
    scheduler.start()
    app.bot_data["scheduler"] = scheduler

    logger.info("Bot ready: scheduler + DB initialized")


async def _post_shutdown(app: Application) -> None:
    scheduler = app.bot_data.get("scheduler")
    if scheduler is not None:
        scheduler.shutdown(wait=False)


def main() -> None:
    config = Config.from_env()
    db = Database(config.db_path)

    app = (
        Application.builder()
        .token(config.bot_token)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    register_handlers(app, config, db)

    logger.info("Bot starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

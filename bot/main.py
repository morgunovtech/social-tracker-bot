from __future__ import annotations

import logging

from telegram import BotCommand
from telegram.ext import Application

from bot.config import Config
from bot.db import Database
from bot.handlers import register_handlers
from bot.scheduler import setup_scheduler
from bot.updates import report_startup_changes

# Only the entry points: everything else is a button away, and /help lists all commands.
_BOT_COMMANDS = [
    BotCommand("start", "Главная: подписчики и статус"),
    BotCommand("now", "Обновить данные"),
    BotCommand("week", "Динамика за неделю"),
    BotCommand("security", "Безопасность аккаунтов"),
    BotCommand("settings", "Настройки"),
    BotCommand("help", "Помощь и все команды"),
]

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
# httpx logs every request URL at INFO, and Bot API URLs contain the bot token.
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def _post_init(app: Application) -> None:
    config: Config = app.bot_data["config"]
    db: Database = app.bot_data["db"]

    await db.init()

    scheduler = await setup_scheduler(app.bot, config, db)
    scheduler.start()
    app.bot_data["scheduler"] = scheduler

    await app.bot.set_my_commands(_BOT_COMMANDS)

    # «🔄 Бот обновился» after a deploy; never let it block the start.
    try:
        await report_startup_changes(app.bot, config, db)
    except Exception:
        logger.exception("Startup update notice failed")

    logger.info("Bot ready: scheduler + DB initialized + commands registered")


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
    # Keep what was sent while the bot was down for a deploy; stale messages are
    # dropped by handlers.drop_stale_messages.
    app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()

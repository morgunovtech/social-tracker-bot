from __future__ import annotations

import logging

from telegram import BotCommand
from telegram.ext import Application

from bot.config import Config
from bot.db import Database
from bot.handlers import register_handlers, restore_owner
from bot.i18n import set_language, t
from bot.redact import RedactingFormatter
from bot.scheduler import setup_scheduler
from bot.updates import report_startup_changes

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
_config: Config | None = None


def secret_values() -> list[str]:
    """What must never reach a log line, as the bot knows it right now: read
    at the moment a line is written, so before the config exists only the
    patterns (bot token, keys in a query, the li_at cookie) mask."""
    c = _config
    if c is None:
        return []
    return [c.bot_token, c.youtube_api_key or "", c.instagram_access_token or "", c.linkedin_li_at or "",
            c.site_ingest_url or "", c.site_ingest_token or "", c.healthcheck_url or "",
            c.github_token or "", c.security_mail_url or "", c.security_mail_token or "",
            c.anthropic_api_key or ""]


def setup_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(RedactingFormatter(LOG_FORMAT, secret_values))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    # httpx logs every request URL at INFO — the Bot API URL with the token
    # on each call. The formatter would mask it; the line is still noise.
    logging.getLogger("httpx").setLevel(logging.WARNING)


setup_logging()
logger = logging.getLogger(__name__)


def _bot_commands() -> list[BotCommand]:
    """The / menu: only the entry points, everything else is a button away and
    /help lists all commands. Built on demand, after the language is set."""
    return [
        BotCommand("start", t("Главная: подписчики и статус")),
        BotCommand("now", t("Обновить данные")),
        BotCommand("week", t("Динамика за неделю")),
        BotCommand("security", t("Безопасность аккаунтов")),
        BotCommand("settings", t("Настройки")),
        BotCommand("help", t("Помощь и все команды")),
    ]


async def _post_init(app: Application) -> None:
    config: Config = app.bot_data["config"]
    db: Database = app.bot_data["db"]

    await db.init()
    await restore_owner(config, db)

    scheduler = await setup_scheduler(app.bot, config, db)
    scheduler.start()
    app.bot_data["scheduler"] = scheduler

    await app.bot.set_my_commands(_bot_commands())

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
    global _config
    config = Config.from_env()
    _config = config
    set_language(config.lang)
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

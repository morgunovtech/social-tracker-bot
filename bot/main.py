from __future__ import annotations

import logging

from telegram.error import InvalidToken
from telegram.ext import Application

from bot import behavior, connections, watchdog
from bot.config import Config
from bot.db import Database
from bot.handlers import (
    ALLOWED_UPDATES,
    collect_lock,
    register_handlers,
    restore_language,
    restore_owner,
    show_keyboard_once,
)
from bot.i18n import set_language
from bot.redact import RedactingFormatter
from bot.scheduler import setup_scheduler
from bot.updates import SNAPSHOT_KEY, adopt_dev_notices, report_startup_changes

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
            c.anthropic_api_key or "", c.mailbox_password or "", watchdog.known_url() or ""]


def setup_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(RedactingFormatter(LOG_FORMAT, secret_values))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    # httpx logs every request URL at INFO — the Bot API URL with the token
    # on each call. The formatter would mask it; the line is still noise.
    logging.getLogger("httpx").setLevel(logging.WARNING)


setup_logging()
logger = logging.getLogger(__name__)


async def _step(name: str, coro) -> None:
    """A start step that must not stop the bot when Telegram refuses it."""
    try:
        await coro
    except Exception:
        logger.exception("Start step «%s» failed — going on without it", name)


async def _post_init(app: Application) -> None:
    config: Config = app.bot_data["config"]
    db: Database = app.bot_data["db"]

    await db.init()
    await restore_owner(config, db)
    await restore_language(config, db)
    await connections.restore(config, db)   # networks connected from the chat
    await watchdog.url(db, config)   # an address set in the chat joins the log redactor

    scheduler = await setup_scheduler(app.bot, config, db, lock=collect_lock(app.bot_data))
    scheduler.start()
    app.bot_data["scheduler"] = scheduler

    # No ☰ command list (BOT_PRINCIPLES §2): the three buttons under the input
    # field are the way in; typed commands keep working and «📖 Что я умею»
    # lists them. Removes the list earlier versions published.
    await _step("delete_my_commands", app.bot.delete_my_commands())
    await _step("set_chat_menu_button", app.bot.set_chat_menu_button())
    await _step("bottom buttons", show_keyboard_once(app.bot, config, db))

    # «🔄 Бот обновился» after a deploy, and what the update moved in how the
    # bot behaves (bot/behavior.py); neither may block the start. The second
    # needs to know whether the bot ran before — read before the first writes.
    pending = None
    try:
        await adopt_dev_notices(db)   # before the first snapshot is written
    except Exception:
        logger.exception("Developer notices switch failed")
    try:
        pending = await behavior.detect(db, config, ran_before=await db.get_setting(SNAPSHOT_KEY) is not None)
    except Exception:
        logger.exception("Behaviour snapshot failed")
    try:
        await report_startup_changes(app.bot, config, db)
    except Exception:
        logger.exception("Startup update notice failed")
    if pending is not None:
        try:
            await behavior.announce(app.bot, config, db, pending)
        except Exception:
            logger.exception("Behaviour change notice failed")

    logger.info("Bot ready: scheduler + DB initialized")


async def _post_shutdown(app: Application) -> None:
    scheduler = app.bot_data.get("scheduler")
    if scheduler is not None:
        scheduler.shutdown(wait=False)


def build_application(config: Config, db: Database) -> Application:
    """The bot with its handlers. Updates are handled concurrently: by default
    python-telegram-bot awaits one update after another, so a /now that
    collects for half a minute (four networks, each with a timeout) held every
    other button and command until it was done. The collection itself is
    behind one lock (handlers.collect_lock), shared with the scheduler's daily
    run, so two collections never overlap."""
    app = (
        Application.builder()
        .token(config.bot_token)
        .concurrent_updates(True)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    register_handlers(app, config, db)
    return app


def main() -> None:
    """Start the bot. A setting that is wrong stops it with one readable log
    line, not a traceback: an empty or placeholder BOT_TOKEN, a bad value in
    .env (Config.from_env), a token Telegram refuses. python-telegram-bot puts
    the refused token into its exception text, and an uncaught exception is
    printed past the log formatter that would mask it."""
    global _config
    try:
        config = Config.from_env()
    except RuntimeError as e:
        logger.error("%s", e)
        raise SystemExit(1) from None
    _config = config
    set_language(config.lang)
    db = Database(config.db_path)
    app = build_application(config, db)

    logger.info("Bot starting...")
    # Keep what was sent while the bot was down for a deploy; stale messages are
    # dropped by handlers.drop_stale_messages. Joins, leaves and reactions in
    # the channel only come when asked for (ALLOWED_UPDATES).
    try:
        app.run_polling(drop_pending_updates=False, allowed_updates=list(ALLOWED_UPDATES))
    except InvalidToken:
        logger.error("Telegram refused BOT_TOKEN: revoked or mistyped? Copy it again from @BotFather "
                     "(/mybots → the bot → API Token) into .env or the Railway variables")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()

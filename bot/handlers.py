from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from bot.config import Config
from bot.db import Database
from bot.reporter import PLATFORMS, build_history_table, build_report
from bot.scheduler import collect_and_report

logger = logging.getLogger(__name__)

HELP_TEXT = """Доступные команды:

/start — Приветствие
/stats — Текущая сводка
/now — Собрать данные и показать отчёт
/linkedin <число> — Ручной ввод подписчиков LinkedIn
/history <platform> <days> — История (например: /history telegram 30)
/help — Список команд
"""


def _is_admin(update: Update, config: Config) -> bool:
    return update.effective_user is not None and update.effective_user.id == config.admin_chat_id


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Я отслеживаю подписчиков в Telegram, YouTube и LinkedIn.\n\n" + HELP_TEXT
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT)


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]

    if not _is_admin(update, config):
        await update.message.reply_text("⛔ Доступ запрещён.")
        return

    report = await build_report(db)
    await update.message.reply_text(report)


async def cmd_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]

    if not _is_admin(update, config):
        await update.message.reply_text("⛔ Доступ запрещён.")
        return

    await update.message.reply_text("⏳ Собираю данные...")
    report = await collect_and_report(context.bot, config, db)
    await update.message.reply_text(report)


async def cmd_linkedin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]

    if not _is_admin(update, config):
        await update.message.reply_text("⛔ Доступ запрещён.")
        return

    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Использование: /linkedin <число>\nПример: /linkedin 4520")
        return

    try:
        count = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Ошибка: укажите целое число.")
        return

    await db.upsert("linkedin", count, source="manual")
    await update.message.reply_text(f"✅ LinkedIn обновлён: {count:,} подписчиков (вручную)")


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]

    if not _is_admin(update, config):
        await update.message.reply_text("⛔ Доступ запрещён.")
        return

    if not context.args or len(context.args) != 2:
        await update.message.reply_text(
            "Использование: /history <platform> <days>\n"
            f"Платформы: {', '.join(PLATFORMS)}\n"
            "Пример: /history telegram 30"
        )
        return

    platform = context.args[0].lower()
    if platform not in PLATFORMS:
        await update.message.reply_text(f"Неизвестная платформа. Доступны: {', '.join(PLATFORMS)}")
        return

    try:
        days = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Ошибка: количество дней должно быть числом.")
        return

    table = await build_history_table(db, platform, days)
    await update.message.reply_text(table, parse_mode="Markdown")


def register_handlers(app, config: Config, db: Database) -> None:
    app.bot_data["config"] = config
    app.bot_data["db"] = db

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("now", cmd_now))
    app.add_handler(CommandHandler("linkedin", cmd_linkedin))
    app.add_handler(CommandHandler("history", cmd_history))

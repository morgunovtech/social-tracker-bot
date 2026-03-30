from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from bot.config import Config
from bot.db import Database
from bot.reporter import PLATFORMS, build_history_table, build_report, build_week_report
from bot.scheduler import collect_and_report

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyboards
# ---------------------------------------------------------------------------

def _main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Статистика", callback_data="stats"),
            InlineKeyboardButton("▶️ Собрать сейчас", callback_data="now"),
        ],
        [
            InlineKeyboardButton("📈 История", callback_data="history"),
            InlineKeyboardButton("📅 Неделя", callback_data="week"),
        ],
        [
            InlineKeyboardButton("✏️ LinkedIn", callback_data="linkedin_prompt"),
        ],
    ])


def _history_platforms() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(label.capitalize(), callback_data=f"history:{p}")
        for p, label in [("telegram", "Telegram"), ("youtube", "YouTube"), ("linkedin", "LinkedIn")]
    ]
    return InlineKeyboardMarkup([buttons, [InlineKeyboardButton("← Назад", callback_data="menu")]])


def _history_periods(platform: str) -> InlineKeyboardMarkup:
    periods = [
        InlineKeyboardButton(f"{d} дней", callback_data=f"history:{platform}:{d}")
        for d in [7, 14, 30]
    ]
    return InlineKeyboardMarkup([periods, [InlineKeyboardButton("← Назад", callback_data="history")]])


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------

def _is_admin(update: Update, config: Config) -> bool:
    user = update.effective_user
    return user is not None and user.id == config.admin_chat_id


async def _deny(update: Update) -> None:
    if update.callback_query:
        await update.callback_query.answer("⛔ Доступ запрещён.", show_alert=True)
    elif update.message:
        await update.message.reply_text("⛔ Доступ запрещён.")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    if not _is_admin(update, config):
        await update.message.reply_text("Привет! Этот бот только для администратора.")
        return
    await update.message.reply_text(
        "Привет! Я отслеживаю подписчиков в Telegram, YouTube и LinkedIn.",
        reply_markup=_main_menu(),
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Команды:\n\n"
        "/stats — текущая сводка\n"
        "/now — собрать данные прямо сейчас\n"
        "/week — недельный дайджест\n"
        "/linkedin <число> — ввести LinkedIn вручную\n"
        "/history <platform> <days> — история\n",
        reply_markup=_main_menu(),
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]
    if not _is_admin(update, config):
        await _deny(update)
        return
    report = await build_report(db)
    await update.message.reply_text(report, reply_markup=_main_menu())


async def cmd_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]
    if not _is_admin(update, config):
        await _deny(update)
        return
    await update.message.reply_text("⏳ Собираю данные...")
    report = await collect_and_report(context.bot, config, db, force_linkedin=True)
    await update.message.reply_text(report, reply_markup=_main_menu())


async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]
    if not _is_admin(update, config):
        await _deny(update)
        return
    report = await build_week_report(db)
    await update.message.reply_text(report, reply_markup=_main_menu())


async def cmd_linkedin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]
    if not _is_admin(update, config):
        await _deny(update)
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
    await update.message.reply_text(
        f"✅ LinkedIn обновлён: {count:,} подписчиков (вручную)",
        reply_markup=_main_menu(),
    )


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]
    if not _is_admin(update, config):
        await _deny(update)
        return
    # With args: /history telegram 30
    if context.args and len(context.args) == 2:
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
        await update.message.reply_text(table, parse_mode="Markdown", reply_markup=_main_menu())
    else:
        # No args: show platform picker
        await update.message.reply_text("Выберите платформу:", reply_markup=_history_platforms())


# ---------------------------------------------------------------------------
# Callback query handler
# ---------------------------------------------------------------------------

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]

    if not _is_admin(update, config):
        await _deny(update)
        return

    data = query.data

    if data == "menu":
        await query.edit_message_text("Выберите действие:", reply_markup=_main_menu())

    elif data == "stats":
        report = await build_report(db)
        await query.edit_message_text(report, reply_markup=_main_menu())

    elif data == "now":
        await query.edit_message_text("⏳ Собираю данные...")
        report = await collect_and_report(context.bot, config, db, force_linkedin=True)
        await query.edit_message_text(report, reply_markup=_main_menu())

    elif data == "week":
        report = await build_week_report(db)
        await query.edit_message_text(report, reply_markup=_main_menu())

    elif data == "linkedin_prompt":
        await query.edit_message_text(
            "Отправьте команду с числом подписчиков:\n\n/linkedin 4520",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="menu")]]),
        )

    elif data == "history":
        await query.edit_message_text("Выберите платформу:", reply_markup=_history_platforms())

    elif data.startswith("history:"):
        parts = data.split(":")
        if len(parts) == 2:
            # Platform selected — show period picker
            platform = parts[1]
            label = platform.capitalize()
            await query.edit_message_text(
                f"Платформа: {label}\nВыберите период:",
                reply_markup=_history_periods(platform),
            )
        elif len(parts) == 3:
            # Period selected — show table
            platform, days_str = parts[1], parts[2]
            days = int(days_str)
            table = await build_history_table(db, platform, days)
            await query.edit_message_text(
                table,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data=f"history:{platform}")]]),
            )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_handlers(app, config: Config, db: Database) -> None:
    app.bot_data["config"] = config
    app.bot_data["db"] = db

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("now", cmd_now))
    app.add_handler(CommandHandler("week", cmd_week))
    app.add_handler(CommandHandler("linkedin", cmd_linkedin))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CallbackQueryHandler(on_callback))

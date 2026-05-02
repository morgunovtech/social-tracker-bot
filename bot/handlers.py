from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# ConversationHandler states
LI_AWAITING_NUMBER = 1

from bot.config import Config
from bot.db import Database
from bot.reporter import PLATFORMS, build_history_all, build_history_table, build_report, build_week_report
from bot.scheduler import (
    collect_and_report,
    get_report_schedule,
    is_quiet_mode,
    normalize_dow,
    reschedule,
)

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
            InlineKeyboardButton("⚙️ Настройки", callback_data="settings"),
        ],
    ])


def _history_platforms() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton("Все", callback_data="history:all"),
        InlineKeyboardButton("Telegram", callback_data="history:telegram"),
        InlineKeyboardButton("YouTube", callback_data="history:youtube"),
        InlineKeyboardButton("LinkedIn", callback_data="history:linkedin"),
    ]
    return InlineKeyboardMarkup([buttons, [InlineKeyboardButton("← Назад", callback_data="menu")]])


def _history_periods(platform: str) -> InlineKeyboardMarkup:
    periods = [
        InlineKeyboardButton(f"{d} дней", callback_data=f"history:{platform}:{d}")
        for d in [7, 14, 30]
    ]
    return InlineKeyboardMarkup([periods, [InlineKeyboardButton("← Назад", callback_data="history")]])


def _settings_keyboard(quiet: bool) -> InlineKeyboardMarkup:
    quiet_label = "🔕 Тихий режим: ВКЛ" if quiet else "🔔 Тихий режим: выкл"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(quiet_label, callback_data="quiet:toggle")],
        [InlineKeyboardButton("← Назад", callback_data="menu")],
    ])


def _dow_pretty(dow: str) -> str:
    if dow == "*":
        return "каждый день"
    names = {
        "mon": "Пн", "tue": "Вт", "wed": "Ср", "thu": "Чт",
        "fri": "Пт", "sat": "Сб", "sun": "Вс",
    }
    if "-" in dow and "," not in dow:
        a, _, b = dow.partition("-")
        return f"{names.get(a, a)}–{names.get(b, b)}"
    return ", ".join(names.get(p, p) for p in dow.split(","))


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
        "/history [platform] [days] — история\n"
        "/settime HH:MM — изменить время отчёта (UTC)\n"
        "/setday <дни> — изменить день недели (sat / mon-fri / mon,thu / daily)\n"
        "/setquiet on|off — пропускать пуш, если за неделю ничего не изменилось\n",
        reply_markup=_main_menu(),
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]
    if not _is_admin(update, config):
        await _deny(update)
        return
    report, _ = await build_report(db, linkedin_stale_days=config.linkedin_stale_days)
    await update.message.reply_text(report, reply_markup=_main_menu())


async def cmd_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]
    if not _is_admin(update, config):
        await _deny(update)
        return
    await update.message.reply_text("⏳ Собираю данные...")
    report, _ = await collect_and_report(context.bot, config, db, force_linkedin=True)
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
    if context.args and len(context.args) == 2:
        platform = context.args[0].lower()
        try:
            days = int(context.args[1])
        except ValueError:
            await update.message.reply_text("Ошибка: количество дней должно быть числом.")
            return
        if platform == "all":
            table = await build_history_all(db, days)
        elif platform in PLATFORMS:
            table = await build_history_table(db, platform, days)
        else:
            await update.message.reply_text(f"Неизвестная платформа. Доступны: all, {', '.join(PLATFORMS)}")
            return
        await update.message.reply_text(table, parse_mode="Markdown", reply_markup=_main_menu())
    else:
        await update.message.reply_text("Выберите платформу:", reply_markup=_history_platforms())


async def cmd_settime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]
    scheduler = context.bot_data["scheduler"]

    if not _is_admin(update, config):
        await _deny(update)
        return

    if not context.args or len(context.args) != 1:
        dow, hour, minute = await get_report_schedule(db, config)
        await update.message.reply_text(
            f"Текущее расписание: {_dow_pretty(dow)} в {hour:02d}:{minute:02d} UTC\n\n"
            "Использование: /settime HH:MM\nПример: /settime 08:00"
        )
        return

    try:
        h_str, m_str = context.args[0].split(":")
        hour, minute = int(h_str), int(m_str)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except (ValueError, AttributeError):
        await update.message.reply_text("Неверный формат. Используйте HH:MM, например: /settime 08:00")
        return

    await db.set_setting("report_time", f"{hour:02d}:{minute:02d}")
    dow, _, _ = await get_report_schedule(db, config)
    reschedule(scheduler, dow, hour, minute)
    await update.message.reply_text(
        f"✅ Время отчёта изменено: {hour:02d}:{minute:02d} UTC ({_dow_pretty(dow)})",
        reply_markup=_main_menu(),
    )


async def cmd_setday(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]
    scheduler = context.bot_data["scheduler"]

    if not _is_admin(update, config):
        await _deny(update)
        return

    if not context.args or len(context.args) != 1:
        dow, hour, minute = await get_report_schedule(db, config)
        await update.message.reply_text(
            f"Текущее расписание: {_dow_pretty(dow)} в {hour:02d}:{minute:02d} UTC\n\n"
            "Использование: /setday <дни>\n"
            "Примеры:\n"
            "  /setday sat — суббота\n"
            "  /setday mon,thu — понедельник и четверг\n"
            "  /setday mon-fri — будни\n"
            "  /setday daily — каждый день"
        )
        return

    try:
        normalized = normalize_dow(context.args[0])
    except ValueError as e:
        await update.message.reply_text(
            f"❌ {e}\nДопустимо: mon, tue, wed, thu, fri, sat, sun, daily, mon-fri, mon,thu"
        )
        return

    await db.set_setting("report_dow", normalized)
    _, hour, minute = await get_report_schedule(db, config)
    reschedule(scheduler, normalized, hour, minute)
    await update.message.reply_text(
        f"✅ День отчёта: {_dow_pretty(normalized)} в {hour:02d}:{minute:02d} UTC",
        reply_markup=_main_menu(),
    )


async def cmd_setquiet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]

    if not _is_admin(update, config):
        await _deny(update)
        return

    if not context.args or context.args[0].lower() not in ("on", "off"):
        current = await is_quiet_mode(db, config)
        state = "ВКЛ" if current else "выкл"
        await update.message.reply_text(
            f"Тихий режим: {state}\n\n"
            "Использование: /setquiet on | off\n"
            "Если включён — бот не присылает отчёт, когда за неделю ничего не изменилось."
        )
        return

    enabled = context.args[0].lower() == "on"
    await db.set_setting("quiet_if_no_change", "1" if enabled else "0")
    await update.message.reply_text(
        f"✅ Тихий режим: {'ВКЛ' if enabled else 'выкл'}",
        reply_markup=_main_menu(),
    )


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
        report, _ = await build_report(db, linkedin_stale_days=config.linkedin_stale_days)
        await query.edit_message_text(report, reply_markup=_main_menu())

    elif data == "now":
        await query.edit_message_text("⏳ Собираю данные...")
        report, _ = await collect_and_report(context.bot, config, db, force_linkedin=True)
        await query.edit_message_text(report, reply_markup=_main_menu())

    elif data == "week":
        report = await build_week_report(db)
        await query.edit_message_text(report, reply_markup=_main_menu())

    elif data == "settings":
        dow, hour, minute = await get_report_schedule(db, config)
        quiet = await is_quiet_mode(db, config)
        await query.edit_message_text(
            f"⚙️ Настройки\n\n"
            f"Расписание: {_dow_pretty(dow)} в {hour:02d}:{minute:02d} UTC\n"
            f"Изменить: /settime HH:MM, /setday sat\n",
            reply_markup=_settings_keyboard(quiet),
        )

    elif data == "quiet:toggle":
        current = await is_quiet_mode(db, config)
        new_value = not current
        await db.set_setting("quiet_if_no_change", "1" if new_value else "0")
        dow, hour, minute = await get_report_schedule(db, config)
        await query.edit_message_text(
            f"⚙️ Настройки\n\n"
            f"Расписание: {_dow_pretty(dow)} в {hour:02d}:{minute:02d} UTC\n"
            f"Изменить: /settime HH:MM, /setday sat\n",
            reply_markup=_settings_keyboard(new_value),
        )

    elif data == "history":
        await query.edit_message_text("Выберите платформу:", reply_markup=_history_platforms())

    elif data.startswith("history:"):
        parts = data.split(":")
        if len(parts) == 2:
            platform = parts[1]
            label = "Все платформы" if platform == "all" else platform.capitalize()
            await query.edit_message_text(
                f"Платформа: {label}\nВыберите период:",
                reply_markup=_history_periods(platform),
            )
        elif len(parts) == 3:
            platform, days_str = parts[1], parts[2]
            days = int(days_str)
            if platform == "all":
                table = await build_history_all(db, days)
            else:
                table = await build_history_table(db, platform, days)
            await query.edit_message_text(
                table,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data=f"history:{platform}")]]),
            )


# ---------------------------------------------------------------------------
# LinkedIn inline-input conversation
# ---------------------------------------------------------------------------

async def li_conv_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    config: Config = context.bot_data["config"]
    if not _is_admin(update, config):
        await _deny(update)
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Введи число подписчиков LinkedIn одним сообщением.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Отмена", callback_data="li_cancel")],
        ]),
    )
    return LI_AWAITING_NUMBER


async def li_conv_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]
    if not _is_admin(update, config):
        await _deny(update)
        return ConversationHandler.END

    text = (update.message.text or "").strip().replace(" ", "").replace(",", "")
    try:
        count = int(text)
        if count < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Это не число. Попробуй ещё раз или /cancel.")
        return LI_AWAITING_NUMBER

    await db.upsert("linkedin", count, source="manual")
    await update.message.reply_text(
        f"✅ LinkedIn обновлён: {count:,} подписчиков (вручную)",
        reply_markup=_main_menu(),
    )
    return ConversationHandler.END


async def li_conv_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Отменено.", reply_markup=_main_menu())
    elif update.message:
        await update.message.reply_text("Отменено.", reply_markup=_main_menu())
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_handlers(app, config: Config, db: Database) -> None:
    app.bot_data["config"] = config
    app.bot_data["db"] = db

    li_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(li_conv_start, pattern="^linkedin_prompt$")],
        states={
            LI_AWAITING_NUMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, li_conv_number),
                CallbackQueryHandler(li_conv_cancel, pattern="^li_cancel$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", li_conv_cancel)],
    )
    # Conversation must be registered before the catch-all CallbackQueryHandler
    app.add_handler(li_conv)

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("now", cmd_now))
    app.add_handler(CommandHandler("week", cmd_week))
    app.add_handler(CommandHandler("linkedin", cmd_linkedin))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("settime", cmd_settime))
    app.add_handler(CommandHandler("setday", cmd_setday))
    app.add_handler(CommandHandler("setquiet", cmd_setquiet))
    app.add_handler(CallbackQueryHandler(on_callback))

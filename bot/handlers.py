from __future__ import annotations

import logging
import os
import platform
import re
import tempfile
from datetime import timedelta

import aiohttp
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.error import BadRequest, Conflict, NetworkError
from telegram.ext import (
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    TypeHandler,
    filters,
)

from bot import monitors, platforms
from bot.config import Config, normalize_dow
from bot.db import Database, utcnow
from bot.monitors import hygiene
from bot.platforms import BY_ID, LABELS, PLATFORM_IDS, PLATFORMS
from bot.platforms.base import Platform
from bot.platforms.linkedin import COOKIE_AGING_DAYS, collect_linkedin, get_cookie_age_days, plausible_count
from bot.reporter import build_history_all, build_history_table, build_week_report
from bot.scheduler import (
    _build_chart_png,
    build_stats,
    collect_and_report,
    get_report_schedule,
    is_quiet_mode,
    reschedule,
    send_alerts,
)

logger = logging.getLogger(__name__)

# ConversationHandler states
LI_AWAITING_NUMBER = 1

# End a dangling LinkedIn-input conversation after this many seconds of silence.
LI_CONV_TIMEOUT = 120

# Longest /history period: keeps the table under Telegram's 4096-char message limit.
HISTORY_MAX_DAYS = 90

# Bot API getFile refuses files above 20 MB.
RESTORE_MAX_BYTES = 20 * 1024 * 1024

# Messages queued while the bot restarts (a deploy) are handled after start;
# older ones (a long outage) are dropped rather than replayed.
PENDING_MAX_AGE = timedelta(minutes=10)

# Persistent reply-keyboard label. Tapping this sends the same text back,
# which our MessageHandler maps to /start.
MENU_BUTTON_TEXT = "📊 Меню"


def _persistent_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(MENU_BUTTON_TEXT)]],
        resize_keyboard=True,
        is_persistent=True,
    )


async def _safe_edit(query, text: str, **kwargs) -> None:
    """edit_message_text that ignores Telegram's 'Message is not modified'.

    Repeated taps on the same inline button produce identical content; without
    this the second tap raises BadRequest and looks like a dead button.
    """
    try:
        await query.edit_message_text(text, **kwargs)
    except BadRequest as e:
        if "message is not modified" not in str(e).lower():
            raise

# ---------------------------------------------------------------------------
# Keyboards
# ---------------------------------------------------------------------------

def _main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Статистика", callback_data="stats"),
            InlineKeyboardButton("🛡 Безопасность", callback_data="sec"),
        ],
        [
            InlineKeyboardButton("▶️ Собрать сейчас", callback_data="now"),
            InlineKeyboardButton("📈 История", callback_data="history"),
        ],
        [
            InlineKeyboardButton("📅 Неделя", callback_data="week"),
            InlineKeyboardButton("🧩 Модули", callback_data="mod"),
        ],
        [
            InlineKeyboardButton("✏️ LinkedIn", callback_data="linkedin_prompt"),
            InlineKeyboardButton("⚙️ Настройки", callback_data="settings"),
        ],
    ])


def _rows(buttons: list[InlineKeyboardButton], per_row: int = 2) -> list[list[InlineKeyboardButton]]:
    return [buttons[i : i + per_row] for i in range(0, len(buttons), per_row)]


def _security_keyboard(config: Config) -> InlineKeyboardMarkup:
    edits = [InlineKeyboardButton(f"✏️ {p.label}", callback_data=f"sec:edit:{p.id}") for p in platforms.enabled(config)]
    return InlineKeyboardMarkup(_rows(edits) + [[InlineKeyboardButton("← Назад", callback_data="menu")]])


async def _checklist_screen(db: Database, platform: Platform) -> tuple[str, InlineKeyboardMarkup]:
    """One account's checklist: numbered items in the text, a row of answers per item."""
    ans = await hygiene.answers(db, platform)
    lines = [f"✏️ {platform.label} — {platform.account}", "", "Отметь, как сейчас. Пароль вводить не нужно.", ""]
    rows: list[list[InlineKeyboardButton]] = []
    checklist = hygiene.items(platform)
    for n, item in enumerate(checklist, 1):
        current = next((c for c in item.choices if c.value == ans.get(item.key)), None)
        lines.append(f"{n}. {item.label}: {current.button if current else '—'}")
        rows.append([
            InlineKeyboardButton(
                f"{n} · {'✅ ' if c is current else ''}{c.button}",
                callback_data=f"sec:set:{platform.id}:{item.key}:{c.value}",
            )
            for c in item.choices
        ])
    n = len(checklist) + 1
    age = hygiene.password_age(ans, utcnow().date())
    when = "—" if age is None else "сегодня" if age == 0 else f"{age} дн. назад"
    lines.append(f"{n}. Последняя смена пароля: {when}")
    ages = [
        InlineKeyboardButton(f"{n} · {label}", callback_data=f"sec:pwd:{platform.id}:{days}")
        for label, days in hygiene.PASSWORD_AGES.items()
    ]
    rows += _rows(ages)
    rows.append([InlineKeyboardButton("← К безопасности", callback_data="sec")])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


async def _modules_screen(db: Database, config: Config) -> tuple[str, InlineKeyboardMarkup]:
    lines = ["🧩 Модули", "", "Платформы (подключаются в .env):"]
    for p in PLATFORMS:
        lines.append(f"✅ {p.label} — {p.target(config)}" if p.enabled(config) else f"⚪ {p.label} — не подключено")
    lines += ["", "Мониторинги:"]
    toggles: list[InlineKeyboardButton] = []
    for m in monitors.MONITORS:
        if not m.requires(config):
            lines.append(f"⚪ {m.label} — нужно: {m.needs}")
            continue
        on = await monitors.is_switched_on(db, m.id)
        lines.append(f"{'✅' if on else '⏸'} {m.label} — {m.description}")
        toggles.append(InlineKeyboardButton(f"{m.label}: {'вкл' if on else 'выкл'}", callback_data=f"mod:{m.id}"))
    keyboard = _rows(toggles) + [[InlineKeyboardButton("← Назад", callback_data="menu")]]
    return "\n".join(lines), InlineKeyboardMarkup(keyboard)


def _history_platforms() -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton("Все", callback_data="history:all")] + [
        InlineKeyboardButton(p.label, callback_data=f"history:{p.id}") for p in PLATFORMS
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


def _settings_text(dow: str, hour: int, minute: int, config: Config) -> str:
    build = f"сборка {config.app_commit[:7]} · " if config.app_commit else ""
    return (
        "⚙️ Настройки\n\n"
        f"Расписание: {_dow_pretty(dow)} в {hour:02d}:{minute:02d} UTC\n"
        "Изменить: /settime HH:MM, /setday sat\n\n"
        f"Версия: {build}Python {platform.python_version()}"
    )


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


async def _answer(query, text: str | None = None, show_alert: bool = False) -> None:
    """query.answer() that survives a press made while the bot was restarting:
    Telegram refuses to answer an old query, but the action itself still runs."""
    try:
        await query.answer(text, show_alert=show_alert)
    except BadRequest as e:
        reason = str(e).lower()
        if "query is too old" not in reason and "query id is invalid" not in reason:
            raise
        logger.info("Late callback answer skipped: %s", e)


async def _deny(update: Update) -> None:
    if update.callback_query:
        await _answer(update.callback_query, "⛔ Доступ запрещён.", show_alert=True)
    elif update.message:
        await update.message.reply_text("⛔ Доступ запрещён.")


async def drop_stale_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Runs before every handler. A message queued during a deploy restart is
    handled; one older than PENDING_MAX_AGE is dropped, so a /now from hours
    ago doesn't fire. Button presses carry no send time and always pass."""
    message = update.message
    if message is not None and message.date is not None and utcnow() - message.date > PENDING_MAX_AGE:
        logger.info("Dropping a message queued for %s", utcnow() - message.date)
        raise ApplicationHandlerStop


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log every unhandled error; tell the admin when their own action failed."""
    if isinstance(context.error, Conflict):
        # A second instance is still polling: Railway overlaps deploys for a few seconds.
        logger.warning("Polling conflict (another instance running): %s", context.error)
        return
    if update is None and isinstance(context.error, NetworkError):
        # Polling hiccup (e.g. no network yet right after start); PTB retries by itself.
        logger.warning("Polling network error, retrying: %s", context.error)
        return
    logger.error("Unhandled error", exc_info=context.error)
    config: Config = context.bot_data["config"]
    if isinstance(update, Update) and _is_admin(update, config):
        try:
            await context.bot.send_message(
                chat_id=config.admin_chat_id,
                text=f"⚠️ Не получилось: {type(context.error).__name__}. Подробности в логах.",
            )
        except Exception:
            logger.exception("Error notice send failed")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    if not _is_admin(update, config):
        await update.message.reply_text("Привет! Этот бот только для администратора.")
        return
    await update.message.reply_text(
        "Привет! Я слежу за подписчиками и безопасностью твоих аккаунтов: падения и накрутка, "
        "смена названия, ссылок и админов, письма о новых входах и смене пароля.\n"
        "Кнопка «📊 Меню» внизу экрана всегда вызывает это меню.",
        reply_markup=_persistent_keyboard(),
    )
    await update.message.reply_text("Меню:", reply_markup=_main_menu())


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    if not _is_admin(update, config):
        await _deny(update)
        return
    await update.message.reply_text(
        "Команды:\n\n"
        "/stats — текущая сводка\n"
        "/now — собрать данные прямо сейчас\n"
        "/week — недельный дайджест\n"
        "/security — балл безопасности и чек-лист: 2FA, резервные коды, пароли\n"
        "/modules — что подключено, включить или выключить мониторинги\n"
        "/linkedin <число> — ввести LinkedIn вручную\n"
        "/history [platform] [days] — история\n"
        "/settime HH:MM — изменить время отчёта (UTC)\n"
        "/setday <дни> — изменить день недели (sat / mon-fri / mon,thu / daily)\n"
        "/setquiet on|off — пропускать пуш, если за неделю ничего не изменилось\n"
        "/setcookie <li_at> — обновить LinkedIn cookie (с проверкой)\n"
        "/cookieage — возраст текущего LinkedIn cookie\n"
        "/restore — вернуть историю из бэкапа (ответом на сообщение с файлом)\n",
        reply_markup=_main_menu(),
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]
    if not _is_admin(update, config):
        await _deny(update)
        return
    report, _ = await build_stats(db, config)
    await update.message.reply_text(report, reply_markup=_main_menu())


async def cmd_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]
    if not _is_admin(update, config):
        await _deny(update)
        return
    await update.message.reply_text("⏳ Собираю данные...")
    outcome = await collect_and_report(context.bot, config, db)
    await update.message.reply_text(outcome.report, reply_markup=_main_menu())
    await send_alerts(context.bot, config, db, outcome)


async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]
    if not _is_admin(update, config):
        await _deny(update)
        return
    report = await build_week_report(db)
    await update.message.reply_text(report, reply_markup=_main_menu())
    chart = await _build_chart_png(db)
    if chart:
        await update.message.reply_photo(chart, caption="📉 Динамика за 30 дней")


async def cmd_security(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]
    if not _is_admin(update, config):
        await _deny(update)
        return
    await update.message.reply_text(await hygiene.render(db, config), reply_markup=_security_keyboard(config))


async def cmd_modules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]
    if not _is_admin(update, config):
        await _deny(update)
        return
    text, keyboard = await _modules_screen(db, config)
    await update.message.reply_text(text, reply_markup=keyboard)


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
        if not 1 <= days <= HISTORY_MAX_DAYS:
            await update.message.reply_text(f"Ошибка: количество дней — от 1 до {HISTORY_MAX_DAYS}.")
            return
        if platform == "all":
            table = await build_history_all(db, days)
        elif platform in PLATFORM_IDS:
            table = await build_history_table(db, platform, days)
        else:
            await update.message.reply_text(f"Неизвестная платформа. Доступны: all, {', '.join(PLATFORM_IDS)}")
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


async def cmd_setcookie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]

    if not _is_admin(update, config):
        await _deny(update)
        return

    if not context.args:
        await update.message.reply_text(
            "Использование: /setcookie <значение li_at>\n\n"
            "Где взять: linkedin.com → DevTools → Application → Cookies → `li_at` → Value\n"
            "Текущий возраст: /cookieage"
        )
        return

    # Don't leave the secret sitting in chat history — delete it before any
    # check can bail out early. Replies go to the chat: the message is gone.
    chat = update.effective_chat
    deleted = True
    try:
        await update.message.delete()
    except Exception:
        deleted = False
    note = "" if deleted else "\n⚠️ Удали сообщение с cookie из чата вручную."

    cookie = " ".join(context.args).strip()
    if len(cookie) < 50:
        await chat.send_message(f"❌ Это не похоже на cookie (слишком короткое).{note}")
        return

    if not config.linkedin_profile_url:
        await chat.send_message(f"❌ Не задан LINKEDIN_PROFILE_URL — нечего проверять.{note}")
        return

    await chat.send_message("⏳ Проверяю cookie...")

    prev_row = await db.get_latest("linkedin")
    prev = prev_row["count"] if prev_row else None
    async with aiohttp.ClientSession() as session:
        count, source = await collect_linkedin(
            session,
            profile_url=config.linkedin_profile_url,
            li_at=cookie,
            prev=prev,
        )

    if count is None:
        reason = (
            "LinkedIn отклонил cookie"
            if source == "cookie_expired"
            else "не удалось получить число подписчиков (подробности в логах)"
        )
        await chat.send_message(
            f"❌ Cookie не сохранён: {reason}.\n"
            f"Проверь, что скопировал значение целиком (без × или других левых символов).{note}"
        )
        return

    await db.set_setting("linkedin_li_at", cookie)
    await db.set_setting("linkedin_li_at_set_at", utcnow().isoformat())
    await db.set_setting("cookie_expired_alerted", "0")  # fresh cookie — re-arm the alert

    # Same guard as the daily collect: a value far from the stored one is
    # likely someone else's counter and must not become the new baseline.
    if plausible_count(prev, count):
        await db.upsert("linkedin", count, source="cookie")
        fetched = f"Тест-фетч: {count:,} подписчиков."
    else:
        fetched = (
            f"Тест-фетч вернул {count:,} — слишком далеко от прошлого {prev:,}, число не записано.\n"
            "Если оно верное, задай его через /linkedin <число>."
        )

    await chat.send_message(
        f"✅ Cookie сохранён. {fetched}\n"
        f"Примерный срок жизни — ~12 месяцев. Бот предупредит за месяц до конца.{note}",
        reply_markup=_main_menu(),
    )


async def cmd_cookieage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]

    if not _is_admin(update, config):
        await _deny(update)
        return

    age = await get_cookie_age_days(db)
    has_db_cookie = bool(await db.get_setting("linkedin_li_at"))
    has_env_cookie = bool(config.linkedin_li_at)

    if age is not None:
        days_left = max(0, COOKIE_AGING_DAYS - age)
        status = "⚠️ пора обновить" if age >= COOKIE_AGING_DAYS else f"осталось ~{days_left} дней до напоминания"
        await update.message.reply_text(
            f"🍪 LinkedIn cookie\n\n"
            f"Установлен через /setcookie {age} дней назад\n"
            f"Статус: {status}\n\n"
            f"Обновить: /setcookie <значение>"
        )
    elif has_db_cookie:
        await update.message.reply_text(
            "🍪 Cookie из БД, но без даты установки. Перезапиши через /setcookie чтобы трекать возраст."
        )
    elif has_env_cookie:
        await update.message.reply_text(
            "🍪 Cookie сейчас прокинут через переменную окружения LINKEDIN_LI_AT.\n"
            "Возраст не отслеживается. Чтобы перевести на управление через бота — отправь /setcookie <значение>."
        )
    else:
        await update.message.reply_text("🍪 Cookie не настроен. Отправь /setcookie <значение>.")


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


async def cmd_restore(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Merge a weekly backup back in: reply /restore to the backup message,
    or send the .db file with the caption /restore."""
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]

    if not _is_admin(update, config):
        await _deny(update)
        return

    message = update.message
    replied = message.reply_to_message
    document = message.document or (replied.document if replied else None)
    if document is None:
        await message.reply_text(
            "Чтобы восстановить историю, ответь командой /restore на сообщение с бэкапом "
            "(📦 Еженедельный бэкап БД) или пришли файл .db с подписью /restore.\n\n"
            "Данные из бэкапа добавятся к текущим: уже собранное не перезапишется."
        )
        return
    if document.file_size and document.file_size > RESTORE_MAX_BYTES:
        await message.reply_text("❌ Файл больше 20 МБ — Telegram не даст боту его скачать.")
        return

    await message.reply_text("⏳ Восстанавливаю...")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "backup.db")
        tg_file = await document.get_file()
        await tg_file.download_to_drive(path)
        try:
            result = await db.restore_from(path)
        except ValueError as e:
            await message.reply_text(f"❌ Не похоже на бэкап этого бота: {e}.")
            return

    # The backup may carry another report time: apply it to the running job.
    scheduler = context.bot_data.get("scheduler")
    if scheduler is not None:
        dow, hour, minute = await get_report_schedule(db, config)
        reschedule(scheduler, dow, hour, minute)

    period = f"{result['first']} — {result['last']}" if result["first"] else "пусто"
    await message.reply_text(
        f"✅ Восстановлено: +{result['added']:,} записей (всего {result['total']:,}, {period}).",
        reply_markup=_main_menu(),
    )


# ---------------------------------------------------------------------------
# Callback query handler
# ---------------------------------------------------------------------------

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    config: Config = context.bot_data["config"]
    db: Database = context.bot_data["db"]

    # Check before answering: _deny answers with an alert, and a query can be answered only once.
    if not _is_admin(update, config):
        await _deny(update)
        return
    await _answer(query)

    data = query.data

    if data == "menu":
        await _safe_edit(query, "Выберите действие:", reply_markup=_main_menu())

    elif data == "stats":
        report, _ = await build_stats(db, config)
        await _safe_edit(query, report, reply_markup=_main_menu())

    elif data == "now":
        await _safe_edit(query, "⏳ Собираю данные...")
        outcome = await collect_and_report(context.bot, config, db)
        await _safe_edit(query, outcome.report, reply_markup=_main_menu())
        await send_alerts(context.bot, config, db, outcome)

    elif data == "week":
        report = await build_week_report(db)
        await _safe_edit(query, report, reply_markup=_main_menu())

    elif data == "settings":
        dow, hour, minute = await get_report_schedule(db, config)
        quiet = await is_quiet_mode(db, config)
        await _safe_edit(
            query,
            _settings_text(dow, hour, minute, config),
            reply_markup=_settings_keyboard(quiet),
        )

    elif data == "quiet:toggle":
        current = await is_quiet_mode(db, config)
        new_value = not current
        await db.set_setting("quiet_if_no_change", "1" if new_value else "0")
        dow, hour, minute = await get_report_schedule(db, config)
        await _safe_edit(
            query,
            _settings_text(dow, hour, minute, config),
            reply_markup=_settings_keyboard(new_value),
        )

    elif data == "history":
        await _safe_edit(query, "Выберите платформу:", reply_markup=_history_platforms())

    elif data == "sec":
        await _safe_edit(query, await hygiene.render(db, config), reply_markup=_security_keyboard(config))

    elif data.startswith("sec:"):
        await _on_security_callback(query, db, data)

    elif data == "mod":
        text, keyboard = await _modules_screen(db, config)
        await _safe_edit(query, text, reply_markup=keyboard)

    elif data.startswith("mod:"):
        monitor_id = data.removeprefix("mod:")
        if monitor_id in monitors.BY_ID:
            await monitors.toggle(db, monitor_id)
        text, keyboard = await _modules_screen(db, config)
        await _safe_edit(query, text, reply_markup=keyboard)

    elif data.startswith("history:"):
        parts = data.split(":")
        if len(parts) == 2:
            platform = parts[1]
            label = "Все платформы" if platform == "all" else LABELS.get(platform, platform)
            await _safe_edit(
                query,
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
            await _safe_edit(
                query,
                table,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data=f"history:{platform}")]]),
            )


async def _on_security_callback(query, db: Database, data: str) -> None:
    """sec:edit:<platform> | sec:set:<platform>:<item>:<value> | sec:pwd:<platform>:<days ago>.

    Values are checked against the checklist: callback data comes from the client.
    """
    parts = data.split(":")[1:]
    if len(parts) < 2 or parts[1] not in BY_ID:
        return
    action, platform, rest = parts[0], BY_ID[parts[1]], parts[2:]
    if action == "set" and len(rest) == 2:
        item = next((i for i in hygiene.items(platform) if i.key == rest[0]), None)
        if item is None or rest[1] not in {c.value for c in item.choices}:
            return
        await hygiene.set_answer(db, platform.id, item.key, rest[1])
    elif action == "pwd" and len(rest) == 1:
        if not rest[0].isdigit() or int(rest[0]) not in hygiene.PASSWORD_AGES.values():
            return
        changed = utcnow().date() - timedelta(days=int(rest[0]))
        await hygiene.set_answer(db, platform.id, "pwd", changed.isoformat())
    elif action != "edit":
        return
    text, keyboard = await _checklist_screen(db, platform)
    await _safe_edit(query, text, reply_markup=keyboard)


# ---------------------------------------------------------------------------
# LinkedIn inline-input conversation
# ---------------------------------------------------------------------------

async def li_conv_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    config: Config = context.bot_data["config"]
    if not _is_admin(update, config):
        await _deny(update)
        return ConversationHandler.END

    query = update.callback_query
    await _answer(query)
    await _safe_edit(
        query,
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
        await _answer(update.callback_query)
        await _safe_edit(update.callback_query, "Отменено.", reply_markup=_main_menu())
    elif update.message:
        await update.message.reply_text("Отменено.", reply_markup=_main_menu())
    return ConversationHandler.END


async def li_conv_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Menu button pressed mid-conversation — abandon the input and show the menu."""
    await cmd_start(update, context)
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_handlers(app, config: Config, db: Database) -> None:
    app.bot_data["config"] = config
    app.bot_data["db"] = db

    # Before everything else: drop messages that waited through a long outage.
    app.add_handler(TypeHandler(Update, drop_stale_messages), group=-1)

    li_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(li_conv_start, pattern="^linkedin_prompt$")],
        states={
            LI_AWAITING_NUMBER: [
                # Menu button must win over the number parser, or a dangling
                # conversation swallows it with "Это не число".
                MessageHandler(filters.Regex(rf"^{re.escape(MENU_BUTTON_TEXT)}$"), li_conv_menu),
                MessageHandler(filters.TEXT & ~filters.COMMAND, li_conv_number),
                CallbackQueryHandler(li_conv_cancel, pattern="^li_cancel$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", li_conv_cancel)],
        conversation_timeout=LI_CONV_TIMEOUT,
    )
    # Conversation must be registered before the catch-all CallbackQueryHandler
    app.add_handler(li_conv)

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("now", cmd_now))
    app.add_handler(CommandHandler("week", cmd_week))
    app.add_handler(CommandHandler("security", cmd_security))
    app.add_handler(CommandHandler("modules", cmd_modules))
    app.add_handler(CommandHandler("linkedin", cmd_linkedin))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("settime", cmd_settime))
    app.add_handler(CommandHandler("setday", cmd_setday))
    app.add_handler(CommandHandler("setquiet", cmd_setquiet))
    app.add_handler(CommandHandler("setcookie", cmd_setcookie))
    app.add_handler(CommandHandler("cookieage", cmd_cookieage))
    app.add_handler(CommandHandler("restore", cmd_restore))
    # A file sent with the caption /restore: CommandHandler only reads message text.
    app.add_handler(MessageHandler(filters.Document.ALL & filters.CaptionRegex(r"^/restore\b"), cmd_restore))
    app.add_handler(MessageHandler(filters.Regex(rf"^{re.escape(MENU_BUTTON_TEXT)}$"), cmd_start))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_error_handler(on_error)

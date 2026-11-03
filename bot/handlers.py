from __future__ import annotations

import asyncio
import functools
import logging
import os
import re
import tempfile
from collections.abc import Awaitable, Callable
from datetime import timedelta
from zoneinfo import ZoneInfo

import aiohttp
from telegram import Update
from telegram.constants import ParseMode
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

from bot import monitors, ui
from bot.config import DOW_ORDER, Config, normalize_dow, normalize_tz
from bot.db import Database, utcnow
from bot.monitors import NO_PREVIEW, hygiene
from bot.platforms import BY_ID, PLATFORM_IDS
from bot.platforms.linkedin import collect_linkedin, plausible_count
from bot.reporter import _fmt
from bot.scheduler import (
    CHART_CAPTION,
    _build_chart_png,
    collect_and_report,
    get_report_schedule,
    get_report_tz,
    is_quiet_mode,
    reschedule,
    save_schedule,
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

# The persistent menu button, including the labels of older versions.
_MENU_BUTTON = filters.Regex(
    "^(?:" + "|".join(re.escape(t) for t in (ui.MENU_BUTTON_TEXT, *ui.LEGACY_MENU_BUTTON_TEXTS)) + ")$"
)


def _deps(context: ContextTypes.DEFAULT_TYPE) -> tuple[Config, Database]:
    return context.bot_data["config"], context.bot_data["db"]


# ---------------------------------------------------------------------------
# Showing screens
# ---------------------------------------------------------------------------

def _markup(screen: ui.Screen) -> dict:
    return {"reply_markup": screen.keyboard, "parse_mode": ParseMode.HTML, "link_preview_options": NO_PREVIEW}


async def _reply(update: Update, screen: ui.Screen):
    return await update.message.reply_text(screen.text, **_markup(screen))


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


async def _show(query, screen: ui.Screen) -> None:
    """Replace the menu message the button sits on: the chat doesn't fill up with menus."""
    await _safe_edit(query, screen.text, **_markup(screen))


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


def _admin_only(handler):
    @functools.wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not _is_admin(update, context.bot_data["config"]):
            await _deny(update)
            return None
        return await handler(update, context)

    return wrapper


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
                text=(
                    f"⚠️ Что-то пошло не так ({type(context.error).__name__}). "
                    "Попробуй ещё раз; подробности — в логах бота."
                ),
            )
        except Exception:
            logger.exception("Error notice send failed")


# ---------------------------------------------------------------------------
# Shared actions
# ---------------------------------------------------------------------------

def _collect_lock(context: ContextTypes.DEFAULT_TYPE) -> asyncio.Lock:
    return context.bot_data.setdefault("collect_lock", asyncio.Lock())


async def _collect_now(
    context: ContextTypes.DEFAULT_TYPE, show: Callable[[ui.Screen], Awaitable[None]]
) -> bool:
    """Collect, showing the progress and then the fresh home screen; False
    while another collection runs (a double tap must not collect twice)."""
    config, db = _deps(context)
    lock = _collect_lock(context)
    if lock.locked():
        return False
    async with lock:
        await show(ui.loading())
        try:
            outcome = await collect_and_report(context.bot, config, db)
        except Exception:
            logger.exception("Manual collection failed")
            await show((await ui.home(db, config)).noted(
                "⚠️ Собрать данные не получилось — подробности в логах. Ниже последние сохранённые."
            ))
            return True
        await show(await ui.home(db, config, report=outcome.report))
        await send_alerts(context.bot, config, db, outcome)
    return True


async def _apply_schedule(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Move the running daily job to the stored report time and zone."""
    config, db = _deps(context)
    scheduler = context.bot_data.get("scheduler")
    if scheduler is not None:
        await reschedule(scheduler, db, config)


async def _set_report_time(context: ContextTypes.DEFAULT_TYPE, hour: int, minute: int) -> None:
    config, db = _deps(context)
    await save_schedule(db, config, time=(hour, minute))
    await _apply_schedule(context)


async def _set_report_tz(context: ContextTypes.DEFAULT_TYPE, tz: ZoneInfo) -> str:
    """Switch the zone, keeping the report at the same moment: its time, and its
    days when that crosses midnight, are told in the new zone. Returns the note."""
    config, db = _deps(context)
    dow, hour, minute = await get_report_schedule(db, config)
    old = await get_report_tz(db, config)
    dow, hour, minute = ui.shift_schedule(dow, hour, minute, old, tz)
    await db.set_setting("report_dow", dow)
    await db.set_setting("report_time", f"{hour:02d}:{minute:02d}")
    await db.set_setting("report_tz", tz.key)
    await _apply_schedule(context)
    if tz.key == old.key:
        return f"✅ Часовой пояс: {ui.tz_name(tz)}"
    return f"✅ Часовой пояс: {ui.tz_name(tz)}. Отчёт придёт в тот же момент, что и раньше, — ниже его время по этому поясу"


def _parse_count(text: str) -> int | None:
    """A follower count as people type it: «4520», «4 520», «4,520», «4.520»."""
    digits = re.sub(r"[\s,.  ]", "", text.strip())
    return int(digits) if digits.isdigit() else None


async def _save_linkedin(db: Database, config: Config, count: int) -> ui.Screen:
    await db.upsert("linkedin", count, source="manual")
    return (await ui.home(db, config)).noted(f"✅ LinkedIn: {_fmt(count)} — сохранено")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, db = _deps(context)
    if not _is_admin(update, config):
        await update.message.reply_text("Это личный бот: он отвечает только своему владельцу.")
        return
    # Two messages: a message carries either the persistent keyboard or inline buttons.
    await update.message.reply_text(ui.WELCOME, reply_markup=ui.persistent_keyboard())
    await _reply(update, await ui.home(db, config))


@_admin_only
async def cmd_home(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """The menu button and /stats: just the home screen, no greeting."""
    config, db = _deps(context)
    await _reply(update, await ui.home(db, config))


@_admin_only
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply(update, ui.help_screen())


@_admin_only
async def cmd_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sent = None

    async def show(screen: ui.Screen) -> None:
        nonlocal sent
        if sent is None:
            sent = await _reply(update, screen)
        else:
            await sent.edit_text(screen.text, **_markup(screen))

    if not await _collect_now(context, show):
        await update.message.reply_text("⏳ Уже собираю данные — результат появится в сообщении выше.")


@_admin_only
async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, db = _deps(context)
    await _reply(update, await ui.dynamics(db))
    chart = await _build_chart_png(db)
    if chart:
        await update.message.reply_photo(chart, caption=CHART_CAPTION)


@_admin_only
async def cmd_security(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, db = _deps(context)
    await _reply(update, await ui.security(db, config))


@_admin_only
async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, db = _deps(context)
    await _reply(update, await ui.settings(db, config))


@_admin_only
async def cmd_modules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, db = _deps(context)
    await _reply(update, await ui.monitors_screen(db, config))


@_admin_only
async def cmd_linkedin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, db = _deps(context)
    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Пришли число вместе с командой, например: /linkedin 4520")
        return
    count = _parse_count(context.args[0])
    if count is None:
        await update.message.reply_text("Нужно целое число без знака, например: /linkedin 4520")
        return
    await _reply(update, await _save_linkedin(db, config, count))


@_admin_only
async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/history [platform] [days]: the day-by-day table, all platforms for 7 days by default."""
    config, db = _deps(context)
    args = context.args or []
    if len(args) > 2:
        await update.message.reply_text("Формат: /history [платформа] [дни], например: /history telegram 30")
        return
    platform = args[0].lower() if args else "all"
    if platform != "all" and platform not in PLATFORM_IDS:
        await update.message.reply_text(f"Неизвестная платформа. Доступны: all, {', '.join(PLATFORM_IDS)}")
        return
    days = 7
    if len(args) == 2:
        try:
            days = int(args[1])
        except ValueError:
            await update.message.reply_text("Количество дней должно быть числом, например: /history all 30")
            return
        if not 1 <= days <= HISTORY_MAX_DAYS:
            await update.message.reply_text(f"Количество дней — от 1 до {HISTORY_MAX_DAYS}.")
            return
    await _reply(update, await ui.table(db, config, platform, days))


@_admin_only
async def cmd_settime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, db = _deps(context)
    if not context.args:
        await _reply(update, await ui.report_time(db, config))
        return
    try:
        h_str, m_str = context.args[0].split(":")
        hour, minute = int(h_str), int(m_str)
        if len(context.args) != 1 or not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except (ValueError, AttributeError):
        await update.message.reply_text("Неверный формат. Нужно ЧЧ:ММ, например: /settime 08:00")
        return
    await _set_report_time(context, hour, minute)
    tz = await get_report_tz(db, config)
    await _reply(update, (await ui.settings(db, config)).noted(f"✅ Отчёт теперь в {ui.clock(hour, minute, tz)}"))


@_admin_only
async def cmd_setday(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, db = _deps(context)
    if not context.args:
        await _reply(update, await ui.report_days(db, config))
        return
    try:
        if len(context.args) != 1:
            raise ValueError
        normalized = normalize_dow(context.args[0])
    except ValueError:
        await update.message.reply_text(
            f"❌ Не понял дни: «{' '.join(context.args)}».\n"
            "Примеры: /setday sat, /setday mon,thu, /setday mon-fri, /setday daily"
        )
        return
    await save_schedule(db, config, dow=normalized)
    await _apply_schedule(context)
    await _reply(update, (await ui.settings(db, config)).noted(f"✅ Отчёт: {ui.dow_pretty(normalized)}"))


@_admin_only
async def cmd_settz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, db = _deps(context)
    if not context.args:
        await _reply(update, await ui.timezone(db, config))
        return
    try:
        if len(context.args) != 1:
            raise ValueError
        name = normalize_tz(context.args[0])
    except ValueError:
        await update.message.reply_text(
            f"❌ Не знаю такой часовой пояс: «{' '.join(context.args)}».\n"
            "Нужно название из базы IANA, например /settz Europe/Moscow или /settz Asia/Almaty. "
            "Частые пояса — кнопками: /settz без названия."
        )
        return
    note = await _set_report_tz(context, ZoneInfo(name))
    await _reply(update, (await ui.settings(db, config)).noted(note))


@_admin_only
async def cmd_setquiet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, db = _deps(context)
    choice = context.args[0].lower() if context.args else ""
    if choice not in ("on", "off"):
        await _reply(update, await ui.settings(db, config))
        return
    await db.set_setting("quiet_if_no_change", "1" if choice == "on" else "0")
    note = "✅ Тихий режим включён" if choice == "on" else "✅ Тихий режим выключен"
    await _reply(update, (await ui.settings(db, config)).noted(note))


@_admin_only
async def cmd_setcookie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, db = _deps(context)

    if not context.args:
        await update.message.reply_text(
            "Пришли cookie вместе с командой: /setcookie <значение li_at>\n\n"
            "Где взять: linkedin.com → DevTools → Application → Cookies → li_at → Value. "
            "Сообщение с cookie я сразу удалю."
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
    note = "" if deleted else "\n⚠️ Удалить сообщение с cookie не получилось — удали его из чата вручную."

    cookie = " ".join(context.args).strip()
    if len(cookie) < 50:
        await chat.send_message(f"❌ Это не похоже на cookie: значение слишком короткое.{note}")
        return

    if not config.linkedin_profile_url:
        await chat.send_message(f"❌ Не задан LINKEDIN_PROFILE_URL — не на чем проверить cookie.{note}")
        return

    await chat.send_message("⏳ Проверяю cookie…")

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
            f"Проверь, что значение скопировано целиком, без лишних символов.{note}"
        )
        return

    await db.set_setting("linkedin_li_at", cookie)
    await db.set_setting("linkedin_li_at_set_at", utcnow().isoformat())
    await db.set_setting("cookie_expired_alerted", "0")  # fresh cookie — re-arm the alert

    # Same guard as the daily collect: a value far from the stored one is
    # likely someone else's counter and must not become the new baseline.
    if plausible_count(prev, count):
        await db.upsert("linkedin", count, source="cookie")
        fetched = f"Проверка прошла: {_fmt(count)} подписчиков."
    else:
        fetched = (
            f"Проверка вернула {_fmt(count)} — слишком далеко от прошлого {_fmt(prev)}, число не записано. "
            f"Если оно верное, введи его: /linkedin {count}"
        )
    screen = (await ui.linkedin(db, config)).noted(f"✅ Cookie сохранён. {fetched}{note}")
    await chat.send_message(screen.text, **_markup(screen))


@_admin_only
async def cmd_cookieage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, db = _deps(context)
    await _reply(update, await ui.linkedin(db, config))


@_admin_only
async def cmd_restore(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Merge a weekly backup back in: reply /restore to the backup message,
    or send the .db file with the caption /restore."""
    config, db = _deps(context)

    message = update.message
    replied = message.reply_to_message
    document = message.document or (replied.document if replied else None)
    if document is None:
        await message.reply_text(
            "Чтобы вернуть историю, ответь командой /restore на сообщение с бэкапом "
            "(«📦 Еженедельный бэкап базы») или пришли файл .db с подписью /restore.\n\n"
            "Данные из бэкапа добавятся к текущим: уже собранное не перезапишется."
        )
        return
    if document.file_size and document.file_size > RESTORE_MAX_BYTES:
        await message.reply_text("❌ Файл больше 20 МБ — Telegram не даст боту его скачать.")
        return

    await message.reply_text("⏳ Восстанавливаю…")
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
    await _apply_schedule(context)

    period = f"{result['first']} — {result['last']}" if result["first"] else "пусто"
    note = (
        f"✅ Восстановлено, добавлено записей: {_fmt(result['added'])}. "
        f"Всего: {_fmt(result['total'])} ({period})."
    )
    await _reply(update, (await ui.home(db, config)).noted(note))


@_admin_only
async def on_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Такой команды нет. Все команды — в /help.")


@_admin_only
async def on_unknown_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # The persistent keyboard again: the user may have hidden or lost it.
    await update.message.reply_text(
        f"Не понимаю это сообщение. Главная — кнопка «{ui.MENU_BUTTON_TEXT}» внизу, все команды — /help.",
        reply_markup=ui.persistent_keyboard(),
    )


# ---------------------------------------------------------------------------
# Buttons
# ---------------------------------------------------------------------------

class _Press:
    """A button press, answered exactly once: with a short confirmation
    where a route gives one, otherwise silently when the route is done."""

    def __init__(self, query):
        self.query = query
        self.answered = False

    async def answer(self, text: str | None = None) -> None:
        if not self.answered:
            self.answered = True
            await _answer(self.query, text)


Route = Callable[[_Press, ContextTypes.DEFAULT_TYPE, list[str]], Awaitable[None]]


async def _cb_home(press: _Press, context, args: list[str]) -> None:
    config, db = _deps(context)
    await _show(press.query, await ui.home(db, config))


async def _cb_now(press: _Press, context, args: list[str]) -> None:
    if _collect_lock(context).locked():
        await press.answer("Уже собираю данные — подожди несколько секунд")
        return
    await press.answer()  # before the collection: it takes seconds

    async def show(screen: ui.Screen) -> None:
        await _show(press.query, screen)

    await _collect_now(context, show)


async def _cb_dynamics(press: _Press, context, args: list[str]) -> None:
    _, db = _deps(context)
    await _show(press.query, await ui.dynamics(db))


async def _cb_chart(press: _Press, context, args: list[str]) -> None:
    config, db = _deps(context)
    chart = await _build_chart_png(db)
    if chart is None:
        await press.answer("Для графика пока мало данных: нужно хотя бы два дня")
        return
    await press.answer("График — ниже")
    await context.bot.send_photo(chat_id=config.admin_chat_id, photo=chart, caption=CHART_CAPTION)


async def _cb_table(press: _Press, context, args: list[str]) -> None:
    """tbl[:<platform>[:<days>]]; anything off falls back to all platforms, 7 days."""
    config, db = _deps(context)
    platform = args[0] if args and args[0] in ("all", *PLATFORM_IDS) else "all"
    days = int(args[1]) if len(args) > 1 and args[1].isdigit() else 7
    if not 1 <= days <= HISTORY_MAX_DAYS:
        days = 7
    await _show(press.query, await ui.table(db, config, platform, days))


async def _cb_security(press: _Press, context, args: list[str]) -> None:
    """sec | sec:edit:<platform> | sec:ask:<platform>:<item>
    | sec:set:<platform>:<item>:<value> | sec:pwd:<platform>:<days ago>.

    Values are checked against the checklist: callback data comes from the client.
    """
    config, db = _deps(context)
    if not args:
        await _show(press.query, await ui.security(db, config))
        return
    if len(args) < 2 or args[1] not in BY_ID:
        return
    action, platform, rest = args[0], BY_ID[args[1]], args[2:]
    if action == "edit" and not rest:
        screen = await ui.checklist(db, platform)
    elif action == "ask" and len(rest) == 1 and rest[0] in ui.question_keys(platform):
        screen = await ui.question(db, platform, rest[0])
    elif action == "set" and len(rest) == 2:
        item = next((i for i in hygiene.items(platform) if i.key == rest[0]), None)
        if item is None or rest[1] not in {c.value for c in item.choices}:
            return
        await hygiene.set_answer(db, platform.id, item.key, rest[1])
        screen = await _after_answer(db, platform, item.key)
    elif action == "pwd" and len(rest) == 1:
        if not rest[0].isdigit() or int(rest[0]) not in hygiene.PASSWORD_AGES.values():
            return
        changed = utcnow().date() - timedelta(days=int(rest[0]))
        await hygiene.set_answer(db, platform.id, hygiene.PASSWORD_KEY, changed.isoformat())
        screen = await _after_answer(db, platform, hygiene.PASSWORD_KEY)
    else:
        return
    if action in ("set", "pwd"):
        await press.answer("Сохранено")
    await _show(press.query, screen)


async def _after_answer(db: Database, platform, key: str) -> ui.Screen:
    """The next unanswered question, so a first pass is a run of taps; the list once all are marked."""
    following = await ui.next_unanswered(db, platform, key)
    if following is not None:
        return await ui.question(db, platform, following)
    return await ui.checklist(db, platform)


async def _cb_settings(press: _Press, context, args: list[str]) -> None:
    """set | set:quiet | set:days[:<preset>] | set:day:<day> | set:time | set:hour:<h> | set:tz[:<zone>]."""
    config, db = _deps(context)
    action = args[0] if args else ""
    value = args[1] if len(args) == 2 else None
    if not args:
        screen = await ui.settings(db, config)
    elif action == "quiet" and len(args) == 1:
        quiet = not await is_quiet_mode(db, config)
        await db.set_setting("quiet_if_no_change", "1" if quiet else "0")
        await press.answer("Тихий режим включён" if quiet else "Тихий режим выключен")
        screen = await ui.settings(db, config)
    elif action == "days" and len(args) == 1:
        screen = await ui.report_days(db, config)
    elif action == "days" and value is not None:
        try:
            await save_schedule(db, config, dow=normalize_dow(value))
        except ValueError:
            return
        screen = await ui.report_days(db, config)
    elif action == "day" and value in DOW_ORDER:
        dow, _, _ = await get_report_schedule(db, config)
        days = set(ui.dow_days(dow)) ^ {value}
        if not days:
            await press.answer("Нужен хотя бы один день")
            return
        await save_schedule(db, config, dow=ui.dow_expr(days))
        screen = await ui.report_days(db, config)
    elif action == "time" and len(args) == 1:
        screen = await ui.report_time(db, config)
    elif action == "hour" and value is not None and value.isdigit() and int(value) <= 23:
        await _set_report_time(context, int(value), 0)
        tz = await get_report_tz(db, config)
        await press.answer(f"Отчёт будет приходить в {ui.clock(int(value), 0, tz)}")
        screen = await ui.settings(db, config)
    elif action == "tz" and len(args) == 1:
        screen = await ui.timezone(db, config)
    elif action == "tz" and value is not None:
        try:
            tz = ZoneInfo(normalize_tz(value))
        except ValueError:
            return
        note = await _set_report_tz(context, tz)
        screen = (await ui.settings(db, config)).noted(note)
    else:
        return
    await _show(press.query, screen)


async def _cb_monitors(press: _Press, context, args: list[str]) -> None:
    config, db = _deps(context)
    if args:
        if len(args) != 1 or args[0] not in monitors.BY_ID:
            return
        on = await monitors.toggle(db, args[0])
        await press.answer(f"{monitors.BY_ID[args[0]].label}: {'включено' if on else 'выключено'}")
    await _show(press.query, await ui.monitors_screen(db, config))


async def _cb_linkedin(press: _Press, context, args: list[str]) -> None:
    """li | li:save:<count> (confirmed after the typo check) | li:cancel of a timed-out prompt."""
    config, db = _deps(context)
    if not args:
        screen = await ui.linkedin(db, config)
    elif len(args) == 2 and args[0] == "save" and args[1].isdigit():
        screen = await _save_linkedin(db, config, int(args[1]))
        await press.answer("Сохранено")
    elif args == ["cancel"]:
        screen = await ui.home(db, config)
    else:
        return
    await _show(press.query, screen)


async def _cb_help(press: _Press, context, args: list[str]) -> None:
    await _show(press.query, ui.help_screen())


_ROUTES: dict[str, Route] = {
    ui.HOME: _cb_home,
    ui.NOW: _cb_now,
    ui.DYNAMICS: _cb_dynamics,
    ui.CHART: _cb_chart,
    ui.TABLE: _cb_table,
    ui.SECURITY: _cb_security,
    ui.SETTINGS: _cb_settings,
    ui.MONITORS: _cb_monitors,
    ui.LINKEDIN: _cb_linkedin,
    ui.HELP: _cb_help,
}
# Screen ids of the menu before the redesign: their buttons stay in the chat history.
_LEGACY = {"menu": ui.HOME, "stats": ui.HOME, "week": ui.DYNAMICS, "settings": ui.SETTINGS, "history": ui.TABLE}


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    config, db = _deps(context)

    # Check before answering: _deny answers with an alert, and a query can be answered only once.
    if not _is_admin(update, config):
        await _deny(update)
        return

    press = _Press(query)
    head, *args = (query.data or "").split(":")
    route = _ROUTES.get(_LEGACY.get(head, head))
    try:
        if route is None:
            await press.answer("Это меню устарело — вот актуальное")
            await _show(query, await ui.home(db, config))
        else:
            await route(press, context, args)
    finally:
        await press.answer()


# ---------------------------------------------------------------------------
# LinkedIn inline-input conversation
# ---------------------------------------------------------------------------

async def li_conv_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    config, db = _deps(context)
    if not _is_admin(update, config):
        await _deny(update)
        return ConversationHandler.END

    query = update.callback_query
    await _answer(query)
    await _show(query, await ui.linkedin_prompt(db))
    return LI_AWAITING_NUMBER


async def li_conv_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    config, db = _deps(context)
    if not _is_admin(update, config):
        await _deny(update)
        return ConversationHandler.END

    count = _parse_count(update.message.text or "")
    if count is None:
        await _reply(update, ui.linkedin_retry())
        return LI_AWAITING_NUMBER

    prev_row = await db.get_latest("linkedin")
    if prev_row is not None and not plausible_count(prev_row["count"], count):
        await _reply(update, ui.linkedin_confirm(prev_row["count"], count))
        return ConversationHandler.END

    await _reply(update, await _save_linkedin(db, config, count))
    return ConversationHandler.END


async def li_conv_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    config, db = _deps(context)
    screen = await ui.home(db, config)
    if update.callback_query:
        await _answer(update.callback_query, "Отменено")
        await _show(update.callback_query, screen)
    elif update.message:
        await _reply(update, screen.noted("Отменено."))
    return ConversationHandler.END


async def li_conv_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Menu button pressed mid-conversation — abandon the input and show the menu."""
    await cmd_home(update, context)
    return ConversationHandler.END


async def li_conv_other_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Another button pressed mid-conversation: it wins, the input is abandoned."""
    await on_callback(update, context)
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

COMMANDS = {
    "start": cmd_start,
    "stats": cmd_home,
    "help": cmd_help,
    "now": cmd_now,
    "week": cmd_week,
    "security": cmd_security,
    "settings": cmd_settings,
    "modules": cmd_modules,
    "linkedin": cmd_linkedin,
    "history": cmd_history,
    "settime": cmd_settime,
    "setday": cmd_setday,
    "settz": cmd_settz,
    "setquiet": cmd_setquiet,
    "setcookie": cmd_setcookie,
    "cookieage": cmd_cookieage,
    "restore": cmd_restore,
}


def register_handlers(app, config: Config, db: Database) -> None:
    app.bot_data["config"] = config
    app.bot_data["db"] = db

    # Before everything else: drop messages that waited through a long outage.
    app.add_handler(TypeHandler(Update, drop_stale_messages), group=-1)

    li_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(li_conv_start, pattern=r"^(?:li:enter|linkedin_prompt)$")],
        states={
            LI_AWAITING_NUMBER: [
                # Menu button must win over the number parser, or a dangling
                # conversation swallows it with "not a number".
                MessageHandler(_MENU_BUTTON, li_conv_menu),
                MessageHandler(filters.TEXT & ~filters.COMMAND, li_conv_number),
                CallbackQueryHandler(li_conv_cancel, pattern=r"^(?:li:cancel|li_cancel)$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", li_conv_cancel), CallbackQueryHandler(li_conv_other_button)],
        conversation_timeout=LI_CONV_TIMEOUT,
        allow_reentry=True,
    )
    # Conversation must be registered before the catch-all CallbackQueryHandler
    app.add_handler(li_conv)

    for name, handler in COMMANDS.items():
        app.add_handler(CommandHandler(name, handler))
    # A file sent with the caption /restore: CommandHandler only reads message text.
    app.add_handler(MessageHandler(filters.Document.ALL & filters.CaptionRegex(r"^/restore\b"), cmd_restore))
    app.add_handler(MessageHandler(_MENU_BUTTON, cmd_home))
    app.add_handler(CallbackQueryHandler(on_callback))
    # Last: whatever nothing above understood gets a hint instead of silence.
    app.add_handler(MessageHandler(filters.COMMAND, on_unknown_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_unknown_text))
    app.add_error_handler(on_error)

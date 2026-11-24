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
from telegram.constants import ChatType, ParseMode
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

from bot import callbacks as cb
from bot import monitors, notifier, ui
from bot.config import DOW_ORDER, Config, normalize_dow, normalize_tz
from bot.db import Database, utcnow
from bot.i18n import t
from bot.monitors import NO_PREVIEW, channel, comments, hygiene
from bot.platforms import BY_ID, PLATFORM_IDS
from bot.platforms import instagram as ig
from bot.platforms.linkedin import collect_linkedin, plausible_count
from bot.reporter import _fmt
from bot.scheduler import (
    CHART_CAPTION,
    _build_chart_png,
    _send_backup,
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
AWAITING_INPUT = 2       # a cookie, a token or a time zone, by button (ui.input_prompt)

# End a dangling input conversation after this many seconds of silence.
LI_CONV_TIMEOUT = 120
# What each entry button asks for.
INPUT_KINDS = {cb.LI_COOKIE: "cookie", cb.IG_TOKEN: "token", cb.TZ_OTHER: "tz"}

# Longest /history period: keeps the table under Telegram's 4096-char message limit.
HISTORY_MAX_DAYS = 90

# Bot API getFile refuses files above 20 MB.
RESTORE_MAX_BYTES = 20 * 1024 * 1024

# Messages queued while the bot restarts (a deploy) are handled after start;
# older ones (a long outage) are dropped rather than replayed.
PENDING_MAX_AGE = timedelta(minutes=10)
# Commands whose argument is a secret: a stale one is deleted from the chat, not just dropped.
SECRET_COMMANDS = ("setcookie", "igtoken")

# What the bot asks Telegram for. Joins and leaves (chat_member) and the
# reactions on posts (message_reaction_count) are not sent unless asked
# for; the list replaces Telegram's default, so everything else the bot
# handles is named too.
ALLOWED_UPDATES = (
    Update.MESSAGE,
    Update.CALLBACK_QUERY,
    Update.MY_CHAT_MEMBER,
    Update.CHANNEL_POST,
    Update.CHAT_MEMBER,
    Update.MESSAGE_REACTION_COUNT,
)



class _ReplyButton(filters.MessageFilter):
    """A button of the persistent reply keyboard, by its text: the current
    label, its English translation and the labels of older versions — a user
    who switched BOT_LANG, or has not had a message since the update, still
    has the old keyboard on screen. The set is built per message, after the
    language is set."""

    def __init__(self, name: str, key: str, legacy: tuple[str, ...] = ()):
        super().__init__(name=name)
        self._key, self._legacy = key, legacy

    def texts(self) -> set[str]:
        return {self._key, t(self._key), *self._legacy}

    @property
    def pattern(self) -> re.Pattern[str]:
        """The same labels as a regex, for callers that match by pattern."""
        return re.compile("^(?:" + "|".join(re.escape(text) for text in sorted(self.texts())) + ")$")

    def filter(self, message) -> bool:
        return bool(message.text) and message.text in self.texts()


_HOME_BUTTON = _ReplyButton("home_button", ui.HOME_BUTTON_TEXT, (*ui.LEGACY_HOME_BUTTON_TEXTS, "🏠 Menu"))
_ABOUT_BUTTON = _ReplyButton("about_button", ui.ABOUT_BUTTON_TEXT)
_ICONS_BUTTON = _ReplyButton("icons_button", ui.ICONS_BUTTON_TEXT)
# The bottom buttons of 1.4.0, still on screen until a message brings the new keyboard.
_REFRESH_BUTTON = _ReplyButton("refresh_button", ui.LEGACY_REFRESH_BUTTON_TEXT)
_MUTE_BUTTON = _ReplyButton("mute_button", ui.LEGACY_MUTE_BUTTON_TEXT)
_REPLY_BUTTONS = _HOME_BUTTON | _ABOUT_BUTTON | _ICONS_BUTTON | _REFRESH_BUTTON | _MUTE_BUTTON
# The answer to anything the bot does not understand, and to a stale button.
NOT_UNDERSTOOD = "Не понял. Всё — кнопками под полем ввода: 🏠 Главная, 📖 Что я умею, ❓ Значки."
STALE_BUTTON = "Кнопка устарела — вот главная. Она всегда под полем ввода: «🏠 Главная»"


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

OWNER_SETTING = "admin_chat_id"


def _is_admin(update: Update, config: Config) -> bool:
    user = update.effective_user
    return user is not None and config.admin_chat_id is not None and user.id == config.admin_chat_id


# The reply keyboard the owner has on screen: bumped when its buttons change,
# so the new one is brought by one note after the update (Telegram replaces a
# keyboard only with a message).
KEYBOARD_SETTING = "reply_keyboard"
KEYBOARD_VERSION = "2"   # 1.5.0: 🏠 Главная · 📖 Что я умею · ❓ Значки


async def show_keyboard_once(bot, config: Config, db: Database) -> bool:
    """At startup: bring the current keyboard to an owner who still has an
    older one, once. Nothing before the first /start — it brings the keyboard."""
    if config.admin_chat_id is None or await db.get_setting(KEYBOARD_SETTING) == KEYBOARD_VERSION:
        return False
    await notifier.send_keyboard(
        bot, config, db,
        t("Главные кнопки теперь под полем ввода: 🏠 Главная, 📖 Что я умею и ❓ Значки. Меню ☰ убрал — "
          "команды работают как раньше, а «🔄 Обновить данные» и «🔕 Помолчать…» — на главной."),
        ui.persistent_keyboard(),
    )
    await db.set_setting(KEYBOARD_SETTING, KEYBOARD_VERSION)
    return True


async def restore_owner(config: Config, db: Database) -> None:
    """At startup: the owner from the DB unless ADMIN_CHAT_ID pins one. With
    neither, the bot waits for its first /start and sends nothing until then."""
    if config.admin_chat_id is not None:
        return
    stored = await db.get_setting(OWNER_SETTING)
    if stored:
        config.set_owner(int(stored))
        logger.info("Owner restored from the database")
    else:
        logger.warning("No owner yet: the first /start claims the bot")


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
        await _answer(update.callback_query, t("⛔ Доступ запрещён."), show_alert=True)
    elif update.message:
        await update.message.reply_text(t("⛔ Доступ запрещён."))


def _admin_only(handler):
    @functools.wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not _is_admin(update, context.bot_data["config"]):
            await _deny(update)
            return None
        return await handler(update, context)

    return wrapper


def _command_name(message) -> str:
    """'/setcookie@bot AQ…' → 'setcookie'; '' for anything that is not a command."""
    text = message.text or message.caption or ""
    if not text.startswith("/"):
        return ""
    return text.split(maxsplit=1)[0][1:].split("@", 1)[0].lower()


async def drop_stale_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Runs before every handler. A message queued during a deploy restart is
    handled; one older than PENDING_MAX_AGE is dropped, so a /now from hours
    ago doesn't fire. Button presses carry no send time and always pass.

    A dropped /setcookie or /igtoken still carries its secret: the owner's
    message is deleted and they are asked to send it again, rather than left
    in the chat without an answer."""
    message = update.message
    if message is None or message.date is None or utcnow() - message.date <= PENDING_MAX_AGE:
        return
    logger.info("Dropping a message queued for %s", utcnow() - message.date)
    if (
        _command_name(message) in SECRET_COMMANDS
        and len((message.text or "").split()) > 1
        and _is_admin(update, context.bot_data["config"])
    ):
        try:
            await message.delete()
        except Exception:
            logger.warning("A stale message with a secret could not be deleted", exc_info=True)
        await update.effective_chat.send_message(
            t("⏳ Эта команда пришла, пока я был выключен: сообщение с секретом я удалил, "
              "чтобы оно не лежало в чате. Пришли его заново.")
        )
    raise ApplicationHandlerStop


def _watch(context: ContextTypes.DEFAULT_TYPE) -> comments.Watch:
    return context.bot_data.setdefault("comments_watch", comments.Watch())


async def on_group_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Runs first, before every other handler. Nothing from a group or a
    channel reaches the owner-only handlers (they would answer «⛔ Доступ
    запрещён» to every comment). A new message in the channel's discussion
    group is reviewed in the background, so a slow classifier never holds up
    the owner's chat; a join, a leave, a post or a reaction in the channel is
    recorded (bot/monitors/channel.py)."""
    chat = update.effective_chat
    if chat is None or chat.type == ChatType.PRIVATE:
        return
    config, db = _deps(context)
    message = update.message
    if message is not None and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        context.application.create_task(
            comments.review(context.bot, config, db, _watch(context), message), update=update
        )
    elif chat.type == ChatType.CHANNEL:
        await channel.record(db, config, update)
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
                text=t(
                    "⚠️ Что-то пошло не так ({error}). Попробуй ещё раз; подробности — в логах бота."
                ).format(error=type(context.error).__name__),
                # The menu the error interrupted may be far up the chat.
                reply_markup=cb.actions_markup((cb.HOME,)),
            )
        except Exception:
            logger.exception("Error notice send failed")


# ---------------------------------------------------------------------------
# Shared actions
# ---------------------------------------------------------------------------

def collect_lock(bot_data: dict) -> asyncio.Lock:
    """The one lock around a collection: /now, the 🔄 button and the scheduler's
    daily run (bot/scheduler.py) share it, so two collections never overlap."""
    return bot_data.setdefault("collect_lock", asyncio.Lock())


def _collect_lock(context: ContextTypes.DEFAULT_TYPE) -> asyncio.Lock:
    return collect_lock(context.bot_data)


async def _collect_now(
    context: ContextTypes.DEFAULT_TYPE, show: Callable[[ui.Screen], Awaitable[None]]
) -> bool:
    """Collect, showing the progress and then the fresh home screen; False
    while another collection runs — a double tap, or the scheduler's daily
    run — so nothing is collected twice."""
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
                t("⚠️ Собрать данные не получилось — подробности в логах. Ниже последние сохранённые.")
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
        return t("✅ Часовой пояс: {tz}").format(tz=ui.tz_name(tz))
    return t(
        "✅ Часовой пояс: {tz}. Отчёт придёт в тот же момент, что и раньше, — ниже его время по этому поясу"
    ).format(tz=ui.tz_name(tz))


def _parse_count(text: str) -> int | None:
    """A follower count as people type it: «4520», «4 520», «4,520», «4.520»."""
    digits = re.sub(r"[\s,.  ]", "", text.strip())
    return int(digits) if digits.isdigit() else None


async def _save_linkedin(db: Database, config: Config, count: int) -> ui.Screen:
    await db.upsert("linkedin", count, source="manual")
    return (await ui.home(db, config)).noted(t("✅ LinkedIn: {count} — сохранено").format(count=_fmt(count)))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, db = _deps(context)
    claimed = False
    if config.admin_chat_id is None and update.effective_user is not None:
        # The first person to say /start owns the bot (BOT_PRINCIPLES §5);
        # ADMIN_CHAT_ID in the environment pins or changes the owner.
        config.set_owner(update.effective_user.id)
        await db.set_setting(OWNER_SETTING, str(update.effective_user.id))
        logger.info("Owner claimed by the first /start")
        claimed = True
    if not _is_admin(update, config):
        await update.message.reply_text(t("Это личный бот: он отвечает только своему владельцу."))
        return
    # Two messages: a message carries either the persistent keyboard or inline buttons.
    await update.message.reply_text(ui.welcome(claimed), reply_markup=ui.persistent_keyboard())
    await db.set_setting(KEYBOARD_SETTING, KEYBOARD_VERSION)
    await _reply(update, await ui.home(db, config))


@_admin_only
async def cmd_home(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """The menu button and /stats: just the home screen, no greeting."""
    config, db = _deps(context)
    await _reply(update, await ui.home(db, config))


@_admin_only
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/help and «📖 Что я умею»: what the bot does and every command."""
    await _reply(update, ui.about_screen())


@_admin_only
async def cmd_icons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """«❓ Значки»: the icon dictionary and what rings."""
    await _reply(update, ui.icons_screen())


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
        await update.message.reply_text(
            t("⏳ Уже собираю данные — по расписанию или по другой команде. Подожди минуту и повтори.")
        )


@_admin_only
async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, db = _deps(context)
    await _reply(update, await ui.dynamics(db))
    chart = await _build_chart_png(db)
    if chart:
        await update.message.reply_photo(chart, caption=t(CHART_CAPTION))


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
async def cmd_comments(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, db = _deps(context)
    await _reply(update, await ui.comments_screen(db, config))


@_admin_only
async def cmd_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, db = _deps(context)
    await _reply(update, await ui.channel_screen(db, config))


@_admin_only
async def cmd_connections(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, db = _deps(context)
    await _reply(update, await ui.connections(db, config))


@_admin_only
async def cmd_linkedin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, db = _deps(context)
    if not context.args or len(context.args) != 1:
        await update.message.reply_text(t("Пришли число вместе с командой, например: /linkedin 4520"))
        return
    count = _parse_count(context.args[0])
    if count is None:
        await update.message.reply_text(t("Нужно целое число без знака, например: /linkedin 4520"))
        return
    await _reply(update, await _save_linkedin(db, config, count))


@_admin_only
async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/history [platform] [days]: the day-by-day table, all platforms for 7 days by default."""
    config, db = _deps(context)
    args = context.args or []
    if len(args) > 2:
        await update.message.reply_text(t("Формат: /history [платформа] [дни], например: /history telegram 30"))
        return
    platform = args[0].lower() if args else "all"
    if platform != "all" and platform not in PLATFORM_IDS:
        await update.message.reply_text(
            t("Неизвестная платформа. Доступны: all, {platforms}").format(platforms=", ".join(PLATFORM_IDS))
        )
        return
    days = 7
    if len(args) == 2:
        try:
            days = int(args[1])
        except ValueError:
            await update.message.reply_text(t("Количество дней должно быть числом, например: /history all 30"))
            return
        if not 1 <= days <= HISTORY_MAX_DAYS:
            await update.message.reply_text(t("Количество дней — от 1 до {max}.").format(max=HISTORY_MAX_DAYS))
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
        await update.message.reply_text(t("Неверный формат. Нужно ЧЧ:ММ, например: /settime 08:00"))
        return
    await _set_report_time(context, hour, minute)
    tz = await get_report_tz(db, config)
    await _reply(update, (await ui.settings(db, config)).noted(t("✅ Отчёт теперь в {time}").format(time=ui.clock(hour, minute, tz))))


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
            t(
                "❌ Не понял дни: «{days}».\n"
                "Примеры: /setday sat, /setday mon,thu, /setday mon-fri, /setday daily"
            ).format(days=" ".join(context.args))
        )
        return
    await save_schedule(db, config, dow=normalized)
    await _apply_schedule(context)
    await _reply(update, (await ui.settings(db, config)).noted(t("✅ Отчёт: {days}").format(days=ui.dow_pretty(normalized))))


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
            t(
                "❌ Не знаю такой часовой пояс: «{tz}».\n"
                "Нужно название из базы IANA, например /settz Europe/Moscow или /settz Asia/Almaty. "
                "Частые пояса — кнопками: /settz без названия."
            ).format(tz=" ".join(context.args))
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
    note = t("✅ Коротко без изменений: включено") if choice == "on" else t("✅ Коротко без изменений: выключено")
    await _reply(update, (await ui.settings(db, config)).noted(note))


async def _mute(db: Database, config: Config, arg: str) -> str | None:
    """Mute for `arg` ('8h', '30m', '1d'); the note to show, None when the argument is not a duration."""
    duration = notifier.parse_duration(arg)
    if duration is None:
        return None
    if duration > notifier.MUTE_MAX:
        return t("Максимум — 7 дней: дольше тишина уже не пауза, а выключенный мониторинг.")
    await notifier.set_mute(db, duration)
    return ui.mute_note(await notifier.mute_until_local(db, config))


async def _unmute(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lift the mute and deliver what it held back right away, not in a minute."""
    config, db = _deps(context)
    await notifier.set_mute(db, None)
    await notifier.flush_queue(context.bot, config, db)


@_admin_only
async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, db = _deps(context)
    note = await _mute(db, config, context.args[0] if context.args else "8h")
    if note is None:
        await update.message.reply_text(
            t("Использование: /mute <время>\nПримеры: /mute 1h, /mute 8h, /mute 30m, /mute 1d\nПо умолчанию: 8h")
        )
        return
    await _reply(update, (await ui.when_to_write(db, config)).noted(note))


@_admin_only
async def cmd_mute_quick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """The «🔕 Тихо 8 ч» reply button of 1.4.0: eight hours of silence, then the home screen."""
    config, db = _deps(context)
    note = await _mute(db, config, "8h")
    await _reply(update, (await ui.home(db, config)).noted(note))


async def _reply_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """One of the three buttons at the bottom of the chat, or a button of the
    1.4.0 keyboard still on screen (🔄 Обновить, 🔕 Тихо 8 ч)."""
    text = update.message.text or ""
    if text in _ABOUT_BUTTON.texts():
        await cmd_help(update, context)
    elif text in _ICONS_BUTTON.texts():
        await cmd_icons(update, context)
    elif text in _REFRESH_BUTTON.texts():
        await cmd_now(update, context)
    elif text in _MUTE_BUTTON.texts():
        await cmd_mute_quick(update, context)
    else:
        await cmd_home(update, context)


@_admin_only
async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, db = _deps(context)
    await _unmute(context)
    await _reply(update, (await ui.when_to_write(db, config)).noted(t("🔔 Снова пишу обо всём.")))


def _ask_by_message(context: ContextTypes.DEFAULT_TYPE, kind: str) -> int:
    """A command without its value starts the same step as its button: the
    value comes as the next message, with «✖️ Отмена» (BOT_PRINCIPLES §2)."""
    context.user_data["awaiting"] = kind
    return AWAITING_INPUT


@_admin_only
async def cmd_setcookie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """/setcookie <li_at> stores the cookie; /setcookie alone asks for it as the next message."""
    if not context.args:
        await _reply(update, ui.input_prompt("cookie"))
        return _ask_by_message(context, "cookie")
    await _store_cookie(update, context, " ".join(context.args).strip())
    return ConversationHandler.END


async def _store_cookie(update: Update, context: ContextTypes.DEFAULT_TYPE, cookie: str) -> None:
    """The value of /setcookie, or the message after «🔑 Прислать cookie»."""
    config, db = _deps(context)
    # Don't leave the secret sitting in chat history — delete it before any
    # check can bail out early. Replies go to the chat: the message is gone.
    chat = update.effective_chat
    deleted = True
    try:
        await update.message.delete()
    except Exception:
        deleted = False
    note = "" if deleted else "\n" + t("🟠 Удалить сообщение с cookie не получилось — удали его из чата вручную.")

    if len(cookie) < 50:
        await chat.send_message(t("❌ Это не похоже на cookie: значение слишком короткое.") + note)
        return

    if not config.linkedin_profile_url:
        await chat.send_message(t("❌ Не задан LINKEDIN_PROFILE_URL — не на чем проверить cookie.") + note)
        return

    await chat.send_message(t("⏳ Проверяю cookie…"))

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
            t("LinkedIn отклонил cookie")
            if source == "cookie_expired"
            else t("не удалось получить число подписчиков (подробности в логах)")
        )
        await chat.send_message(
            t(
                "❌ Cookie не сохранён: {reason}.\n"
                "Проверь, что значение скопировано целиком, без лишних символов."
            ).format(reason=reason) + note
        )
        return

    await db.set_setting("linkedin_li_at", cookie)
    await db.set_setting("linkedin_li_at_set_at", utcnow().isoformat())
    await db.set_setting("cookie_expired_alerted", "0")  # fresh cookie — re-arm the alert

    # Same guards as the daily collect: the page carries other profiles'
    # counters too, so the first number is confirmed by the owner, and a value
    # far from the stored one must not become the new baseline.
    if prev is None:
        fetched = t(
            "Проверка вернула {count}. Это первое значение — сверь его со страницей профиля и подтверди: /linkedin {raw}"
        ).format(count=_fmt(count), raw=count)
    elif plausible_count(prev, count):
        await db.upsert("linkedin", count, source="cookie")
        fetched = t("Проверка прошла: {count} подписчиков.").format(count=_fmt(count))
    else:
        fetched = t(
            "Проверка вернула {count} — слишком далеко от прошлого {prev}, число не записано. "
            "Если оно верное, введи его: /linkedin {raw}"
        ).format(count=_fmt(count), prev=_fmt(prev), raw=count)
    screen = (await ui.linkedin(db, config)).noted(t("✅ Cookie сохранён. {fetched}").format(fetched=fetched) + note)
    await chat.send_message(screen.text, **_markup(screen))


@_admin_only
async def cmd_igtoken(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """/igtoken <token> stores the token; /igtoken alone asks for it as the next message."""
    if not context.args:
        await _reply(update, ui.input_prompt("token"))
        return _ask_by_message(context, "token")
    await _store_token(update, context, "".join(context.args).strip())
    return ConversationHandler.END


async def _store_token(update: Update, context: ContextTypes.DEFAULT_TYPE, token: str) -> None:
    """The value of /igtoken, or the message after «🔑 Прислать токен»."""
    config, db = _deps(context)
    # The token is a secret: out of the chat history before any check can bail out.
    chat = update.effective_chat
    deleted = True
    try:
        await update.message.delete()
    except Exception:
        deleted = False
    note = "" if deleted else "\n" + t("🟠 Удалить сообщение с токеном не получилось — удали его из чата вручную.")

    if len(token) < 50:
        await chat.send_message(t("❌ Это не похоже на токен: значение слишком короткое.") + note)
        return

    if not config.instagram_username:
        await chat.send_message(t("❌ Не задан INSTAGRAM_USERNAME — Instagram не подключён.") + note)
        return

    await chat.send_message(t("⏳ Проверяю токен…"))

    async with aiohttp.ClientSession() as session:
        try:
            user_id = await ig.resolve_account(session, token, config.instagram_username)
            user = await ig.fetch_user(session, token, user_id) if user_id else None
        except ig.InstagramAuthError:
            user_id = user = None
            reason = t("Instagram отклонил токен")
        except Exception:
            logger.exception("Instagram token check failed")
            user_id = user = None
            reason = t("не удалось связаться с Instagram (подробности в логах)")
        else:
            reason = (
                t(
                    "токен выдан не для @{username} — проверь INSTAGRAM_USERNAME "
                    "и какой аккаунт добавлен в приложение Meta"
                ).format(username=config.instagram_username)
                if user_id is None
                else t("Instagram не ответил (подробности в логах)")
            )

    if user_id is None or user is None:
        await chat.send_message(
            t(
                "❌ Токен не сохранён: {reason}.\n"
                "Проверь, что значение скопировано целиком, без лишних символов."
            ).format(reason=reason) + note
        )
        return

    username = str(user.get("username") or config.instagram_username)
    await ig.store_token(db, token, user_id, config.instagram_username)
    await db.set_setting("instagram_token_alerted", "0")  # a fresh token re-arms the alert
    try:
        count = int(user["followers_count"])
    except (KeyError, TypeError, ValueError):
        count = None
    if count is not None:
        await db.upsert("instagram", count, source="api")
        fetched = t("Проверка прошла: @{username}, {count} подписчиков.").format(username=username, count=_fmt(count))
    else:
        fetched = t("Проверка прошла: @{username}, но число подписчиков API не вернул.").format(username=username)
    screen = (await ui.instagram(db, config)).noted(t("✅ Токен сохранён. {fetched}").format(fetched=fetched) + note)
    await chat.send_message(screen.text, **_markup(screen))


@_admin_only
async def cmd_cookieage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config, db = _deps(context)
    await _reply(update, await ui.linkedin(db, config))


async def _restore_document(context: ContextTypes.DEFAULT_TYPE, document) -> str:
    """Merge a backup file into the live DB; returns the note to show."""
    config, db = _deps(context)
    if document.file_size and document.file_size > RESTORE_MAX_BYTES:
        return t("❌ Файл больше 20 МБ — Telegram не даст боту его скачать.")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "backup.db")
        tg_file = await document.get_file()
        await tg_file.download_to_drive(path)
        try:
            result = await db.restore_from(path)
        except ValueError as e:
            return t("❌ Не похоже на бэкап этого бота: {error}.").format(error=e)
    # The backup may carry another report time: apply it to the running job.
    await _apply_schedule(context)
    period = f"{result['first']} — {result['last']}" if result["first"] else t("пусто")
    return t(
        "✅ Восстановлено, добавлено записей: {added}. Всего: {total} ({period})."
    ).format(added=_fmt(result["added"]), total=_fmt(result["total"]), period=period)


@_admin_only
async def cmd_restore(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Merge a weekly backup back in: reply /restore to the backup message,
    send the .db file with the caption /restore — or just send the file and
    confirm with the button (on_document)."""
    config, db = _deps(context)

    message = update.message
    replied = message.reply_to_message
    document = message.document or (replied.document if replied else None)
    if document is None:
        await message.reply_text(
            t(
                "Чтобы вернуть историю, пришли файл бэкапа («📦 Еженедельный бэкап базы») и подтверди кнопкой, "
                "или ответь на него командой /restore.\n\n"
                "Данные из бэкапа добавятся к текущим: уже собранное не перезапишется."
            )
        )
        return
    if document.file_size and document.file_size > RESTORE_MAX_BYTES:
        await message.reply_text(t("❌ Файл больше 20 МБ — Telegram не даст боту его скачать."))
        return
    await message.reply_text(t("⏳ Восстанавливаю…"))
    note = await _restore_document(context, document)
    if note.startswith("❌"):
        await message.reply_text(note)
        return
    await _reply(update, (await ui.home(db, config)).noted(note))


def _looks_like_backup(document) -> bool:
    name = (getattr(document, "file_name", None) or "").lower()
    mime = (getattr(document, "mime_type", None) or "").lower()
    return name.endswith((".db", ".sqlite", ".sqlite3")) or mime in ("application/x-sqlite3", "application/vnd.sqlite3")


@_admin_only
async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """A file without a caption: a database file is offered for a restore
    with one button (the file used to be ignored in silence); anything else
    gets a hint."""
    if _looks_like_backup(update.message.document):
        await update.message.reply_text(
            t("Это бэкап базы? Могу вернуть из него историю — уже собранное не перезапишется."),
            reply_markup=ui.restore_prompt(), do_quote=True,
        )
        return
    await update.message.reply_text(
        t("Не знаю, что делать с этим файлом. Бэкап базы (.db) я восстановлю — пришли его и подтверди кнопкой.")
    )


@_admin_only
async def on_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        t("Такой команды нет. Все команды — в «📖 Что я умею» под полем ввода."), reply_markup=ui.persistent_keyboard()
    )


@_admin_only
async def on_unknown_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # The persistent keyboard again: the user may have hidden or lost it.
    await update.message.reply_text(t(NOT_UNDERSTOOD), reply_markup=ui.persistent_keyboard())


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
        await press.answer(t("Уже собираю данные — подожди несколько секунд"))
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
        await press.answer(t("Для графика пока мало данных: нужно хотя бы два дня"))
        return
    await press.answer(t("График — ниже"))
    await context.bot.send_photo(chat_id=config.admin_chat_id, photo=chart, caption=t(CHART_CAPTION))


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
        await press.answer(t("Сохранено"))
    await _show(press.query, screen)


async def _after_answer(db: Database, platform, key: str) -> ui.Screen:
    """The next unanswered question, so a first pass is a run of taps; the list once all are marked."""
    following = await ui.next_unanswered(db, platform, key)
    if following is not None:
        return await ui.question(db, platform, following)
    return await ui.checklist(db, platform)


async def _cb_settings(press: _Press, context, args: list[str]) -> None:
    """set | set:quiet | set:days[:<preset>] | set:day:<day> | set:time | set:hour:<h> | set:tz[:<zone>]
    | set:when | set:qh:<preset|off> | set:mute:<duration|off>."""
    config, db = _deps(context)
    action = args[0] if args else ""
    value = args[1] if len(args) == 2 else None
    if not args:
        screen = await ui.settings(db, config)
    elif action == "quiet" and len(args) == 1:
        quiet = not await is_quiet_mode(db, config)
        await db.set_setting("quiet_if_no_change", "1" if quiet else "0")
        await press.answer(t("Коротко без изменений: включено") if quiet else t("Коротко без изменений: выключено"))
        screen = await ui.settings(db, config)
    elif action == "when" and len(args) == 1:
        screen = await ui.when_to_write(db, config)
    elif action == "qh" and (value == "off" or value in notifier.QUIET_PRESETS):
        # Only what the screen offers: a forged «qh:25-3» must not reach the settings.
        await notifier.set_quiet_hours(db, None if value == "off" else value)
        await press.answer(t("Сохранено"))
        screen = await ui.when_to_write(db, config)
        if value == "off":
            await notifier.flush_queue(context.bot, config, db)
    elif action == "mute" and value == "off":
        await _unmute(context)
        screen = (await ui.when_to_write(db, config)).noted(t("🔔 Снова пишу обо всём."))
    elif action == "mute" and value in ui.MUTE_CHOICES:
        note = await _mute(db, config, value)
        screen = (await ui.when_to_write(db, config)).noted(note)
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
            await press.answer(t("Нужен хотя бы один день"))
            return
        await save_schedule(db, config, dow=ui.dow_expr(days))
        screen = await ui.report_days(db, config)
    elif action == "time" and len(args) == 1:
        screen = await ui.report_time(db, config)
    elif action == "hour" and value is not None and value.isdigit() and int(value) <= 23:
        _, _, minute = await get_report_schedule(db, config)
        await _set_report_time(context, int(value), minute)
        tz = await get_report_tz(db, config)
        await press.answer(t("Отчёт будет приходить в {time}").format(time=ui.clock(int(value), minute, tz)))
        screen = await ui.report_time(db, config)
    elif action == "minute" and value is not None and value.isdigit() and int(value) in ui.MINUTE_CHOICES:
        _, hour, _ = await get_report_schedule(db, config)
        await _set_report_time(context, hour, int(value))
        tz = await get_report_tz(db, config)
        await press.answer(t("Отчёт будет приходить в {time}").format(time=ui.clock(hour, int(value), tz)))
        screen = await ui.report_time(db, config)
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
    """mod — the screen; mod:<id> — toggle and back to the screen;
    mod:<id>:off — «⚙️ Не присылать такие» under an alert: a toast, the alert
    stays; mod:<id>:<cm|ch> — the toggle on that monitor's own screen."""
    config, db = _deps(context)
    if not args:
        await _show(press.query, await ui.monitors_screen(db, config))
        return
    if args[0] not in monitors.BY_ID or len(args) > 2:
        return
    label = t(monitors.BY_ID[args[0]].label)
    if len(args) == 2 and args[1] == "off":
        await monitors.set_switch(db, args[0], False)
        await press.answer(
            t("{label}: выключено. Включить снова — ⚙️ Настройки → 🧩 Мониторинги").format(label=label)
        )
        return
    if len(args) == 2 and args[1] not in (cb.COMMENTS, cb.CHANNEL):
        return
    on = await monitors.toggle(db, args[0])
    await press.answer(f"{label}: {t('включено') if on else t('выключено')}")
    if len(args) == 2:
        screen = await (ui.comments_screen if args[1] == cb.COMMENTS else ui.channel_screen)(db, config)
    else:
        screen = await ui.monitors_screen(db, config)
    await _show(press.query, screen)


async def _cb_comments(press: _Press, context, args: list[str]) -> None:
    """cm — the screen; cm:<del|ban|ok|unban>:<review id> — a card button.
    The card is re-rendered in place from the record, so a second tap or an
    old card shows the current state."""
    config, db = _deps(context)
    if not args:
        await _show(press.query, await ui.comments_screen(db, config))
        return
    if len(args) != 2 or not args[1].isdigit():
        return
    review, note = await comments.act(context.bot, db, int(args[1]), args[0])
    if review is None:
        await press.answer(note)
        return
    await press.answer(note)
    text, markup = comments.card(review, _watch(context).group_title)
    await _safe_edit(press.query, text, reply_markup=markup, link_preview_options=NO_PREVIEW)


async def _cb_channel(press: _Press, context, args: list[str]) -> None:
    config, db = _deps(context)
    await _show(press.query, await ui.channel_screen(db, config))


async def _cb_connections(press: _Press, context, args: list[str]) -> None:
    config, db = _deps(context)
    await _show(press.query, await ui.connections(db, config))


async def _cb_linkedin(press: _Press, context, args: list[str]) -> None:
    """li | li:save:<count> (confirmed after the typo check) | li:cancel of a timed-out prompt."""
    config, db = _deps(context)
    if not args:
        screen = await ui.linkedin(db, config)
    elif len(args) == 2 and args[0] == "save" and args[1].isdigit():
        screen = await _save_linkedin(db, config, int(args[1]))
        await press.answer(t("Сохранено"))
    elif args == ["cancel"]:
        screen = await ui.home(db, config)
    else:
        return
    await _show(press.query, screen)


async def _cb_instagram(press: _Press, context, args: list[str]) -> None:
    config, db = _deps(context)
    await _show(press.query, await ui.instagram(db, config))


async def _cb_about(press: _Press, context, args: list[str]) -> None:
    """«📖 Что я умею»; also the «❓ Помощь» button of older menus."""
    await _show(press.query, ui.about_screen())


async def _cb_icons(press: _Press, context, args: list[str]) -> None:
    await _show(press.query, ui.icons_screen())


async def _screen(context, screen_id: str) -> ui.Screen | None:
    """A screen an alert's button may open, by its id."""
    config, db = _deps(context)
    builders = {
        cb.HOME: lambda: ui.home(db, config),
        cb.DYNAMICS: lambda: ui.dynamics(db),
        cb.SECURITY: lambda: ui.security(db, config),
        cb.CHANNEL: lambda: ui.channel_screen(db, config),
        cb.COMMENTS: lambda: ui.comments_screen(db, config),
        cb.CONNECTIONS: lambda: ui.connections(db, config),
    }
    builder = builders.get(screen_id)
    return await builder() if builder else None


async def _cb_open(press: _Press, context, args: list[str]) -> None:
    """open:<screen> — the screen as a new message, so the alert it was
    pressed on stays in the chat as it is."""
    config, db = _deps(context)
    screen = await _screen(context, args[0]) if args else None
    if screen is None:
        await press.answer(t(STALE_BUTTON))
        screen = await ui.home(db, config)
    await context.bot.send_message(chat_id=config.admin_chat_id, text=screen.text, **_markup(screen))


async def _cb_mute(press: _Press, context, args: list[str]) -> None:
    """mute — the «🔕 Помолчать…» picker; mute:<1h|4h|8h|1d> | mute:off —
    under an alert: a toast, the alert stays; with :home — pressed on the
    home screen or the picker, and the home screen is shown."""
    config, db = _deps(context)
    if not args:
        await _show(press.query, ui.mute_picker())
        return
    if args[0] not in ("off", *ui.MUTE_CHOICES) or len(args) > 2:
        return
    if args[0] == "off":
        await _unmute(context)
        note = t("🔔 Снова пишу обо всём.")
    else:
        await notifier.set_mute(db, notifier.parse_duration(args[0]))
        note = t("🔕 Молчу до {until}.").format(until=await notifier.mute_until_local(db, config))
    if len(args) == 2 and args[1] == cb.HOME:
        await _show(press.query, (await ui.home(db, config)).noted(note))
    else:
        await press.answer(note)


async def _cb_restore(press: _Press, context, args: list[str]) -> None:
    """restore:yes | restore:no under a .db file: the file is the message the
    prompt replied to."""
    config, db = _deps(context)
    if args == ["no"]:
        await _show(press.query, (await ui.home(db, config)).noted(t("Отменено.")))
        return
    if args != ["yes"]:
        return
    original = getattr(getattr(press.query, "message", None), "reply_to_message", None)
    document = getattr(original, "document", None)
    if document is None:
        await press.answer(t("Файл не нашёл — пришли его заново или ответь на него командой /restore"))
        return
    await press.answer(t("⏳ Восстанавливаю…"))
    note = await _restore_document(context, document)
    await _show(press.query, (await ui.home(db, config)).noted(note))


async def _cb_backup(press: _Press, context, args: list[str]) -> None:
    """The database file now — before a migration or an experiment, not on Sunday."""
    config, db = _deps(context)
    await press.answer(t("📦 Отправляю бэкап…"))
    await _send_backup(context.bot, config, db)


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
    ui.INSTAGRAM: _cb_instagram,
    cb.ABOUT: _cb_about,
    cb.ICONS: _cb_icons,
    cb.HELP: _cb_about,
    ui.COMMENTS: _cb_comments,
    ui.CHANNEL: _cb_channel,
    cb.CONNECTIONS: _cb_connections,
    cb.OPEN: _cb_open,
    cb.MUTE: _cb_mute,
    cb.BACKUP: _cb_backup,
    cb.RESTORE: _cb_restore,
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
            await press.answer(t(STALE_BUTTON))
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
        await _answer(update.callback_query, t("Отменено"))
        await _show(update.callback_query, screen)
    elif update.message:
        await _reply(update, screen.noted(t("Отменено.")))
    return ConversationHandler.END


async def li_conv_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """A reply-keyboard button pressed mid-conversation — abandon the input and do what it says."""
    await _reply_button(update, context)
    return ConversationHandler.END


async def li_conv_other_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Another button pressed mid-conversation: it wins, the input is abandoned."""
    await on_callback(update, context)
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Text-input conversations: a cookie, a token, a time zone — by button
# ---------------------------------------------------------------------------

async def input_conv_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """«🔑 Прислать cookie», «🔑 Прислать токен», «✏️ Другой пояс…»: ask for
    the value as the next message, the way the LinkedIn number is asked for."""
    config, db = _deps(context)
    if not _is_admin(update, config):
        await _deny(update)
        return ConversationHandler.END
    query = update.callback_query
    kind = INPUT_KINDS.get(query.data or "")
    await _answer(query)
    if kind is None:
        return ConversationHandler.END
    context.user_data["awaiting"] = kind
    await _show(query, ui.input_prompt(kind))
    return AWAITING_INPUT


async def input_conv_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    config, db = _deps(context)
    if not _is_admin(update, config):
        await _deny(update)
        return ConversationHandler.END
    kind = context.user_data.pop("awaiting", None)
    value = (update.message.text or "").strip()
    if kind == "cookie":
        await _store_cookie(update, context, value)
    elif kind == "token":
        await _store_token(update, context, value)
    elif kind == "tz":
        try:
            name = normalize_tz(value)
        except ValueError:
            context.user_data["awaiting"] = "tz"
            await _reply(update, ui.input_retry_tz())
            return AWAITING_INPUT
        note = await _set_report_tz(context, ZoneInfo(name))
        await _reply(update, (await ui.settings(db, config)).noted(note))
    return ConversationHandler.END


async def input_conv_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("awaiting", None)
    return await li_conv_cancel(update, context)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

COMMANDS = {
    "start": cmd_start,
    "stats": cmd_home,
    "help": cmd_help,
    "icons": cmd_icons,
    "now": cmd_now,
    "week": cmd_week,
    "security": cmd_security,
    "settings": cmd_settings,
    "modules": cmd_modules,
    "comments": cmd_comments,
    "channel": cmd_channel,
    "connections": cmd_connections,
    "linkedin": cmd_linkedin,
    "history": cmd_history,
    "settime": cmd_settime,
    "setday": cmd_setday,
    "settz": cmd_settz,
    "setquiet": cmd_setquiet,
    "mute": cmd_mute,
    "unmute": cmd_unmute,
    "cookieage": cmd_cookieage,
    "restore": cmd_restore,
}


def register_handlers(app, config: Config, db: Database) -> None:
    app.bot_data["config"] = config
    app.bot_data["db"] = db

    # Before everything else, each in a group of its own (PTB runs one handler
    # per group): group and channel traffic goes to its monitors and stops
    # there; then messages that waited through a long outage are dropped.
    app.add_handler(TypeHandler(Update, on_group_update), group=-2)
    app.add_handler(TypeHandler(Update, drop_stale_messages), group=-1)

    li_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(li_conv_start, pattern=r"^(?:li:enter|linkedin_prompt)$")],
        states={
            LI_AWAITING_NUMBER: [
                # The reply buttons must win over the number parser, or a
                # dangling conversation swallows them with "not a number".
                MessageHandler(_REPLY_BUTTONS, li_conv_menu),
                MessageHandler(filters.TEXT & ~filters.COMMAND, li_conv_number),
                CallbackQueryHandler(li_conv_cancel, pattern=r"^(?:li:cancel|li_cancel)$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", li_conv_cancel), CallbackQueryHandler(li_conv_other_button)],
        conversation_timeout=LI_CONV_TIMEOUT,
        allow_reentry=True,
    )
    input_conv = ConversationHandler(
        # A button, or /setcookie and /igtoken typed without their value (with
        # it they store the secret at once and end there).
        entry_points=[
            CallbackQueryHandler(input_conv_start, pattern="^(?:" + "|".join(map(re.escape, INPUT_KINDS)) + ")$"),
            CommandHandler("setcookie", cmd_setcookie),
            CommandHandler("igtoken", cmd_igtoken),
        ],
        states={
            AWAITING_INPUT: [
                MessageHandler(_REPLY_BUTTONS, li_conv_menu),
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_conv_value),
                CallbackQueryHandler(input_conv_cancel, pattern=f"^{re.escape(cb.INPUT_CANCEL)}$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", input_conv_cancel), CallbackQueryHandler(li_conv_other_button)],
        conversation_timeout=LI_CONV_TIMEOUT,
        allow_reentry=True,
    )
    # Conversations must be registered before the catch-all CallbackQueryHandler
    app.add_handler(li_conv)
    app.add_handler(input_conv)

    for name, handler in COMMANDS.items():
        app.add_handler(CommandHandler(name, handler))
    # A file sent with the caption /restore: CommandHandler only reads message text.
    app.add_handler(MessageHandler(filters.Document.ALL & filters.CaptionRegex(r"^/restore\b"), cmd_restore))
    # Any other file: a backup is offered for a restore, the rest gets a hint.
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(_REPLY_BUTTONS, _reply_button))
    app.add_handler(CallbackQueryHandler(on_callback))
    # Last: whatever nothing above understood gets a hint instead of silence.
    app.add_handler(MessageHandler(filters.COMMAND, on_unknown_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_unknown_text))
    app.add_error_handler(on_error)

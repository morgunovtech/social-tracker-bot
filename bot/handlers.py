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
from telegram.constants import ChatMemberStatus, ChatType, MessageOriginType, ParseMode
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
from bot import classifier, connections, mailbox, monitors, notifier, platforms, reputation, ui, watchdog
from bot.config import DEFAULT_TZ, DOW_ORDER, Config, normalize_dow, normalize_tz
from bot.db import HELD_KEEP_DAYS, Database, utcnow
from bot.i18n import LANGUAGES, set_language, t
from bot.monitors import NO_PREVIEW, channel, comments, hygiene
from bot.platforms import BY_ID, PLATFORM_IDS
from bot.platforms import instagram as ig
from bot.platforms.linkedin import collect_linkedin, plausible_count
from bot.platforms.telegram import channel_info, collect_telegram
from bot.platforms.youtube import collect_youtube
from bot.reporter import _fmt
from bot.scheduler import (
    CHART_CAPTION,
    _build_chart_png,
    _send_backup,
    collect_and_report,
    get_report_schedule,
    get_report_tz,
    is_quiet_mode,
    offer_watchdog_once,
    reschedule,
    save_schedule,
    send_alerts,
    zone_chosen,
)

logger = logging.getLogger(__name__)

# ConversationHandler states
LI_AWAITING_NUMBER = 1
AWAITING_INPUT = 2       # a cookie, a token or a time zone, by button (ui.input_prompt)

# End a dangling input conversation after this many seconds of silence.
LI_CONV_TIMEOUT = 120
# What each entry button asks for.
INPUT_KINDS = {cb.LI_COOKIE: "cookie", cb.IG_TOKEN: "token", cb.TZ_OTHER: "tz", cb.WD_URL: "watchdog",
               cb.REP_WORDS: "rep_words", **{entry: monitor for monitor, entry in cb.REP_KEYS.items()},
               **{entry: f"conn_{platform}" for platform, entry in cb.CONN_ADD.items()},
               cb.CLAUDE_KEY: "conn_anthropic", cb.MAIL_BOX: "mail_box", cb.MAIL_WORKER: "mail_worker"}
# A service-account key file is small; anything bigger is not one.
KEY_FILE_MAX_BYTES = 20_000

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
    Update.EDITED_MESSAGE,     # a comment edited into spam is reviewed again

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


# The chat language once it was chosen at runtime — in ⚙️ Настройки, or by the
# owner's Telegram at the first /start. It wins over BOT_LANG (chat beats .env).
LANG_SETTING = "bot_lang"


async def restore_language(config: Config, db: Database) -> None:
    """At startup: the language kept in the database, when there is one."""
    stored = await db.get_setting(LANG_SETTING)
    if stored in LANGUAGES and stored != config.lang:
        config.set_lang(stored)
        set_language(stored)


async def _switch_language(config: Config, db: Database, lang: str) -> None:
    await db.set_setting(LANG_SETTING, lang)
    config.set_lang(lang)
    set_language(lang)


# Telegram languages whose speakers read Russian far more often than English
# (until the bot speaks them): the bot stays Russian, and a schedule nobody set
# moves to the country's zone instead of Moscow's.
RUSSIAN_READERS = {
    "uz": "Asia/Tashkent",
    "kk": "Asia/Almaty",
    "ky": "Asia/Bishkek",
    "tg": "Asia/Dushanbe",
    "be": "Europe/Minsk",
}


async def adopt_owner_language(code: str | None, config: Config, db: Database) -> tuple[bool, bool]:
    """The bot was just claimed and nobody chose a language — BOT_LANG is empty
    and the chat never set one: the owner's Telegram decides. Russian stays
    Russian; Uzbek, Kazakh, Kyrgyz, Tajik and Belarusian stay Russian too and
    a schedule nobody set moves to that country's zone (RUSSIAN_READERS); any
    other language becomes English, and a schedule nobody set moves to the
    English default zone (UTC). Returns (the language switched, the zone was set)."""
    if (os.getenv("BOT_LANG") or "").strip() or await db.get_setting(LANG_SETTING):
        return False, False
    base = (code or "ru").lower().split("-")[0]
    if base == "ru":
        return False, False
    if base in RUSSIAN_READERS:
        if await zone_chosen(db):
            return False, False
        await db.set_setting("report_tz", RUSSIAN_READERS[base])
        return False, True
    await _switch_language(config, db, "en")
    if await zone_chosen(db):
        return True, False
    await db.set_setting("report_tz", DEFAULT_TZ["en"])
    return True, True


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
    edited = getattr(update, "edited_message", None)
    if chat is None or chat.type == ChatType.PRIVATE:
        if edited is not None:
            # The owner fixed a typo in an old message: not a new command.
            # python-telegram-bot's command and text handlers take edits too.
            raise ApplicationHandlerStop
        return
    config, db = _deps(context)
    message = update.message or edited
    if message is not None and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        context.application.create_task(
            comments.review(context.bot, config, db, _watch(context), message, edited=edited is not None),
            update=update,
        )
    elif chat.type == ChatType.CHANNEL:
        if (promoted := getattr(update, "my_chat_member", None)) is not None:
            await _offer_channel(context, promoted)
        await channel.record(db, config, update)
    raise ApplicationHandlerStop


_ADMIN_STATUSES = (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)


async def _offer_channel(context: ContextTypes.DEFAULT_TYPE, change) -> None:
    """The owner has just made the bot an admin of a channel, and no channel
    is connected: one message with a button that connects it (ui.channel_offer).
    A change of rights, someone else's doing or a second channel says nothing."""
    config, db = _deps(context)
    promoted = (change.new_chat_member.status in _ADMIN_STATUSES
                and change.old_chat_member.status not in _ADMIN_STATUSES)
    by_owner = change.from_user is not None and change.from_user.id == config.admin_chat_id
    if promoted and by_owner and not config.telegram_channel_id:
        screen = ui.channel_offer(change.chat.title or str(change.chat.id), change.chat.id)
        await notifier.send(context.bot, config, db, screen.text, reply_markup=screen.keyboard)


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
    claimed = adopted = False
    if config.admin_chat_id is None and update.effective_user is not None:
        # The first person to say /start owns the bot (BOT_PRINCIPLES §5);
        # ADMIN_CHAT_ID in the environment pins or changes the owner.
        config.set_owner(update.effective_user.id)
        await db.set_setting(OWNER_SETTING, str(update.effective_user.id))
        logger.info("Owner claimed by the first /start")
        claimed = True
        adopted, zone_set = await adopt_owner_language(
            getattr(update.effective_user, "language_code", None), config, db
        )
        if adopted or zone_set:
            await _apply_schedule(context)
    if not _is_admin(update, config):
        await update.message.reply_text(t("Это личный бот: он отвечает только своему владельцу."))
        return
    # Two messages: a message carries either the persistent keyboard or inline buttons.
    # A bot without a network says where to start and opens 🔌 Подключения
    # instead of an empty report — also when ADMIN_CHAT_ID made the claim needless.
    fresh = not platforms.enabled(config)
    await update.message.reply_text(ui.welcome(claimed, fresh), reply_markup=ui.persistent_keyboard())
    await db.set_setting(KEYBOARD_SETTING, KEYBOARD_VERSION)
    if adopted:
        await _reply(update, ui.language_note())
    if fresh:
        await _reply(update, (await ui.connections(db, config)).noted(t(ui.FIRST_NETWORK)))
    else:
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
    name = ui.zone_from_text(" ".join(context.args))
    if name is None:
        await update.message.reply_text(
            t(
                "❌ Не знаю такой пояс: «{tz}».\n"
                "Пришли город по-английски или название пояса, например /settz Berlin или /settz Asia/Almaty. "
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
        await chat.send_message(t("❌ Сначала подключи Instagram: 🔌 Подключения → «➕ Instagram».") + note)
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
                    "токен выдан не для @{username} — проверь @username в «🔌 Подключения» "
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


async def _store_watchdog(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    """The message after «🔗 Прислать ссылку»: a live test ping, and the
    address is kept only when the watchdog took it. False keeps the step
    open — the next paste is answered, not left in the chat."""
    config, db = _deps(context)
    # The address is a secret: out of the chat history before any check.
    chat = update.effective_chat
    deleted = True
    try:
        await update.message.delete()
    except Exception:
        deleted = False
    note = "" if deleted else "\n" + t("🟠 Удалить сообщение со ссылкой не получилось — удали его из чата вручную.")
    address = watchdog.parse(text)
    if address is None:
        screen = ui.input_retry(
            t("❌ Нужна ссылка https://…, например https://hc-ping.com/… из healthchecks.io. "
              "Пришли её ещё раз или нажми «✖️ Отмена».") + note
        )
        await chat.send_message(screen.text, **_markup(screen))
        return False
    await chat.send_message(t("⏳ Отмечаюсь у сторожа…"))
    error = await watchdog.probe(address)
    if error is not None:
        screen = ui.input_retry(
            t("❌ Сторож не на связи: {reason}. Проверь, что ссылка скопирована целиком и check не удалён, "
              "и пришли её ещё раз — или нажми «✖️ Отмена».").format(reason=watchdog.reason(error)) + note
        )
        await chat.send_message(screen.text, **_markup(screen))
        return False
    await watchdog.save(db, address)
    screen = (await ui.watchdog_screen(db, config)).noted(
        t("✅ Сторож подключён и на связи ({who}). Дальше отмечаюсь после каждого ежедневного сбора.").format(
            who=watchdog.name(address)
        ) + note
    )
    await chat.send_message(screen.text, **_markup(screen))
    return True


async def _store_rep_key(update: Update, context: ContextTypes.DEFAULT_TYPE, monitor_id: str, value: str) -> bool:
    """A reputation source's read-only key (🔎 Репутация → 🔑): out of the
    chat first, then a live test call, kept only when the source answered.
    False keeps the step open."""
    config, db = _deps(context)
    chat = update.effective_chat
    deleted = True
    try:
        await update.message.delete()
    except Exception:
        deleted = False
    note = "" if deleted else "\n" + t("🟠 Удалить сообщение с ключом не получилось — удали его из чата вручную.")
    source = reputation.BY_MONITOR[monitor_id]
    await chat.send_message(t("⏳ Проверяю ключ…"))
    async with aiohttp.ClientSession() as session:
        error, seen = await source.module.check(session, value.strip())
    if error is not None:
        screen = ui.input_retry(
            t("❌ {source} не принял ключ: {reason}. Пришли его ещё раз или нажми «✖️ Отмена».").format(
                source=t(source.label), reason=reputation.reason(error, seen)) + note
        )
        await chat.send_message(screen.text, **_markup(screen))
        return False
    await db.set_setting(monitors.BY_ID[monitor_id].secret, value.strip())
    screen = (await ui.reputation_screen(db, config)).noted(
        t("✅ {source} подключён: {seen}").format(source=t(source.label), seen=seen) + note
    )
    await chat.send_message(screen.text, **_markup(screen))
    return True


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
            await connections.restore(config, db)   # networks the backup connected from the chat
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
    document = update.message.document
    name = (getattr(document, "file_name", None) or "").lower()
    if name.endswith(".json") and (document.file_size or 0) <= KEY_FILE_MAX_BYTES:
        # The Search Console key comes as a file from Google Cloud: taken as
        # if it was pasted into «🔑 Google».
        file = await document.get_file()
        raw = bytes(await file.download_as_bytearray()).decode("utf-8", errors="replace")
        if reputation.google.parse_key(raw) is not None:
            await _store_rep_key(update, context, "rep_google", raw)
            return
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
    elif action == "lang" and len(args) == 1:
        # Two languages: the button is a switch. The three buttons under the
        # input field keep their old words until a message brings new ones.
        await _switch_language(config, db, "en" if config.lang == "ru" else "ru")
        await press.answer(t("Сохранено"))
        await context.bot.send_message(
            chat_id=config.admin_chat_id, text=t("Язык: {lang}. Кнопки под полем ввода обновил.").format(lang=t(ui.LANG_NAMES[config.lang])),
            reply_markup=ui.persistent_keyboard())
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
    if args[0] == "lim":                  # cm:lim:<n> — the daily limit; 0 — none
        if len(args) == 2 and args[1].isdigit() and int(args[1]) in comments.LIMIT_CHOICES:
            limit = int(args[1])
            await db.set_setting(comments.LIMIT_KEY, str(limit))
            await press.answer(t("Лимит: {n} в сутки").format(n=limit) if limit else t("Лимит снят"))
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
    """conn — the screen; conn:pick:<id> — «✅ Подключить канал» under the
    offer of a channel the owner has just made the bot an admin of."""
    config, db = _deps(context)
    note = None
    if len(args) == 2 and args[0] == "pick" and connections.telegram_channel(args[1]):
        note = await _connect_channel(context, args[1])
        if note is None:
            await press.answer(t("❌ Не вижу этот канал — я всё ещё его администратор?"))
            return
    screen = await ui.connections(db, config)
    await _show(press.query, screen.noted(note) if note else screen)
    if note:
        await _offer_watchdog_now(context)


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


async def _cb_reputation(press: _Press, context, args: list[str]) -> None:
    """rep — the screen; rep:now — this week's report at once (a check that
    the keys work, or a report on demand)."""
    config, db = _deps(context)
    if args == ["now"]:
        await press.answer(t("⏳ Собираю отчёт…"))
        if not await reputation.send(context.bot, config, db):
            await context.bot.send_message(
                chat_id=config.admin_chat_id,
                text=t("🔎 За неделю сказать нечего: подключённые источники ничего не нашли."),
            )
        return
    await _show(press.query, await ui.reputation_screen(db, config))


async def _cb_watchdog(press: _Press, context, args: list[str]) -> None:
    """wd — the screen; wd:test — a live ping now; wd:off — asked first; wd:off:yes — off."""
    config, db = _deps(context)
    if args == ["test"]:
        address = await watchdog.url(db, config)
        if not address:
            return
        error = await watchdog.probe(address)
        await watchdog.record(db, error)
        await press.answer(t("✅ Сторож на связи") if error is None else watchdog.reason(error))
        screen = await ui.watchdog_screen(db, config)
    elif args == ["off"]:
        screen = ui.watchdog_off_confirm(fallback=bool(config.healthcheck_url))
    elif args == ["off", "yes"]:
        await watchdog.forget(db)
        await press.answer(t("Сторож отключён"))
        screen = await ui.watchdog_screen(db, config)
    elif not args:
        screen = await ui.watchdog_screen(db, config)
    else:
        return
    await _show(press.query, screen)


async def _cb_mail(press: _Press, context, args: list[str]) -> None:
    """mail — the screen; mail:off:<box|wk> — asked first; mail:off:<box|wk>:yes — off."""
    config, db = _deps(context)
    if not args:
        screen = await ui.mail_screen(db, config)
    elif len(args) == 2 and args[0] == "off" and args[1] in ("box", "wk"):
        screen = ui.mail_off_confirm(args[1])
    elif args == ["off", "box", "yes"]:
        await mailbox.disconnect(config, db)
        await press.answer(t("Ящик отключён"))
        screen = await ui.mail_screen(db, config)
    elif args == ["off", "wk", "yes"]:
        await connections.remove(config, db, "security_mail_url", "security_mail_token")
        await press.answer(t("Воркер отключён"))
        screen = await ui.mail_screen(db, config)
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
        cb.WATCHDOG: lambda: ui.watchdog_screen(db, config),
        cb.REPUTATION: lambda: ui.reputation_screen(db, config),
        cb.MAIL: lambda: ui.mail_screen(db, config),
        cb.SETTINGS: lambda: ui.settings(db, config),
        cb.MONITORS: lambda: ui.monitors_screen(db, config),
        cb.OPEN_TIME: lambda: ui.report_time(db, config),
        cb.OPEN_TZ: lambda: ui.timezone(db, config),
        cb.OPEN_WHEN: lambda: ui.when_to_write(db, config),
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


async def _cb_digest(press: _Press, context, args: list[str]) -> None:
    """dg:<id> — «ℹ️ N» under a digest: that message whole, below the digest,
    with its time and its own buttons; the digest stays as it is."""
    config, db = _deps(context)
    item = await notifier.held_item(db, config, int(args[0])) if args and args[0].isdigit() else None
    if item is None:
        await press.answer(
            t("Полного текста уже нет: я храню его {days} дн. после сводки.").format(days=HELD_KEEP_DAYS)
        )
        return
    text, markup = item
    await context.bot.send_message(
        chat_id=config.admin_chat_id, text=text, reply_markup=markup, link_preview_options=NO_PREVIEW
    )


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
    cb.WATCHDOG: _cb_watchdog,
    cb.REPUTATION: _cb_reputation,
    cb.MAIL: _cb_mail,
    cb.OPEN: _cb_open,
    cb.DIGEST: _cb_digest,
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
    origin = getattr(update.message, "forward_origin", None)
    if kind == "conn_telegram" and getattr(origin, "type", None) == MessageOriginType.CHANNEL:
        value = str(origin.chat.id)            # a post forwarded from the channel names it, private or not
    if kind == "cookie":
        await _store_cookie(update, context, value)
    elif kind == "token":
        await _store_token(update, context, value)
    elif kind == "tz":
        name = ui.zone_from_text(value)
        if name is None:
            context.user_data["awaiting"] = "tz"
            await _reply(update, ui.input_retry_tz())
            return AWAITING_INPUT
        note = await _set_report_tz(context, ZoneInfo(name))
        await _reply(update, (await ui.settings(db, config)).noted(note))
    elif kind == "watchdog" and not await _store_watchdog(update, context, value):
        context.user_data["awaiting"] = "watchdog"
        return AWAITING_INPUT
    elif kind == "rep_words":
        words = reputation.parse_words(value)
        await db.set_setting(reputation.WORDS_KEY, ", ".join(words))
        note = t("✅ Брендовые слова: {words}").format(words=", ".join(words)) if words else t("Брендовые слова убраны")
        await _reply(update, (await ui.reputation_screen(db, config)).noted(note))
    elif kind in reputation.BY_MONITOR and not await _store_rep_key(update, context, kind, value):
        context.user_data["awaiting"] = kind
        return AWAITING_INPUT
    elif kind is not None and kind.startswith("conn_"):
        again = await _store_connection(update, context, kind, value)
        if again:
            context.user_data["awaiting"] = again
            return AWAITING_INPUT
    elif kind is not None and kind.startswith("mail_"):
        again = await _store_mail(update, context, kind, value)
        if again:
            context.user_data["awaiting"] = again
            return AWAITING_INPUT
    return ConversationHandler.END


# What «-» forgets for each network, and what its first collection needs next.
_CONN_ATTRS = {
    "conn_telegram": ("telegram_channel_id",),
    "conn_youtube": ("youtube_channel_id", "youtube_api_key"),
    "conn_youtube_key": ("youtube_channel_id", "youtube_api_key"),
    "conn_instagram": ("instagram_username",),
    "conn_linkedin": ("linkedin_profile_url",),
}


async def _keep_first_count(db: Database, platform: str, count: int) -> None:
    """A network connected from the chat has just been counted: while it has
    no value yet, that count is today's. Otherwise 🔌 Подключения said «первый
    сбор ещё не был» right under «сейчас N», and the home screen had no data
    until the next daily collection."""
    if await db.get_latest(platform) is None:
        await db.upsert(platform, count)


async def _offer_watchdog_now(context: ContextTypes.DEFAULT_TYPE) -> None:
    """After a network is connected from the chat, below the screen that says
    so: the watchdog, once ever (scheduler.offer_watchdog_once)."""
    config, db = _deps(context)
    try:
        await offer_watchdog_once(context.bot, config, db)
    except Exception:
        logger.exception("Watchdog offer failed")


async def _connect_channel(context: ContextTypes.DEFAULT_TYPE, channel: str) -> str | None:
    """Count the channel's subscribers and connect it: the line that says so,
    by the channel's title, or None when Telegram doesn't show the bot the channel."""
    config, db = _deps(context)
    count = await collect_telegram(context.bot, channel)
    if count is None:
        return None
    title, admin = await channel_info(context.bot, channel)
    await connections.save(config, db, telegram_channel_id=channel)
    await connections.remember_title(db, channel, title)
    await _keep_first_count(db, "telegram", count)
    note = t("✅ Telegram-канал {channel} подключён: сейчас {count}.").format(
        channel=f"«{title}»" if title else channel, count=_fmt(count))
    if not admin:
        note += " " + t("Чтобы видеть вступления, посты и реакции, добавь меня в администраторы канала.")
    return note


async def _store_connection(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str, value: str) -> str | None:
    """The message after «➕ <network>» on 🔌 Подключения: the value is
    checked — with a live request where there is one — kept in the database
    and put to work at once. Returns the kind to keep asking for (a value
    that was not taken, or YouTube's second step), None when the step is over."""
    config, db = _deps(context)
    chat = update.effective_chat

    async def again(note: str, step: str = kind) -> str:
        screen = ui.input_retry(note)
        await chat.send_message(screen.text, **_markup(screen))
        return step

    async def done(note: str) -> None:
        await _reply(update, (await ui.connections(db, config)).noted(note))

    if kind == "conn_anthropic":
        return await _store_claude_key(update, context, value)
    if value == connections.REMOVE and kind != "conn_youtube_key":
        await connections.remove(config, db, *_CONN_ATTRS[kind])
        context.user_data.pop("conn_youtube_channel", None)
        await done(t("Убрал то, что было задано в чате. Если сеть задана в настройках хостинга — действует она."))
        return None

    if kind == "conn_telegram":
        channel = connections.telegram_channel(value)
        if channel is None and connections.invite_link(value):
            return await again(t(
                "❌ По ссылке-приглашению я не узнаю, какой это канал. Перешли сюда любой пост из канала "
                "— или нажми «✖️ Отмена»."
            ))
        if channel is None:
            return await again(t(
                "❌ Нужен @username канала или ссылка t.me/…, а у закрытого канала — любой его пост, "
                "пересланный сюда. Пришли ещё раз или нажми «✖️ Отмена»."
            ))
        note = await _connect_channel(context, channel)
        if note is None:
            return await again(t(
                "❌ Не вижу канал {channel}. Проверь имя и добавь меня в администраторы канала, "
                "потом пришли его ещё раз — или нажми «✖️ Отмена»."
            ).format(channel=channel))
        await done(note)
        await _offer_watchdog_now(context)
    elif kind == "conn_youtube":
        channel = connections.youtube_channel(value)
        if channel is None:
            return await again(t("❌ Нужен id канала — 24 знака, начинается с UC (YouTube → Настройки → Расширенные настройки), или ссылка youtube.com/channel/UC…. Пришли ещё раз или нажми «✖️ Отмена»."))
        context.user_data["conn_youtube_channel"] = channel
        if config.youtube_api_key:        # the key is already there (.env or an earlier step): check the pair now
            return await _store_connection(update, context, "conn_youtube_key", config.youtube_api_key)
        return await again(ui.prompt_text("conn_youtube_key"), "conn_youtube_key")
    elif kind == "conn_youtube_key":
        channel = context.user_data.get("conn_youtube_channel") or config.youtube_channel_id
        typed = value != config.youtube_api_key
        note = ""
        if typed:                         # a secret: out of the chat history before any check
            try:
                await update.message.delete()
            except Exception:
                note = "\n" + t("🟠 Удалить сообщение с ключом не получилось — удали его из чата вручную.")
        key = connections.youtube_key(value)
        if key is None or not channel:
            return await again(t("❌ Это не похоже на ключ YouTube Data API. Пришли его ещё раз или нажми «✖️ Отмена».") + note)
        async with aiohttp.ClientSession() as session:
            count = await collect_youtube(session, key, channel)
        if count is None:
            return await again(t(
                "❌ YouTube не отдал число подписчиков канала {channel} с этим ключом. Проверь, что в проекте включён "
                "YouTube Data API v3 и id канала верный, и пришли ключ ещё раз — или нажми «✖️ Отмена»."
            ).format(channel=channel) + note)
        context.user_data.pop("conn_youtube_channel", None)
        await connections.save(config, db, youtube_channel_id=channel, youtube_api_key=key)
        await _keep_first_count(db, "youtube", count)
        await done(t("✅ YouTube подключён: сейчас {count}.").format(count=_fmt(count)) + note)
        await _offer_watchdog_now(context)
    elif kind == "conn_instagram":
        username = connections.instagram_username(value)
        if username is None:
            return await again(t("❌ Нужен @username Instagram или ссылка на профиль. Пришли ещё раз или нажми «✖️ Отмена»."))
        await connections.save(config, db, instagram_username=username)
        await done(t("✅ Instagram @{username} записан. Остался токен: кнопка «📸 Instagram» ниже.").format(username=username))
    elif kind == "conn_linkedin":
        url = connections.linkedin_url(value)
        if url is None:
            return await again(t("❌ Нужна ссылка на профиль вида linkedin.com/in/…. Пришли ещё раз или нажми «✖️ Отмена»."))
        await connections.save(config, db, linkedin_profile_url=url)
        await done(t("✅ Профиль LinkedIn записан. Дальше — cookie или число вручную: кнопка «💼 LinkedIn» ниже."))
    return None


# What a failed live check of a Claude key says (classifier.check_key).
_CLAUDE_KEY_ANSWERS = {
    classifier.KEY_REFUSED: "❌ Ключ не принят: проверь, что он скопирован целиком и не отозван.",
    classifier.KEY_NO_ACCESS: "❌ У ключа нет доступа к API: проверь его рабочее пространство на console.anthropic.com.",
    classifier.KEY_NO_MODEL: "❌ Ключ работает, но модель {model} ему недоступна.",
    classifier.KEY_UNCHECKED: "⚠️ Не смог проверить ключ: Anthropic сейчас не отвечает. Попробуй через пару минут.",
}


async def _store_claude_key(update: Update, context: ContextTypes.DEFAULT_TYPE, value: str) -> str | None:
    """The message after «🔑 Прислать ключ Claude» on 💬 Комментарии: out of
    the chat at once, checked live (reading the model is free), kept as a
    secret (db._SECRET_SETTINGS) and laid over the config — the next comment
    is checked with it and the log redactor masks it. «-» forgets the key set
    here; one in the hosting settings is in force again."""
    config, db = _deps(context)
    chat = update.effective_chat

    async def again(note: str) -> str:
        screen = ui.input_retry(note + "\n" + t("Пришли ключ ещё раз или нажми «✖️ Отмена»."))
        await chat.send_message(screen.text, **_markup(screen))
        return "conn_anthropic"

    async def done(note: str) -> None:
        await _reply(update, (await ui.comments_screen(db, config)).noted(note))

    if value.strip() == connections.REMOVE:
        await connections.remove(config, db, "anthropic_api_key")
        await done(t("Убрал ключ, заданный в чате. Если ключ задан в настройках хостинга — действует он."))
        return None
    note = ""
    try:                                  # a secret: out of the chat history before any check
        await update.message.delete()
    except Exception:
        note = "\n" + t("🟠 Удалить сообщение с ключом не получилось — удали его из чата вручную.")
    key = connections.anthropic_key(value)
    if key is None:
        return await again(t("❌ Это не похоже на ключ Claude API: он начинается с sk-ant-.") + note)
    answer = await classifier.check_key(key, config.comments_model)
    if answer != classifier.KEY_OK:
        return await again(t(_CLAUDE_KEY_ANSWERS[answer]).format(model=config.comments_model) + note)
    await connections.save(config, db, anthropic_api_key=key)
    await done(t("✅ Ключ Claude принят: модель {model} ему доступна. Проверяю комментарии со следующего.").format(
        model=config.comments_model) + note)
    return None


async def _worker_answers(url: str, token: str) -> str:
    """A live check of a mail-worker: «ok», «token» (401) or «unreachable»."""
    try:
        async with aiohttp.ClientSession() as session, session.get(
            f"{url}/events", headers={"Authorization": f"Bearer {token}"}, timeout=aiohttp.ClientTimeout(total=20)
        ) as resp:
            if resp.status == 200:
                return "ok"
            return "token" if resp.status in (401, 403) else "unreachable"
    except Exception as e:
        logger.warning("Mail worker check failed: %s", type(e).__name__)
        return "unreachable"


async def _store_mail(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str, value: str) -> str | None:
    """The steps after «📮 Отдельный ящик» (address, then the app password)
    and «☁️ Свой воркер» (address, then the token) on ✉️ Письма безопасности.
    The secret's message leaves the chat first; each pair is checked live —
    an IMAP sign-in, a request to the worker — before it is kept and laid over
    the config. Returns the step to keep asking for, None when it is over."""
    config, db = _deps(context)
    chat = update.effective_chat
    step = context.user_data

    async def again(note: str, next_kind: str = kind) -> str:
        screen = ui.input_retry(note) if next_kind == kind else ui.input_prompt(next_kind)
        if next_kind != kind and note:
            screen = screen.noted(note)
        await chat.send_message(screen.text, **_markup(screen))
        return next_kind

    async def done(note: str) -> None:
        await _reply(update, (await ui.mail_screen(db, config)).noted(note))

    async def out_of_chat() -> str:
        try:
            await update.message.delete()
            return ""
        except Exception:
            return "\n" + t("🟠 Удалить сообщение не получилось — удали его из чата вручную.")

    if kind == "mail_box":
        if value.strip() == connections.REMOVE:
            await mailbox.disconnect(config, db)
            await done(t("Убрал ящик, заданный в чате."))
            return None
        address = mailbox.address(value)
        if address is None:
            return await again(t("❌ Это не похоже на адрес почты. Пришли его ещё раз или нажми «✖️ Отмена»."))
        if mailbox.servers_for(address) is None:
            return await again(t(
                "❌ Пока я умею только Gmail и Яндекс: адрес на gmail.com, yandex.ru, ya.ru или yandex.com. "
                "Заведи такой ящик для бота и пришли его адрес — или нажми «✖️ Отмена»."))
        step["mailbox_address"] = address
        return await again("", "mail_box_pw")
    if kind == "mail_box_pw":
        address = step.get("mailbox_address") or config.mailbox_address
        note = await out_of_chat()
        if not address:
            return await again(t("❌ Сначала адрес ящика: нажми «📮 Отдельный ящик» ещё раз.") + note)
        password = mailbox.app_password(value)
        try:
            validity, top = await asyncio.to_thread(mailbox.probe, address, password)
        except mailbox.MailboxError as e:
            if e.kind == mailbox.AUTH:
                why = t("❌ Ящик {address} не принял пароль. Нужен пароль приложения, а не пароль от почты.").format(
                    address=address)
                if mailbox.is_yandex(address):
                    why += " " + t("Яндекс: проверь, что почтовые программы (IMAP) разрешены, и учти, что новый "
                                   "пароль приложения может заработать не сразу — тогда пришли его чуть позже.")
            else:
                why = t("⚠️ Не смог достучаться до почтового сервера. Попробуй через пару минут.")
            return await again(why + " " + t("Пришли пароль ещё раз или нажми «✖️ Отмена».") + note)
        step.pop("mailbox_address", None)
        await connections.save(config, db, mailbox_address=address, mailbox_password=password)
        await mailbox.start_at(db, validity, top)
        for key in (mailbox.ERROR_KEY, mailbox.AUTH_STREAK, mailbox.NET_STREAK, mailbox.AUTH_ALERTED):
            await db.set_setting(key, "")
        await done(t("✅ Ящик {address} подключён: читаю новые письма раз в 5 минут; то, что уже лежит в ящике, "
                     "не трогаю.").format(address=address) + note)
        return None
    if kind == "mail_worker":
        if value.strip() == connections.REMOVE:
            await connections.remove(config, db, "security_mail_url", "security_mail_token")
            await done(t("Убрал воркер, заданный в чате. Если он задан в настройках хостинга — действует он."))
            return None
        url = connections.worker_url(value)
        if url is None:
            return await again(t("❌ Нужен адрес вида https://socialbot-mail.<аккаунт>.workers.dev. Пришли ещё раз "
                                 "или нажми «✖️ Отмена»."))
        step["mail_worker_url"] = url
        return await again("", "mail_worker_token")
    if kind == "mail_worker_token":
        url = step.get("mail_worker_url") or config.security_mail_url
        note = await out_of_chat()
        token = value.strip()
        if not url or not token:
            return await again(t("❌ Сначала адрес воркера: нажми «☁️ Свой воркер» ещё раз.") + note)
        answer = await _worker_answers(url, token)
        if answer == "token":
            return await again(t("❌ Воркер не принял токен. Пришли тот, что задан у воркера, или нажми «✖️ Отмена».")
                               + note)
        if answer != "ok":
            return await again(t("⚠️ Воркер не ответил. Проверь адрес и пришли токен ещё раз — или нажми «✖️ Отмена».")
                               + note)
        step.pop("mail_worker_url", None)
        await connections.save(config, db, security_mail_url=url, security_mail_token=token)
        await done(t("✅ Воркер подключён: забираю у него письма раз в 5 минут.") + note)
        return None
    return None


async def input_conv_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("awaiting", None)
    context.user_data.pop("conn_youtube_channel", None)
    context.user_data.pop("mailbox_address", None)
    context.user_data.pop("mail_worker_url", None)
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
                # A post forwarded from the channel («➕ Telegram»): it may carry no text.
                MessageHandler((filters.TEXT | filters.FORWARDED) & ~filters.COMMAND, input_conv_value),
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

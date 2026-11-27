"""Callback data of the buttons, in one place.

The screens (bot/ui.py), the handlers and the notifier all need the ids: an
alert carries a button that opens a screen, and the notifier cannot import
the screens (ui imports the notifier). Ids are short — Telegram allows 64
bytes of callback data — and never change, since menus of older versions
stay in the chat.
"""

from __future__ import annotations

from collections.abc import Iterable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.i18n import t

# Screens.
HOME = "home"
NOW = "now"
DYNAMICS = "dyn"
CHART = "chart"
TABLE = "tbl"
SECURITY = "sec"
SETTINGS = "set"
MONITORS = "mod"
LINKEDIN = "li"
INSTAGRAM = "ig"
ABOUT = "about"          # «📖 Что я умею»
ICONS = "icons"          # «❓ Значки»
HELP = "help"            # the «❓ Помощь» of 1.0–1.4: opens «📖 Что я умею»
CONNECTIONS = "conn"
COMMENTS = "cm"
CHANNEL = "ch"
WATCHDOG = "wd"          # ⏱ Сторож: wd | wd:test | wd:off[:yes]
REPUTATION = "rep"       # 🔎 Репутация: rep | rep:now
# Settings screens an alert may open (open:<id>); inside the menu they are set:time, set:tz, set:when.
OPEN_TIME = "rtime"      # 🕗 Время отчёта
OPEN_TZ = "rtz"          # 🌍 Часовой пояс
OPEN_WHEN = "when"       # 🔔 Когда писать

# Actions.
OPEN = "open"            # open:<screen> — the screen as a new message; the alert it sits on stays
MUTE = "mute"            # mute — the picker; mute:<1h|4h|8h|1d|off>, with :home when pressed on the home screen
MUTE_QUICK = f"{MUTE}:8h"
MUTE_OFF = f"{MUTE}:off"
BACKUP = "backup"        # the database file now, not on Sunday
RESTORE = "restore"      # restore:yes | restore:no under a .db file sent without a caption
DIGEST = "dg"            # dg:<id> — «ℹ️ N» under a digest: the held message in full, below it

# Entry points of the text-input conversations (bot/handlers.py); a handler
# that walks every button skips them, since the answer is the next message.
LI_ENTER = "li:enter"
LI_CANCEL = "li:cancel"
LI_COOKIE = "li:cookie"
IG_TOKEN = "ig:token"
TZ_OTHER = "set:tz:other"
WD_URL = "wd:url"
# The reputation report's inputs: the brand words and one read-only key per source.
REP_WORDS = "rep:words"
REP_KEYS = {"rep_google": "rep:k:g", "rep_yandex": "rep:k:y", "rep_ai": "rep:k:c"}
# A network connected from the chat (bot/connections.py): platform id → entry.
CONN_ADD = {"telegram": "conn:tg", "youtube": "conn:yt", "instagram": "conn:ig", "linkedin": "conn:li"}
# The comment check's Claude key, sent on 💬 Комментарии; cm:lim:<n> picks the daily limit there.
CLAUDE_KEY = "cm:key"
COMMENTS_LIMIT = "cm:lim"
INPUT_CANCEL = "input:cancel"
CONVERSATION_ENTRIES = frozenset({LI_ENTER, LI_COOKIE, IG_TOKEN, TZ_OTHER, WD_URL, REP_WORDS, *REP_KEYS.values(),
                                  *CONN_ADD.values(), CLAUDE_KEY})

# The screens an alert or a report may open, with their labels (translated when built).
SCREEN_LABELS = {
    HOME: "🏠 Главная",
    DYNAMICS: "📈 Динамика",
    SECURITY: "🛡 Безопасность",
    CHANNEL: "📣 Канал",
    COMMENTS: "💬 Комментарии",
    CONNECTIONS: "🔌 Подключения",
    WATCHDOG: "⏱ Сторож",
    REPUTATION: "🔎 Репутация",
    SETTINGS: "⚙️ Настройки",
    MONITORS: "🧩 Мониторинги",
    OPEN_TIME: "🕗 Время отчёта",
    OPEN_TZ: "🌍 Часовой пояс",
    OPEN_WHEN: "🔔 Когда писать",
}


def actions_markup(
    screens: Iterable[str] = (), *, mute: bool = False, monitor: str | None = None
) -> InlineKeyboardMarkup | None:
    """The row under an alert: the screens it leads to, «🔕 Тихо 8 ч» for one
    that may wait, and «⚙️ Не присылать такие» for the monitor that sent it."""
    row = [
        InlineKeyboardButton(t(SCREEN_LABELS[screen]), callback_data=f"{OPEN}:{screen}")
        for screen in screens
        if screen in SCREEN_LABELS
    ]
    if mute:
        row.append(InlineKeyboardButton(t("🔕 Тихо 8 ч"), callback_data=MUTE_QUICK))
    rows = [row] if row else []
    if monitor:
        rows.append([InlineKeyboardButton(t("⚙️ Не присылать такие"), callback_data=f"{MONITORS}:{monitor}:off")])
    return InlineKeyboardMarkup(rows) if rows else None

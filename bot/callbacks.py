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

# Actions.
OPEN = "open"            # open:<screen> — the screen as a new message; the alert it sits on stays
MUTE = "mute"            # mute — the picker; mute:<1h|4h|8h|1d|off>, with :home when pressed on the home screen
MUTE_QUICK = f"{MUTE}:8h"
MUTE_OFF = f"{MUTE}:off"
BACKUP = "backup"        # the database file now, not on Sunday
RESTORE = "restore"      # restore:yes | restore:no under a .db file sent without a caption

# Entry points of the text-input conversations (bot/handlers.py); a handler
# that walks every button skips them, since the answer is the next message.
LI_ENTER = "li:enter"
LI_CANCEL = "li:cancel"
LI_COOKIE = "li:cookie"
IG_TOKEN = "ig:token"
TZ_OTHER = "set:tz:other"
INPUT_CANCEL = "input:cancel"
CONVERSATION_ENTRIES = frozenset({LI_ENTER, LI_COOKIE, IG_TOKEN, TZ_OTHER})

# The screens an alert or a report may open, with their labels (translated when built).
SCREEN_LABELS = {
    HOME: "🏠 Главная",
    DYNAMICS: "📈 Динамика",
    SECURITY: "🛡 Безопасность",
    CHANNEL: "📣 Канал",
    COMMENTS: "💬 Комментарии",
    CONNECTIONS: "🔌 Подключения",
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

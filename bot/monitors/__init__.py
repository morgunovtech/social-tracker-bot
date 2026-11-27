"""Monitors: what is alert-worthy and how it is phrased.

Every monitor can be switched off in /modules (stored in settings as
monitor_<id> = off); one that needs configuration is unavailable until it
has it. Platforms are switched on by their own configuration, not here.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from telegram import LinkPreviewOptions

from bot import platforms
from bot.config import Config
from bot.db import Database

# ── Icons: one dictionary (BOT_PRINCIPLES.md §1) ───────────────────────────
#
# The icon says how urgent, the text says what happened. Two problem levels:
#
#   critical  🔴  act now — rings, passes quiet hours and /mute
#   warning   🟠  act, but not today — silent, waits for the digest at night
#
# Everything else is a state, not a level: it never rings by itself. A likely
# hijack is 🔴 too, with «похоже на взлом» said in words in its headline;
# there is no icon of its own for it. The same icons are used in the alerts,
# on the screens, in the reports and in the legend (ICON_LEGEND).
LEVEL_ICONS = {"critical": "🔴", "warning": "🟠"}
CRITICAL, WARNING = LEVEL_ICONS["critical"], LEVEL_ICONS["warning"]
OK = "✅"             # fine · works again · switched on
UNCHECKED = "⚠️"      # could not check — the bot tries again by itself
PENDING = "⏳"        # waiting for the first check
INFO = "ℹ️"           # a fact that is not a problem
OFF = "⬜"            # switched off
NOT_CONNECTED = "➖"  # not connected: a network or an integration without its key
UNMARKED = "❓"       # a checklist item without an answer
# The words a hijack sign carries in its headline (translated where shown).
HIJACK = "похоже на взлом"

# What each icon means and what the bot does with it, in the order the legend
# shows them; Russian, translated where it is drawn.
ICON_LEGEND: tuple[tuple[str, str, str], ...] = (
    (CRITICAL, "нужно действие сейчас", "звонит сразу, даже ночью и в тишине"),
    (WARNING, "нужно действие, но не сегодня", "без звука; ночью и в тишине ждёт сводки"),
    (OK, "в порядке · снова работает · включено", ""),
    (UNCHECKED, "не смог проверить", "попробую ещё раз сам, тревогу не поднимаю"),
    (PENDING, "жду первой проверки", ""),
    (INFO, "факт, который не проблема", ""),
    (OFF, "выключено", ""),
    (NOT_CONNECTED, "не подключено", ""),
    (UNMARKED, "не отмечено", "пункт чек-листа без ответа"),
)


def level_icon(level: str | None) -> str:
    """🔴 for critical, 🟠 for every other problem level."""
    return LEVEL_ICONS.get(level or "", WARNING)


# Security alerts quote changed descriptions and email subjects: a link in
# them may be a scam page, so Telegram must not fetch and preview it.
NO_PREVIEW = LinkPreviewOptions(is_disabled=True)

# Characters that change how the rest of a line reads while staying invisible:
# direction overrides and isolates (U+202A–U+202E, U+2066–U+2069 — «exe.png»
# reads «gnp.exe», «evil.com moc.elgoog» reads backwards), zero-width and
# joiner marks (U+200B–U+200F, U+2060–U+2064), the byte-order mark and C0
# controls other than newline and tab. The same set as TofsDevOps' clean().
_INVISIBLE = dict.fromkeys([*range(0x202A, 0x202F), *range(0x2066, 0x206A), *range(0x200B, 0x2010),
                            *range(0x2060, 0x2065), 0xFEFF, 0x7F,
                            *(c for c in range(0x20) if c not in (0x09, 0x0A))])


def clean(text: object) -> str:
    """Someone else's text as it will be shown: no direction overrides, no
    zero-width marks, no control characters. A display name, a profile
    description or a mail subject cannot redraw the line around it."""
    return str(text).translate(_INVISIBLE)


# A URL, or anything Telegram would turn into a link: a bare domain.
_LINKISH = re.compile(r"(?:https?://|www\.)\S+|\b[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}\b(?:/\S*)?", re.IGNORECASE)


def defang(text: str) -> str:
    """Quoted, untrusted text made safe to show: invisible direction and
    format characters removed (clean), links readable but not clickable —
    https://evil.example/x → hxxps://evil[.]example/x. Telegram links every
    URL and bare domain whether or not previews are on."""

    def _one(match: re.Match) -> str:
        link = re.sub(r"^http", "hxxp", match.group(0), flags=re.IGNORECASE)
        return link.replace(".", "[.]")

    return _LINKISH.sub(_one, clean(text))


@dataclass(frozen=True)
class Monitor:
    id: str
    label: str
    description: str
    requires: Callable[[Config], bool] = lambda config: True
    needs: str = ""  # what to configure while requires() is false
    # A key the owner sends in the chat (🔌 Подключения → 🔎 Репутация), kept
    # in this setting: the monitor is off until it is there.
    secret: str = ""
    # Whether it is on while the owner never touched its switch.
    default_on: bool = True


def _has_profiles(config: Config) -> bool:
    return any(p.profile_fields for p in platforms.enabled(config))


def _has_mail(config: Config) -> bool:
    """A mail-worker, a separate mailbox (bot/mailbox.py), or both."""
    return bool(config.security_mail_url and config.security_mail_token) or bool(
        config.mailbox_address and config.mailbox_password
    )


def _has_channel(config: Config) -> bool:
    return bool(config.telegram_channel_id)


def _has_comments(config: Config) -> bool:
    return bool(config.anthropic_api_key and (config.telegram_channel_id or config.comments_chat_id))


MONITORS: tuple[Monitor, ...] = (
    Monitor("followers", "Подписчики", "падения, наплыв ботов, круглые числа"),
    Monitor("collection", "Сбор данных", "сбои несколько дней подряд, истёкший cookie LinkedIn или токен Instagram"),
    Monitor(
        "profile",
        "Профиль",
        "смена названия, описания и ссылок, аватарки; новые админы; пропавшие видео",
        requires=_has_profiles,
        needs="Telegram-канал, YouTube или Instagram",
    ),
    Monitor(
        "links",
        "Ссылки в профилях",
        "раз в неделю — куда ведут ссылки в описаниях: не открывается, переадресация, технический адрес",
        requires=_has_profiles,
        needs="Telegram-канал, YouTube или Instagram",
    ),
    Monitor("hygiene", "Чек-лист безопасности", "2FA и пароли: балл в отчёте, напоминание раз в месяц"),
    Monitor(
        "outgoing",
        "Отправки наружу",
        "цифры на сайт, строки в TofsDevOps, отметки сторожу: сутки не доходят — скажу, где и почему",
    ),
    Monitor(
        "mail",
        "Письма безопасности",
        "новые входы, смена пароля, телефона и 2FA, новые ключи и токены, новый владелец сайта в поиске, коды входа — "
        "из пересланных писем соцсетей, GitHub, Microsoft, Яндекса",
        requires=_has_mail,
        needs="почта — 🔌 Подключения → ✉️ Письма безопасности",
    ),
    Monitor(
        "rep_google",
        "Поиски в Google",
        "раз в неделю: сколько раз тебя и твои продукты искали в Google — показы и клики по брендовым запросам",
        secret="rep_google_key",
    ),
    Monitor(
        "rep_yandex",
        "Поиски в Яндексе",
        "раз в неделю: брендовые запросы в Яндексе — показы и клики",
        secret="rep_yandex_token",
    ),
    Monitor(
        "rep_ai",
        "ИИ-ассистенты",
        "раз в неделю: сколько раз ChatGPT, Perplexity и другие открывали твои страницы по запросам людей",
        secret="rep_cloudflare_token",
    ),
    Monitor(
        "channel",
        "Жизнь канала",
        "подписки и отписки, откуда пришли, посты и реакции — экран 📣 Канал и строка в отчёте",
        requires=_has_channel,
        needs="Telegram-канал, бот в его админах",
    ),
    Monitor(
        "comments",
        "Комментарии",
        "запрещённый контент в обсуждении канала: наркотики, порно, экстремизм, мошенничество — карточка с кнопками",
        requires=_has_comments,
        needs="ключ Claude (🔌 Подключения → 💬 Комментарии) и Telegram-канал с группой обсуждения",
    ),
    # A failed deploy, the weekly vulnerabilities in the bot's packages and the
    # Dependabot PRs waiting for a human: only whoever owns the code can act on
    # them, so a bot deployed from someone else's repository (the Railway
    # template) starts with it off. A bot that ran before 1.13.0 keeps it on
    # (updates.adopt_dev_notices). UPDATE_WATCH=0 still switches it all off.
    # BOT_PRINCIPLES §6, the exception of 2026-11-27.
    Monitor(
        "dev_notices",
        "Для разработчика",
        "упавший деплой, PR от Dependabot и уязвимости в пакетах: исправить это может только владелец кода",
        requires=lambda config: config.update_watch,
        needs="слежение за обновлениями — его выключили в настройках хостинга",
        default_on=False,
    ),
)
DEV_NOTICES = "dev_notices"
BY_ID: dict[str, Monitor] = {m.id: m for m in MONITORS}


def switch_key(monitor_id: str) -> str:
    """The setting that keeps the user's switch: «off», «on» or absent (on)."""
    return f"monitor_{monitor_id}"



async def is_switched_on(db: Database, monitor_id: str) -> bool:
    """The user's switch alone, regardless of configuration; the monitor's
    default while the owner never touched it."""
    value = await db.get_setting(switch_key(monitor_id))
    if value is None:
        monitor = BY_ID.get(monitor_id)
        return monitor.default_on if monitor else True
    return value != "off"


async def is_connected(db: Database, monitor_id: str) -> bool:
    """Its key, if it needs one from the chat, is there."""
    secret = BY_ID[monitor_id].secret
    return not secret or bool(await db.get_setting(secret))


async def is_on(db: Database, config: Config, monitor_id: str) -> bool:
    return (BY_ID[monitor_id].requires(config) and await is_connected(db, monitor_id)
            and await is_switched_on(db, monitor_id))


async def toggle(db: Database, monitor_id: str) -> bool:
    """Flip the switch; returns the new state."""
    new_state = not await is_switched_on(db, monitor_id)
    await set_switch(db, monitor_id, new_state)
    return new_state


async def set_switch(db: Database, monitor_id: str, on: bool) -> None:
    await db.set_setting(switch_key(monitor_id), "on" if on else "off")

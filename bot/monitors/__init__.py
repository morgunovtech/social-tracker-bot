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

# Security alerts quote changed descriptions and email subjects: a link in
# them may be a scam page, so Telegram must not fetch and preview it.
NO_PREVIEW = LinkPreviewOptions(is_disabled=True)

# A URL, or anything Telegram would turn into a link: a bare domain.
_LINKISH = re.compile(r"(?:https?://|www\.)\S+|\b[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}\b(?:/\S*)?", re.IGNORECASE)


def defang(text: str) -> str:
    """Make the links in quoted, untrusted text readable but not clickable:
    https://evil.example/x → hxxps://evil[.]example/x. Telegram links every URL
    and bare domain whether or not previews are on."""

    def _one(match: re.Match) -> str:
        link = re.sub(r"^http", "hxxp", match.group(0), flags=re.IGNORECASE)
        return link.replace(".", "[.]")

    return _LINKISH.sub(_one, text)


@dataclass(frozen=True)
class Monitor:
    id: str
    label: str
    description: str
    requires: Callable[[Config], bool] = lambda config: True
    needs: str = ""  # what to configure while requires() is false


def _has_profiles(config: Config) -> bool:
    return any(p.profile_fields for p in platforms.enabled(config))


def _has_mail(config: Config) -> bool:
    return bool(config.security_mail_url and config.security_mail_token)


MONITORS: tuple[Monitor, ...] = (
    Monitor("followers", "Подписчики", "падения, наплыв ботов, круглые числа"),
    Monitor("collection", "Сбор данных", "сбои несколько дней подряд, истёкший cookie LinkedIn"),
    Monitor(
        "profile",
        "Профиль",
        "смена названия, описания и ссылок, аватарки; новые админы; пропавшие видео",
        requires=_has_profiles,
        needs="Telegram-канал или YouTube",
    ),
    Monitor("hygiene", "Гигиена", "чек-лист 2FA и паролей, балл безопасности, напоминания"),
    Monitor(
        "mail",
        "Письма безопасности",
        "новые входы, смена пароля, коды входа — из пересланных писем",
        requires=_has_mail,
        needs="SECURITY_MAIL_URL и SECURITY_MAIL_TOKEN",
    ),
)
BY_ID: dict[str, Monitor] = {m.id: m for m in MONITORS}


def _key(monitor_id: str) -> str:
    return f"monitor_{monitor_id}"


async def is_switched_on(db: Database, monitor_id: str) -> bool:
    """The user's switch alone, regardless of configuration."""
    return await db.get_setting(_key(monitor_id)) != "off"


async def is_on(db: Database, config: Config, monitor_id: str) -> bool:
    return BY_ID[monitor_id].requires(config) and await is_switched_on(db, monitor_id)


async def toggle(db: Database, monitor_id: str) -> bool:
    """Flip the switch; returns the new state."""
    new_state = not await is_switched_on(db, monitor_id)
    await db.set_setting(_key(monitor_id), "on" if new_state else "off")
    return new_state

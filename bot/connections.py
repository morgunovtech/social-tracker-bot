"""Networks connected from the chat (🔌 Подключения → «➕ …»).

What names a network — the Telegram channel, the YouTube channel and its API
key, the Instagram @username, the LinkedIn profile — used to live only in
.env, which on a hosted install means a trip to the panel's variables. Each
can now be sent to the bot as a message: it is checked (a live request where
one exists), kept in the database and laid over the config, so collection
starts without a restart. A value set in the chat wins over .env (chat beats
.env, BOT_PRINCIPLES §5); «-» removes it and the variable is in force again.

The YouTube key is a secret: its message is deleted, the Sunday backup is
made without it (db._SECRET_SETTINGS) and the log redactor reads it from the
config like the one from .env.
"""

from __future__ import annotations

import re

from bot.config import Config
from bot.db import Database

# Config attribute → the settings key it is kept under.
KEYS = {
    "telegram_channel_id": "conn_telegram_channel_id",
    "youtube_channel_id": "conn_youtube_channel_id",
    "youtube_api_key": "conn_youtube_api_key",
    "instagram_username": "conn_instagram_username",
    "linkedin_profile_url": "conn_linkedin_profile_url",
}
REMOVE = "-"

_TG_NAME = re.compile(r"^(?:https?://)?(?:t\.me|telegram\.me)/([A-Za-z][A-Za-z0-9_]{3,31})/?$|^@?([A-Za-z][A-Za-z0-9_]{3,31})$")
_TG_ID = re.compile(r"^-100\d{5,15}$")
_YT_ID = re.compile(r"(UC[A-Za-z0-9_-]{22})")
_YT_KEY = re.compile(r"^[A-Za-z0-9_-]{30,60}$")
_IG_NAME = re.compile(r"^(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9._]{1,30})/?(?:\?.*)?$|^@?([A-Za-z0-9._]{1,30})$")
_LI_URL = re.compile(r"^(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/(in/[^/?#\s]{2,100})/?(?:[?#].*)?$", re.IGNORECASE)


def telegram_channel(raw: str) -> str | None:
    """@username (also from a t.me link) or the -100… id; None when neither."""
    value = raw.strip()
    if _TG_ID.match(value):
        return value
    m = _TG_NAME.match(value)
    return f"@{m.group(1) or m.group(2)}" if m else None


def youtube_channel(raw: str) -> str | None:
    """The UC… id, also out of a youtube.com/channel/UC… link."""
    value = raw.strip()
    m = _YT_ID.fullmatch(value) or re.search(r"youtube\.com/channel/" + _YT_ID.pattern, value)
    return m.group(1) if m else None


def youtube_key(raw: str) -> str | None:
    value = raw.strip()
    return value if _YT_KEY.match(value) else None


def instagram_username(raw: str) -> str | None:
    m = _IG_NAME.match(raw.strip())
    return (m.group(1) or m.group(2)).lower() if m else None


def linkedin_url(raw: str) -> str | None:
    m = _LI_URL.match(raw.strip())
    return f"https://www.linkedin.com/{m.group(1)}/" if m else None


# What .env said, per config object: «-» in the chat brings it back.
_ENV: dict[int, dict[str, str | None]] = {}


def _env(config: Config) -> dict[str, str | None]:
    return _ENV.setdefault(id(config), {attr: getattr(config, attr) for attr in KEYS})


async def restore(config: Config, db: Database) -> None:
    """At startup: lay what the chat set over the config read from .env."""
    _env(config)
    for attr, key in KEYS.items():
        stored = (await db.get_setting(key) or "").strip()
        if stored:
            object.__setattr__(config, attr, stored)


async def save(config: Config, db: Database, **values: str) -> None:
    """Keep the values and put them to work at once."""
    _env(config)
    for attr, value in values.items():
        await db.set_setting(KEYS[attr], value)
        object.__setattr__(config, attr, value)


async def remove(config: Config, db: Database, *attrs: str) -> None:
    """Forget what the chat set: the value from .env (or nothing) is back."""
    env = _env(config)
    for attr in attrs:
        await db.set_setting(KEYS[attr], "")
        object.__setattr__(config, attr, env[attr])


async def from_chat(db: Database, attr: str) -> bool:
    return bool((await db.get_setting(KEYS[attr]) or "").strip())

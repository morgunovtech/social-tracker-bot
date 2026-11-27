"""The bot's own watchdog (BOT_PRINCIPLES §6): a dead man's switch that hears
from the bot after every daily run and writes to the owner when it does not.

The address is set from the chat (🔌 Подключения → ⏱ Сторож) with a live test
ping and kept in the DB; HEALTHCHECK_URL in .env is the fallback. Either a
healthchecks.io check (a plain GET) or a TofsDevOps heartbeat address (a POST
with a line per network, bot/tofs_status.py). The address is a secret —
whoever has it can ping in the bot's name — so it never reaches a screen, a
log line or the Sunday backup.

healthchecks.io answers a check that does not exist with HTTP 200 and
«OK (not found)»: the body is read, not only the status code.
"""

from __future__ import annotations

import json
import logging
from urllib.parse import urlsplit

import aiohttp

from bot import tofs_status
from bot.config import Config, first_url
from bot.db import Database, utcnow
from bot.i18n import t

logger = logging.getLogger(__name__)

URL_KEY = "watchdog_url"          # set from the chat; wins over HEALTHCHECK_URL
LAST_KEY = "watchdog_last"        # the last ping: {"at": ISO UTC, "error": code or null}
OFFERED_KEY = "watchdog_offered"  # «⏱ Сторож» was offered after the first collection

# Why a ping did not land, as a code (logged as is) → what the owner reads.
_REASONS = {
    "not_found": "check не найден — удалён или ссылка скопирована не целиком",
    "rejected": "отвечает ошибкой {status}",
    "timeout": "не ответил за 10 с",
    "connect": "не удаётся подключиться — сеть или DNS",
    "error": "не отвечает",
    "tofs": "TofsDevOps не принял отметку",
}
# Not reaching the watchdog says nothing about the address (⚠️ «could not
# check»); an answer that refuses it does (🟠 — fix the address).
UNCHECKED_REASONS = frozenset({"timeout", "connect", "error"})

async def url(db: Database | None, config: Config) -> str | None:
    """The address in use: the one set in the chat, else HEALTHCHECK_URL.
    A stored address is a secret setting, so the log redactor masks it
    (db.known_secrets)."""
    stored = (await db.get_setting(URL_KEY) or "").strip() if db is not None else ""
    if stored:
        return stored
    return config.healthcheck_url


async def source(db: Database, config: Config) -> str:
    """'chat', 'env' or '' — where the address in use comes from."""
    if (await db.get_setting(URL_KEY) or "").strip():
        return "chat"
    return "env" if config.healthcheck_url else ""


def parse(text: str) -> str | None:
    """The address in what the owner pasted — a whole line such as
    `&& curl -fsS https://…` included; only https:// is taken."""
    found = first_url(text)
    return found if found and found.startswith("https://") and len(found) >= 20 else None


def name(address: str) -> str:
    """What the screens say instead of the address: never the address itself."""
    if tofs_status.is_tofs_url(address):
        return "TofsDevOps"
    host = (urlsplit(address).hostname or "").lower()
    return "healthchecks.io" if host.endswith(("hc-ping.com", "healthchecks.io")) else host


def reason(code: str) -> str:
    """A ping's failure in the chat language: 'rejected:403' → «отвечает ошибкой 403»."""
    kind, _, status = code.partition(":")
    return t(_REASONS.get(kind, _REASONS["error"])).format(status=status)


async def probe(address: str) -> str | None:
    """One ping: None when the watchdog took the mark, else why not, as a code."""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(address) as resp:
                status, body = resp.status, (await resp.content.read(512)).decode(errors="replace")
    except TimeoutError:
        return "timeout"
    except aiohttp.ClientConnectorError:
        return "connect"
    except Exception as e:
        # Never the exception text: it may carry the whole address.
        logger.warning("Watchdog ping to %s failed: %s", name(address), type(e).__name__)
        return "error"
    if status >= 400:
        return f"rejected:{status}"
    if "not found" in body.lower():
        return "not_found"
    return None


async def record(db: Database, error: str | None) -> None:
    await db.set_setting(LAST_KEY, json.dumps({"at": utcnow().isoformat(), "error": error}))


async def last(db: Database) -> dict:
    try:
        data = json.loads(await db.get_setting(LAST_KEY) or "{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


async def save(db: Database, address: str) -> None:
    """A checked address from the chat; its ping just landed."""
    await db.set_setting(URL_KEY, address)
    await record(db, None)


async def forget(db: Database) -> None:
    """Switched off in the chat: HEALTHCHECK_URL, if set, takes over again."""
    await db.set_setting(URL_KEY, "")
    await db.set_setting(LAST_KEY, "")

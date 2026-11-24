"""Where the links in the profiles lead — checked once a week.

The profile monitor alerts a link that appears in a description: the classic
hijack payload. The links that were already there go stale another way: a
domain moves (morgunov.tech → s.morgunov.tech), a product gets its own host,
a page is deleted — and the description keeps sending people to a redirect or
an error. Once a week the bot follows every link in the descriptions it
watches (the stored profile baselines, so no extra API call) and says:

    🟠 a link does not open: no such host, a refused certificate or
       connection, a missing page (404, 410), a server error (5xx);
    ℹ️ a link goes through a redirect to another host — the final address
       is better in the description;
    ℹ️ a link lands on a technical host (*.pages.dev, *.workers.dev) — if
       the product has its own domain, that one is better.

Each link's state is kept; nothing repeats while it stays the same, and a
link that opens again gets one ✅. A failure is checked once more a minute
later before it counts, and when every link fails the way a dead network
fails (no DNS, no connection), it is the bot's network: nothing is said and
the check runs again the next day. A site that refuses robots (401, 403, 429, LinkedIn's
999, other 4xx) is «could not check» and changes nothing.

A description is someone else's text — after a hijack, a stranger's. Every
hop is checked before it is requested: http(s) only, a public address only,
at most MAX_HOPS redirects, the body never read. The bot must not be sent to
its own server's internal addresses.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import re
import socket
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlsplit

import aiohttp
from telegram import Bot

from bot import callbacks, humanize, monitors, notifier, platforms
from bot.config import Config
from bot.db import Database, parse_utc, utcnow
from bot.i18n import t
from bot.monitors import defang
from bot.notifier import Priority
from bot.platforms.base import TEXT

logger = logging.getLogger(__name__)

MONITOR_ID = "links"
EVERY = timedelta(days=7)
# The daily run drifts by its own duration; a week is a week less an hour.
DUE_SLACK = timedelta(hours=1)
STATE_KEY = "links_state"
CHECKED_KEY = "links_checked_at"
MAX_HOPS = 10
MAX_LINKS = 20
TIMEOUT = aiohttp.ClientTimeout(total=15)
RETRY_AFTER = 60   # seconds before a failure is checked again
USER_AGENT = "Mozilla/5.0 (compatible; SocialTrackerBot; +https://github.com/morgunovtech/social-tracker-bot)"
# Deploy hosts a product is served from before it gets a name of its own.
TECHNICAL_HOSTS = (".pages.dev", ".workers.dev")
# Consent and sign-in pages a big network puts in front of a profile: the end
# of the check, not a redirect of the link.
INTERSTITIALS = ("consent.youtube.com", "consent.google.com", "accounts.google.com")
# A missing page or a server error; anything else from 400 up is a site that
# refuses robots — could not check.
BROKEN_STATUSES = frozenset({404, 410})

# OK, BROKEN, REDIRECT, TECHNICAL — what a link's state is; UNCHECKED never stored.
OK, BROKEN, REDIRECT, TECHNICAL, UNCHECKED = "ok", "broken", "redirect", "technical", "unchecked"

_EXPLICIT = re.compile(r"(?:https?://|www\.|t\.me/)[^\s<>\"'«»()]+", re.IGNORECASE)
# A bare domain counts only with a TLD people put in profiles: «Node.js» and
# «README.md» are not links.
_BARE = re.compile(
    r"(?<![\w@./:-])((?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+"
    r"(?:com|net|org|io|dev|app|tech|me|ru|uz|kz|by|ua|co|ai|xyz|site|online|info|pro|page|link|ly|gg|tv|eu)"
    r")(/[^\s<>\"'«»()]*)?(?![\w-])",
    re.IGNORECASE,
)
_TRAILING = ".,;:!?…)]}»\"'"


@dataclass(frozen=True)
class Found:
    url: str          # as followed: with a scheme
    platform: str     # its label: «Telegram»
    field: str        # the field's label before translation: «описание канала»


@dataclass(frozen=True)
class Result:
    state: str
    final_host: str = ""
    detail: str = ""  # why it does not open, in the chat language
    tech: str = ""    # «HTTP 404», «DNS»


def extract(text: str) -> list[str]:
    """The links in a description, with a scheme, in order, without repeats."""
    found: list[str] = []
    for match in _EXPLICIT.finditer(text):
        link = match.group(0).rstrip(_TRAILING)
        found.append(link if re.match(r"https?://", link, re.I) else f"https://{link}")
    rest = _EXPLICIT.sub(" ", text)
    for match in _BARE.finditer(rest):
        found.append("https://" + match.group(0).rstrip(_TRAILING))
    return list(dict.fromkeys(found))


async def links_in_profiles(db: Database, config: Config) -> list[Found]:
    """Every link in the text fields of the stored profiles."""
    found: dict[str, Found] = {}
    for platform in platforms.enabled(config):
        raw = await db.get_setting(f"profile_{platform.id}")
        if not raw:
            continue
        try:
            fields = json.loads(raw)
        except ValueError:
            continue
        for name, (label, kind) in platform.profile_fields.items():
            if kind != TEXT or not isinstance(fields.get(name), str):
                continue
            for url in extract(fields[name]):
                found.setdefault(url, Found(url, platform.label, label))
    return list(found.values())[:MAX_LINKS]


def _bare_host(host: str) -> str:
    host = host.lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


async def _public(host: str, port: int) -> bool:
    """Does the host resolve, and only to public addresses? Raises OSError
    (socket.gaierror) when it does not resolve."""
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        pass
    infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return bool(infos) and all(ipaddress.ip_address(info[4][0]).is_global for info in infos)


async def follow(session: aiohttp.ClientSession, url: str) -> Result:
    """Follow one link hop by hop; what it is now."""
    start = _bare_host(urlsplit(url).hostname or "")
    current = url
    for _ in range(MAX_HOPS + 1):
        parts = urlsplit(current)
        host = (parts.hostname or "").lower()
        if parts.scheme not in ("http", "https") or not host:
            return Result(UNCHECKED, tech="scheme")
        if host in INTERSTITIALS:
            return Result(OK, start)   # a network's consent page: the profile is behind it
        try:
            if not await _public(host, parts.port or (443 if parts.scheme == "https" else 80)):
                return Result(UNCHECKED, tech="private address")
        except OSError:
            return Result(BROKEN, host, t("адрес {host} не находится").format(host=defang(host)), "DNS")
        try:
            async with session.get(current, allow_redirects=False, timeout=TIMEOUT,
                                   headers={"User-Agent": USER_AGENT}) as resp:
                status, location = resp.status, resp.headers.get("Location")
        except aiohttp.ClientConnectorCertificateError:
            return Result(BROKEN, host, t("сертификат сайта не принимается"), "TLS")
        except aiohttp.ClientSSLError:
            return Result(BROKEN, host, t("защищённое соединение не устанавливается"), "TLS")
        except aiohttp.ClientConnectorError:
            return Result(BROKEN, host, t("сайт не принимает соединение"), "connect")
        except TimeoutError:
            return Result(BROKEN, host, t("сайт не ответил за 15 с"), "timeout")
        except aiohttp.ClientError as e:
            return Result(UNCHECKED, tech=type(e).__name__)
        if 300 <= status < 400 and location:
            current = urljoin(current, location)
            continue
        if status in BROKEN_STATUSES:
            return Result(BROKEN, host, t("страница не найдена ({status})").format(status=status), f"HTTP {status}")
        if 500 <= status < 600:     # LinkedIn's 999 is a refusal, not a server error
            return Result(BROKEN, host, t("сайт отвечает ошибкой {status}").format(status=status), f"HTTP {status}")
        if status >= 400:
            return Result(UNCHECKED, tech=f"HTTP {status}")
        final = _bare_host(host)
        if final.endswith(TECHNICAL_HOSTS):
            return Result(TECHNICAL, final)
        return Result(REDIRECT if final != start else OK, final)
    return Result(BROKEN, "", t("переадресаций больше {n}").format(n=MAX_HOPS), "redirect loop")


# Failures that say as much about the bot's own network as about the site.
NETWORK_TECH = frozenset({"DNS", "connect", "timeout"})


async def check_links(session: aiohttp.ClientSession, urls: list[str], retry_after: float = RETRY_AFTER,
                      ) -> dict[str, Result] | None:
    """Every link once; the failures once more after one pause, together — a
    failure counts only when it is still there a minute later. None when
    every link failed the way a dead network fails: then it is the bot's
    own network, not the sites (BOT_PRINCIPLES §4), and nothing is said."""
    results = {url: await follow(session, url) for url in urls}
    broken = [url for url, result in results.items() if result.state == BROKEN]
    if broken and retry_after:
        await asyncio.sleep(retry_after)
        for url in broken:
            results[url] = await follow(session, url)
    if len(results) >= 2 and all(r.state == BROKEN and r.tech in NETWORK_TECH for r in results.values()):
        return None
    return results


def _when(raw: str | None) -> datetime | None:
    try:
        return parse_utc(raw) if raw else None
    except ValueError:
        return None


async def due(db: Database, now: datetime | None = None) -> bool:
    last = _when(await db.get_setting(CHECKED_KEY))
    return last is None or (now or utcnow()) - last >= EVERY - DUE_SLACK


def _where(found: Found) -> str:
    return t("{platform}, {field}").format(platform=found.platform, field=t(found.field))


def _shown(url: str) -> str:
    """A link as a message quotes it: someone's text, defanged and short."""
    text = re.sub(r"^https://", "", url)
    return defang(text if len(text) <= 80 else text[:79] + "…")


async def check(bot: Bot, config: Config, db: Database, session: aiohttp.ClientSession,
                retry_after: float = RETRY_AFTER) -> int:
    """Follow every link, tell what changed; returns the messages sent.
    The new state is kept only once its messages went out."""
    try:
        before = json.loads(await db.get_setting(STATE_KEY) or "{}")
    except ValueError:
        before = {}
    now = utcnow()
    state: dict[str, dict] = {}
    alerts: list[str] = []
    notes: list[str] = []
    tz = await notifier.owner_tz(db, config)
    found_links = await links_in_profiles(db, config)
    results = await check_links(session, [found.url for found in found_links], retry_after)
    if results is None:
        logger.warning("Profile links: every link failed like a dead network — not told, checked again tomorrow")
        return 0
    for found in found_links:
        result = results[found.url]
        was = before.get(found.url, {})
        if result.state == UNCHECKED:
            if was:
                state[found.url] = was   # a site that refuses robots says nothing new
            logger.info("Link not checked (%s): %s", result.tech, found.platform)
            continue
        entry = {"state": result.state, "final": result.final_host,
                 "since": was.get("since") if was.get("state") == result.state else now.isoformat()}
        state[found.url] = entry
        changed = was.get("state") != result.state or was.get("final") != result.final_host
        if result.state == BROKEN and was.get("state") != BROKEN:
            head = t("🟠 {where}: ссылка не открывается — {why}").format(where=_where(found), why=result.detail)
            alerts.append(humanize.alert(
                [head, _shown(found.url)], "link_broken", result.tech, t("проверка ссылок раз в неделю"),
            ))
        elif was.get("state") == BROKEN and result.state != BROKEN:
            how_long = humanize.lasted(_when(was.get("since")), None, now, tz)
            alerts.append(humanize.recovery(
                t("✅ {where}: ссылка снова открывается — {link}").format(where=_where(found), link=_shown(found.url)),
                how_long, "Не открывалась",
            ))
        elif changed and result.state == REDIRECT:
            notes.append(t("• {where}: {link} → {final} — ведёт через переадресацию, лучше поставить конечный адрес")
                         .format(where=_where(found), link=_shown(found.url), final=defang(result.final_host)))
        elif changed and result.state == TECHNICAL:
            notes.append(t("• {where}: {link} — ведёт на технический адрес {final}; если у сайта есть свой домен, "
                           "лучше он").format(where=_where(found), link=_shown(found.url),
                                              final=defang(result.final_host)))
    sent = 0
    for text in alerts:
        await notifier.send(bot, config, db, text, Priority.NORMAL, no_preview=True, actions=(callbacks.SECURITY,),
                            monitor=MONITOR_ID)
        sent += 1
    if notes:
        text = "\n".join([t("ℹ️ Ссылки в профилях — можно лучше:"), *notes,
                          t("Поправить можно в самом профиле; я проверю снова через неделю.")])
        await notifier.send(bot, config, db, text, Priority.DIGEST, no_preview=True)
        sent += 1
    await db.set_setting(STATE_KEY, json.dumps(state, ensure_ascii=False))
    await db.set_setting(CHECKED_KEY, now.isoformat())
    return sent


async def run(bot: Bot, config: Config, db: Database) -> int:
    """The weekly check, from the daily job: when it is due and switched on."""
    if not await monitors.is_on(db, config, MONITOR_ID) or not await due(db):
        return 0
    async with aiohttp.ClientSession() as session:
        return await check(bot, config, db, session)

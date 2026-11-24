"""The weekly reputation report: how the owner and their products are found.

Metrics, not incidents (BOT_PRINCIPLES, «Кто за что отвечает»): once a week,
one message with what the connected sources saw, next to the follower growth
the bot already knows — and nothing when there is nothing to say.

    🔎 Репутация за неделю · 15.11–21.11
    🔍 Google: 120 показов, 8 кликов по брендовым запросам (+30 %) · «good pass» 40, «foundyou» 30
    🔍 Яндекс: 15 показов, 2 клика · «foundyou» 10
    🤖 ИИ-ассистенты открывали страницы 343 раза (+351 %) · ChatGPT-User 200, Perplexity-User 100
    👥 Подписчики: 16 860, +120 за неделю

Each source is a monitor of its own (bot/monitors/__init__.py: rep_google,
rep_yandex, rep_ai), on once the owner sent its read-only key in
the chat (🔌 Подключения → 🔎 Репутация) and switched off in /modules. The
keys never reach a screen, a log line or the Sunday backup.

What is not here on purpose: the sites' clicks and impressions as a whole,
indexing, robots, sitemaps, canonical copies — TofsDevOps watches those as
signs of breakage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from types import ModuleType

import aiohttp
from telegram import Bot

from bot import callbacks, monitors, notifier, platforms
from bot.config import Config
from bot.db import Database, parse_utc, utcnow
from bot.i18n import plural, t
from bot.notifier import Priority
from bot.reputation import cloudflare, google, yandex
from bot.reputation.base import Failure, Week

logger = logging.getLogger(__name__)

WORDS_KEY = "rep_brand_words"
SENT_KEY = "rep_sent_at"
EVERY = timedelta(days=7)
DUE_SLACK = timedelta(hours=1)
# Search Console and Webmaster fill a day in two or three days: the week ends
# this many days before today, so both weeks compared are complete.
LAG_DAYS = 3


@dataclass(frozen=True)
class Source:
    monitor: str      # its monitor id, which also names the input step
    label: str        # «Google», as the report and the screens say it
    module: ModuleType
    needs_words: bool  # a search source needs the brand words


SOURCES: tuple[Source, ...] = (
    Source("rep_google", "Google", google, True),
    Source("rep_yandex", "Яндекс", yandex, True),
    Source("rep_ai", "Cloudflare", cloudflare, False),
)
BY_MONITOR = {s.monitor: s for s in SOURCES}


def parse_words(text: str) -> list[str]:
    """«Семён Моргунов, FoundYou, good pass» → the brand words, lower case, no repeats."""
    seen: dict[str, None] = {}
    for part in text.replace("\n", ",").replace(";", ",").split(","):
        word = " ".join(part.split()).lower()
        if 2 <= len(word) <= 60:
            seen.setdefault(word, None)
    return list(seen)[:20]


async def words(db: Database) -> list[str]:
    return parse_words(await db.get_setting(WORDS_KEY) or "")


def window(today: date) -> tuple[date, date, date, date]:
    """(start, end, previous start, previous end): two whole weeks, ending LAG_DAYS ago."""
    end = today - timedelta(days=LAG_DAYS)
    start = end - timedelta(days=6)
    return start, end, start - timedelta(days=7), start - timedelta(days=1)


def _pct(now: int, before: int | None) -> str:
    if not before:
        return ""
    change = round((now - before) / before * 100)
    return f" ({'+' if change >= 0 else '−'}{abs(change)} %)"


def _fmt(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def _quoted(pairs: list[tuple[str, int]]) -> str:
    return ", ".join(f"«{name}» {_fmt(count)}" for name, count in pairs)


def _plain(pairs: list[tuple[str, int]]) -> str:
    return ", ".join(f"{name} {_fmt(count)}" for name, count in pairs)


def search_line(label: str, now: Week, before: Week | None) -> str:
    head = t("🔍 {source}: {shows} {shows_word}, {clicks} {clicks_word} по брендовым запросам{change}").format(
        source=t(label), shows=_fmt(now.total), shows_word=plural(now.total, "показ", "показа", "показов"),
        clicks=_fmt(now.clicks), clicks_word=plural(now.clicks, "клик", "клика", "кликов"),
        change=_pct(now.total, before.total if before else None),
    )
    return head + (f" · {_quoted(now.top())}" if now.by else "")


def ai_line(now: Week, before: Week | None) -> str:
    head = t("🤖 ИИ-ассистенты открывали твои страницы {n} {times}{change}").format(
        n=_fmt(now.total), times=plural(now.total, "раз", "раза", "раз"),
        change=_pct(now.total, before.total if before else None),
    )
    parts = [_plain(now.top())] if now.by else []
    if now.where:
        parts.append(t("чаще всего — {host}").format(host=now.top(1, "where")[0][0]))
    return head + "".join(f" · {p}" for p in parts)



async def followers_line(db: Database, config: Config, today: date) -> str:
    now_total, before_total = 0, 0
    for platform in platforms.enabled(config):
        latest = await db.get_latest(platform.id)
        if latest is None:
            continue
        before = await db.get_on_or_before(platform.id, today - timedelta(days=7), 3)
        now_total += latest["count"]
        before_total += before["count"] if before else latest["count"]
    if not now_total:
        return ""
    delta = now_total - before_total
    return t("👥 Подписчики: {total}, {delta} за неделю").format(
        total=_fmt(now_total), delta=f"{'+' if delta >= 0 else '−'}{_fmt(abs(delta))}")


def reason(code: str, seen: str = "") -> str:
    """Why a source did not answer, in the chat language. seen — for
    'no_sites', the account to add (a service account's e-mail)."""
    from bot import watchdog

    reasons = {
        "key": t("это не тот ключ или он не читается"),
        "no_sites": t("у ключа нет доступа ни к одному сайту"),
        "no_words": t("не заданы брендовые слова"),
        "not_available": t("на этом тарифе API этих данных не отдаёт"),
    }
    if code == "no_sites" and seen:
        return t("у ключа нет доступа ни к одному сайту — добавь {who} в пользователи ресурса").format(who=seen)
    return reasons.get(code) or watchdog.reason(code)


def failure_line(label: str, code: str) -> str:
    return t("⚠️ {source}: не смог получить данные — {reason}").format(source=t(label), reason=reason(code))


async def due(db: Database, now: datetime | None = None) -> bool:
    raw = await db.get_setting(SENT_KEY)
    try:
        last = parse_utc(raw) if raw else None
    except ValueError:
        last = None
    return last is None or (now or utcnow()) - last >= EVERY - DUE_SLACK


async def build(db: Database, config: Config, session: aiohttp.ClientSession, today: date | None = None,
                ) -> tuple[str, dict]:
    """The report's text ('' when there is nothing to say) and what to keep
    for the next one."""
    today = today or utcnow().date()
    start, end, prev_start, prev_end = window(today)
    brand = await words(db)
    lines: list[str] = []
    keep: dict = {}
    said = False
    for source in SOURCES:
        if not await monitors.is_on(db, config, source.monitor):
            continue
        secret = await db.get_setting(monitors.BY_ID[source.monitor].secret) or ""
        try:
            if source.needs_words and not brand:
                raise Failure("no_words")
            now = await source.module.week(session, secret, brand, start, end)
            try:
                before = await source.module.week(session, secret, brand, prev_start, prev_end)
            except Failure:
                before = None     # the previous week out of reach (a short retention): no change said
        except Failure as e:
            lines.append(failure_line(source.label, e.code))
            said = True
            continue
        except (aiohttp.ClientError, TimeoutError) as e:
            lines.append(failure_line(source.label, "timeout" if isinstance(e, TimeoutError) else "connect"))
            said = True
            continue
        if not now.total:
            continue
        said = True
        lines.append(ai_line(now, before) if source.monitor == "rep_ai" else search_line(source.label, now, before))
    if not said:
        return "", keep
    followers = await followers_line(db, config, today)
    head = t("🔎 <b>Репутация за неделю</b> · {start}–{end}").format(
        start=start.strftime("%d.%m"), end=end.strftime("%d.%m"))
    return "\n".join([head, "", *lines, *([followers] if followers else [])]), keep


async def send(bot: Bot, config: Config, db: Database, session: aiohttp.ClientSession | None = None) -> bool:
    """Build and send now; True when a report went out."""
    own = session is None
    session = session or aiohttp.ClientSession()
    try:
        text, keep = await build(db, config, session)
    finally:
        if own:
            await session.close()
    await db.set_setting(SENT_KEY, utcnow().isoformat())
    for key, value in keep.items():
        await db.set_setting(key, value)
    if not text:
        logger.info("Reputation report: nothing to say this week")
        return False
    return await notifier.send(bot, config, db, text, Priority.DIGEST, actions=(callbacks.REPUTATION,))


async def run(bot: Bot, config: Config, db: Database) -> bool:
    """From the daily job: once a week, when any source is on."""
    if not any([await monitors.is_on(db, config, s.monitor) for s in SOURCES]) or not await due(db):
        return False
    return await send(bot, config, db)


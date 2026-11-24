"""What the bot sends out is watched too (BOT_PRINCIPLES §4).

Three deliveries leave the bot on their own: the subscriber counts pushed to
the owner's site (SITE_INGEST_URL), the status lines sent to TofsDevOps
(bot/tofs_status.py — the daily mark and the half-hourly refresh) and the
daily mark at any other watchdog (healthchecks.io). Each one that fails was
only a log line, and a log line is not a notification: a changed token froze
the counts on the site, and nobody would have known.

Every attempt is recorded here. A day without one that landed is one 🟠 that
says where and why; the first one that lands after it is one ✅ with how
long it did not. ⚙️ Настройки shows when each last landed. The state is kept
while the monitor is off, so switching it on does not alert a stale failure.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from telegram import Bot

from bot import callbacks, humanize, monitors, notifier
from bot.config import Config
from bot.db import Database, parse_utc, utcnow
from bot.i18n import t
from bot.notifier import Priority

logger = logging.getLogger(__name__)

MONITOR_ID = "outgoing"
# A day, less the run's own jitter: a daily push that failed twice in a row,
# or a day of half-hourly refreshes.
ALERT_AFTER = timedelta(hours=23)

SITE, TOFS, WATCHDOG = "site", "tofs", "watchdog"


@dataclass(frozen=True)
class Target:
    id: str
    what: str            # Russian, translated where shown: what does not arrive
    down: str            # the headline: «{where} не принимает …»
    back: str            # the recovery's headline
    verb: str            # how the recovery says it lasted
    explanation: str     # humanize.EXPLANATIONS key
    screen: str          # where it is fixed


TARGETS: dict[str, Target] = {
    SITE: Target(
        SITE, "Цифры на сайт", "🟠 {where} не принимает цифры подписчиков уже {how_long}: {reason}",
        "✅ {where} снова принимает цифры подписчиков", "Не принимал", "push_site", callbacks.SETTINGS,
    ),
    TOFS: Target(
        TOFS, "Строки в TofsDevOps", "🟠 TofsDevOps не принимает строки состояния уже {how_long}: {reason}",
        "✅ TofsDevOps снова принимает строки состояния", "Не принимал", "push_tofs", callbacks.WATCHDOG,
    ),
    WATCHDOG: Target(
        WATCHDOG, "Отметки сторожу", "🟠 Сторож {where} не принимает отметки уже {how_long}: {reason}",
        "✅ Сторож {where} снова принимает отметки", "Не принимал", "push_watchdog", callbacks.WATCHDOG,
    ),
}


def _key(target: str) -> str:
    return f"outgoing_{target}"


def host(url: str | None) -> str:
    """Where a delivery goes, as a screen may say it: the host, never the
    path or the query (a token may sit there)."""
    return (urlsplit(url or "").hostname or "").lower()


def reason(code: str) -> str:
    """Why a delivery did not land, in the chat language — the watchdog's words."""
    from bot import watchdog  # watchdog imports tofs_status, which imports the monitors

    return watchdog.reason(code)


def error_code(error: BaseException) -> str:
    """An exception of a delivery as a code reason() reads; never its text,
    which may carry the address."""
    import aiohttp

    if isinstance(error, TimeoutError):
        return "timeout"
    if isinstance(error, aiohttp.ClientConnectorError):
        return "connect"
    return "error"


async def state(db: Database, target: str) -> dict:
    try:
        data = json.loads(await db.get_setting(_key(target)) or "{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _when(raw: str | None) -> datetime | None:
    try:
        return parse_utc(raw) if raw else None
    except ValueError:
        return None


async def record(bot: Bot | None, config: Config, db: Database, target: str, error: str | None, where: str = "") -> None:
    """One delivery to target: error None when it landed, else its code
    ('rejected:401', 'timeout', …); where — the host it went to. Says the
    day without a delivery once, and its end once."""
    spec = TARGETS[target]
    now = utcnow()
    current = await state(db, target)
    on = await monitors.is_on(db, config, MONITOR_ID)
    if error is None:
        if current.get("alerted") and on and bot is not None:
            since = _when(current.get("fail_since"))
            how_long = humanize.lasted(since, _when(current.get("fail_last")), now, await notifier.owner_tz(db, config))
            try:
                await notifier.send(
                    bot, config, db, humanize.recovery(t(spec.back).format(where=where), how_long, spec.verb),
                    Priority.NORMAL, actions=(spec.screen,),
                )
            except Exception:
                logger.exception("Outgoing recovery notice failed")
        await db.set_setting(_key(target), json.dumps({"ok_at": now.isoformat(), "where": where}))
        return
    since = _when(current.get("fail_since")) or now
    current.update({"fail_since": since.isoformat(), "fail_last": now.isoformat(), "error": error, "where": where})
    if not current.get("alerted") and on and bot is not None and now - since >= ALERT_AFTER:
        last_ok = _when(current.get("ok_at"))
        tz = await notifier.owner_tz(db, config)
        head = t(spec.down).format(
            where=where, how_long=humanize.fmt_duration((now - since).total_seconds() / 60), reason=reason(error),
        )
        details = [
            t("последняя удачная {when}").format(when=last_ok.astimezone(tz).strftime("%d.%m %H:%M"))
            if last_ok else t("удачных ещё не было"),
            error,
        ]
        try:
            current["alerted"] = await notifier.send(
                bot, config, db, humanize.alert(head, spec.explanation, *details), Priority.NORMAL,
                actions=(spec.screen,), monitor=MONITOR_ID,
            )
        except Exception:
            logger.exception("Outgoing alert send failed — will try with the next delivery")
    await db.set_setting(_key(target), json.dumps(current))


def _local(at: datetime, tz) -> str:
    local = at.astimezone(tz)
    if local.date() == utcnow().astimezone(tz).date():
        return t("сегодня {time}").format(time=local.strftime("%H:%M"))
    return local.strftime("%d.%m %H:%M")


async def line(db: Database, config: Config, target: str, where: str = "") -> str:
    """One line for ⚙️ Настройки: when it last landed, or since when it does not."""
    spec = TARGETS[target]
    current = await state(db, target)
    tz = await notifier.owner_tz(db, config)
    what = t(spec.what) + (f" ({where})" if where else "")
    ok_at, since = _when(current.get("ok_at")), _when(current.get("fail_since"))
    if since is not None:
        icon = monitors.WARNING if utcnow() - since >= ALERT_AFTER else monitors.UNCHECKED
        last = t(", последняя удачная {when}").format(when=_local(ok_at, tz)) if ok_at else ""
        return t("{icon} {what}: не доходят с {since} — {reason}{last}").format(
            icon=icon, what=what, since=_local(since, tz), reason=reason(current.get("error") or "error"), last=last,
        )
    if ok_at is not None:
        return t("{icon} {what}: последняя удачная {when}").format(icon=monitors.OK, what=what, when=_local(ok_at, tz))
    return t("{icon} {what}: ещё не отправлялись").format(icon=monitors.PENDING, what=what)

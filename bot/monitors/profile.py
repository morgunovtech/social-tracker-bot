"""Profile integrity: alert when a watched public profile field changes.

A hijacked account is usually renamed, gets a scam link in its description,
a new admin or loses its videos within minutes, long before the follower
count moves. The first look at a profile only stores the baseline.

The changes of one check are one alert in the one shape (bot/humanize.py),
the worst line first; «unreadable» is alerted once, and «readable again»
says how long it was not, from the first failed check of the series. Each
change also goes to the security log, as its line before translation.
"""

from __future__ import annotations

import json
import logging
import math
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import aiohttp
from telegram import Bot

from bot import humanize, notifier, platforms
from bot.callbacks import SECURITY
from bot.config import Config
from bot.db import Database, parse_utc, utcnow
from bot.i18n import plural, t
from bot.monitors import CRITICAL, HIJACK, WARNING, defang
from bot.notifier import Priority
from bot.platforms.base import ADMINS, COUNT, IMAGE, STATE, TEXT, Context, Platform

logger = logging.getLogger(__name__)

CHECK_INTERVAL = timedelta(minutes=30)
# Consecutive failed fetches before "profile unreachable" is alerted (~1.5 h).
UNREACHABLE_AFTER = 3
# A drop in posts/videos is alerted when it reaches both bounds.
COUNT_DROP_MIN_ABS = 3
COUNT_DROP_MIN_PCT = 10.0
SNIPPET_LEN = 120
# A description stuffed with links must not push the alert past Telegram's
# 4096-character limit: the send would fail and the alert be lost.
MAX_LINKS = 5
MESSAGE_LIMIT = 4000
_UTC = ZoneInfo("UTC")

_LINK = re.compile(r"(?:https?://|www\.|t\.me/)[^\s<>\"«»]+", re.IGNORECASE)


def _quote(text: str) -> humanize.Phrase | str:
    """A text field's value as an alert quotes it: someone's text, shortened
    and defanged — or the bot's own «(пусто)», translated where it is shown."""
    text = " ".join(text.split())
    if not text:
        return humanize.phrase("(пусто)")
    return defang(text if len(text) <= SNIPPET_LEN else text[: SNIPPET_LEN - 1] + "…")


def _admin_changes(label: str, before: str, after: str) -> list[humanize.Phrase]:
    old = {a["id"]: a for a in json.loads(before)}
    new = {a["id"]: a for a in json.loads(after)}
    hijack = humanize.phrase(HIJACK)
    # A display name is other people's text: a domain in it must not be a link.
    found = [
        humanize.phrase("🔴 {label}: {hijack} — новый админ {name}", label=label, hijack=hijack,
                        name=defang(new[uid]["name"]))
        for uid in new.keys() - old.keys()
    ]
    found += [
        humanize.phrase("🟠 {label}: админ удалён — {name}", label=label, name=defang(old[uid]["name"]))
        for uid in old.keys() - new.keys()
    ]
    owner_before = next((a for a in old.values() if a["status"] == "creator"), None)
    owner_after = next((a for a in new.values() if a["status"] == "creator"), None)
    if owner_before and owner_after and owner_before["id"] != owner_after["id"]:
        found.append(
            humanize.phrase("🔴 {label}: {hijack} — сменился владелец: {before} → {after}", label=label,
                            hijack=hijack, before=defang(owner_before["name"]), after=defang(owner_after["name"]))
        )
    return found


def changes(platform: Platform, old: dict[str, str], new: dict[str, str]) -> list[tuple[humanize.Phrase, str]]:
    """The watched fields that changed: (the line before translation — what
    the security log keeps, bot/security_log.py —, what the alert adds under
    it: the new links of a text field). A field missing on either side (new
    to the connector, or not returned) is not a change."""
    found: list[tuple[humanize.Phrase, str]] = []
    for name, (label, kind) in platform.profile_fields.items():
        before, after = old.get(name), new.get(name)
        if before is None or after is None or before == after:
            continue
        field = humanize.phrase(label)
        if kind == TEXT:
            # A link that wasn't there before is the classic hijack payload.
            added = sorted(set(_LINK.findall(after)) - set(_LINK.findall(before)))
            quoted = {"platform": platform.label, "field": field, "before": _quote(before), "after": _quote(after)}
            if not added:
                found.append((humanize.phrase("{icon} {platform}: {field} — «{before}» → «{after}»",
                                              icon=WARNING, **quoted), ""))
                continue
            more = t(" и ещё {n}").format(n=len(added) - MAX_LINKS) if len(added) > MAX_LINKS else ""
            links = "\n    " + t("новые ссылки: {links}{more}").format(
                links=defang(", ".join(added[:MAX_LINKS])), more=more
            )
            found.append((humanize.phrase("{icon} {platform}: {hijack} — {field}: «{before}» → «{after}»",
                                          icon=CRITICAL, hijack=humanize.phrase(HIJACK), **quoted), links))
        elif kind == STATE:
            found.append((humanize.phrase("{icon} {platform}: {field} — «{before}» → «{after}»", icon=WARNING,
                                          platform=platform.label, field=field, before=humanize.phrase(before),
                                          after=humanize.phrase(after)), ""))
        elif kind == IMAGE:
            found.append((humanize.phrase("🟠 {platform}: новая {field}", platform=platform.label, field=field), ""))
        elif kind == ADMINS:
            found += [(line, "") for line in _admin_changes(platform.label, before, after)]
        elif kind == COUNT:
            try:
                was, now = int(before), int(after)
            except ValueError:
                continue
            drop = was - now
            if drop >= COUNT_DROP_MIN_ABS and drop >= math.ceil(was * COUNT_DROP_MIN_PCT / 100):
                found.append((humanize.phrase(
                    "🔴 {platform}: {hijack} — {field}: было {was}, стало {now} (−{drop})", platform=platform.label,
                    hijack=humanize.phrase(HIJACK), field=field, was=was, now=now, drop=drop,
                ), ""))
    return found


def diff(platform: Platform, old: dict[str, str], new: dict[str, str]) -> list[str]:
    """The alert lines for the watched fields that changed, in the chat language."""
    return [humanize.render(line) + more for line, more in changes(platform, old, new)]


def _reachability(
    platform: Platform, fails: int, reachable: bool,
    since: datetime | None = None, last: datetime | None = None, now: datetime | None = None,
    tz: ZoneInfo = _UTC,
) -> tuple[list[str], int]:
    """(messages, new count of consecutive failed fetches). since and last —
    the first and the latest failed check of the series, for how long the
    profile was unreadable once it is back; tz — the owner's zone."""
    if reachable:
        if fails >= UNREACHABLE_AFTER:
            head = t("✅ {label}: профиль снова доступен").format(label=platform.label)
            how_long = humanize.lasted(since, last, now or utcnow(), tz, CHECK_INTERVAL)
            return [humanize.recovery(head, how_long, "Не читался")], 0
        return [], 0
    fails += 1
    if fails == UNREACHABLE_AFTER:
        head = t(
            "🔴 {label}: профиль не читается {n} {checks} подряд — "
            "канал удалён или скрыт, или у бота отобрали права?"
        ).format(label=platform.label, n=fails, checks=plural(fails, "проверку", "проверки", "проверок"))
        return [humanize.alert(head, "profile_unreachable", _every())], fails
    return [], fails


def _every() -> str:
    return t("проверка профиля раз в {minutes} мин").format(minutes=int(CHECK_INTERVAL.total_seconds() // 60))


def change_alert(changes: list[str]) -> str:
    """The changes of one check as one alert: the hijack signs (🔴) first."""
    ordered = sorted(changes, key=lambda line: not line.startswith(CRITICAL))
    key = "profile_hijack" if ordered[0].startswith(CRITICAL) else "profile_change"
    return humanize.alert(ordered, key, _every())


def _when(raw: str | None) -> datetime | None:
    try:
        return parse_utc(raw) if raw else None
    except ValueError:
        return None


async def _send(bot: Bot, config: Config, db: Database, text: str, priority: Priority) -> bool:
    if len(text) > MESSAGE_LIMIT:
        text = text[: MESSAGE_LIMIT - 1] + "…"
    try:
        # A 🔴 line rings through quiet hours and /mute; 🟠 changes wait for the digest.
        await notifier.send(bot, config, db, text, priority, no_preview=True, actions=(SECURITY,), monitor="profile")
        return True
    except Exception:
        logger.exception("Profile alert send failed — will retry on the next check")
        return False


async def check(bot: Bot, config: Config, db: Database, session: aiohttp.ClientSession) -> int:
    """Fetch every watched profile and alert on changes, one message per
    platform; returns the number of messages sent.

    The new baseline, the failure counter and the log entries are saved only
    after the alert went out: a failed send leaves everything as it was, so
    the next check finds the same change and retries.
    """
    sent = 0
    tz = await notifier.owner_tz(db, config)
    for platform in platforms.enabled(config):
        if not platform.profile_fields:
            continue
        current = await platform.fetch_profile(Context(bot, session, config, db))
        fail_key, key = f"profile_fail_{platform.id}", f"profile_{platform.id}"
        since_key, last_key = f"profile_fail_since_{platform.id}", f"profile_fail_last_{platform.id}"
        fails = int(await db.get_setting(fail_key) or "0")
        stored = await db.get_setting(key)
        baseline = json.loads(stored) if stored is not None else None
        now = utcnow()

        parts, new_fails = _reachability(
            platform, fails, current is not None,
            _when(await db.get_setting(since_key)), _when(await db.get_setting(last_key)), now, tz,
        )
        # «Unreadable» rings, and so does «readable again» after it (BOT_PRINCIPLES §1).
        priority = Priority.CRITICAL if parts else Priority.NORMAL
        found = changes(platform, baseline, current) if current is not None and baseline is not None else []
        lines = [humanize.render(line) + more for line, more in found]
        if lines:
            parts.append(change_alert(lines))
            if notifier.priority_for(lines) is Priority.CRITICAL:
                priority = Priority.CRITICAL
        if parts:
            if not await _send(bot, config, db, "\n\n".join(parts), priority):
                continue
            sent += 1

        if current is None:
            if fails == 0:
                await db.set_setting(since_key, now.isoformat())
            await db.set_setting(last_key, now.isoformat())
        if new_fails != fails:
            await db.set_setting(fail_key, str(new_fails))
        if current is not None:
            # Merged: a field missing from this fetch keeps its last known value.
            merged = {**(baseline or {}), **current}
            if merged != baseline:
                await db.set_setting(key, json.dumps(merged, ensure_ascii=False))
        # The log keeps the line before translation: 🛡 Безопасность shows it in
        # the chat language of the day it is read.
        stamp = utcnow().isoformat()
        for i, (line, _) in enumerate(found):
            await db.add_event(f"profile:{platform.id}:{stamp}:{i}", platform.label, "profile", humanize.dump(line))
    return sent

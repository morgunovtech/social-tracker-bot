"""Profile integrity: alert when a watched public profile field changes.

A hijacked account is usually renamed, gets a scam link in its description,
a new admin or loses its videos within minutes, long before the follower
count moves. The first look at a profile only stores the baseline.
"""

from __future__ import annotations

import json
import logging
import math
import re
from datetime import timedelta

import aiohttp
from telegram import Bot

from bot import notifier, platforms
from bot.callbacks import SECURITY
from bot.config import Config
from bot.db import Database, utcnow
from bot.i18n import plural, t
from bot.monitors import CRITICAL, HIJACK, WARNING, defang
from bot.platforms.base import ADMINS, COUNT, IMAGE, TEXT, Context, Platform

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

ADVICE = (
    "Если это сделал не ты — смени пароль, заверши чужие сеансы и проверь список админов. "
    "Если ты — всё в порядке."
)

_LINK = re.compile(r"(?:https?://|www\.|t\.me/)[^\s<>\"«»]+", re.IGNORECASE)


def _snippet(text: str) -> str:
    text = " ".join(text.split())
    if not text:
        return t("(пусто)")
    return defang(text if len(text) <= SNIPPET_LEN else text[: SNIPPET_LEN - 1] + "…")


def _admin_lines(label: str, before: str, after: str) -> list[str]:
    old = {a["id"]: a for a in json.loads(before)}
    new = {a["id"]: a for a in json.loads(after)}
    # A display name is other people's text: a domain in it must not be a link.
    lines = [
        t("🔴 {label}: {hijack} — новый админ {name}").format(label=label, hijack=t(HIJACK), name=defang(new[uid]["name"]))
        for uid in new.keys() - old.keys()
    ]
    lines += [
        t("🟠 {label}: админ удалён — {name}").format(label=label, name=defang(old[uid]["name"]))
        for uid in old.keys() - new.keys()
    ]
    owner_before = next((a for a in old.values() if a["status"] == "creator"), None)
    owner_after = next((a for a in new.values() if a["status"] == "creator"), None)
    if owner_before and owner_after and owner_before["id"] != owner_after["id"]:
        lines.append(
            t("🔴 {label}: {hijack} — сменился владелец: {before} → {after}").format(
                label=label, hijack=t(HIJACK), before=defang(owner_before["name"]), after=defang(owner_after["name"])
            )
        )
    return lines


def diff(platform: Platform, old: dict[str, str], new: dict[str, str]) -> list[str]:
    """Alert lines for the watched fields that changed. A field missing on
    either side (new to the connector, or not returned) is not a change."""
    lines: list[str] = []
    for name, (label, kind) in platform.profile_fields.items():
        before, after = old.get(name), new.get(name)
        if before is None or after is None or before == after:
            continue
        if kind == TEXT:
            # A link that wasn't there before is the classic hijack payload.
            added = sorted(set(_LINK.findall(after)) - set(_LINK.findall(before)))
            line = (
                t("{icon} {platform}: {hijack} — {field}: «{before}» → «{after}»") if added
                else t("{icon} {platform}: {field} — «{before}» → «{after}»")
            ).format(
                icon=CRITICAL if added else WARNING,
                platform=platform.label,
                hijack=t(HIJACK),
                field=t(label),
                before=_snippet(before),
                after=_snippet(after),
            )
            if added:
                more = t(" и ещё {n}").format(n=len(added) - MAX_LINKS) if len(added) > MAX_LINKS else ""
                line += "\n    " + t("новые ссылки: {links}{more}").format(
                    links=defang(", ".join(added[:MAX_LINKS])), more=more
                )
            lines.append(line)
        elif kind == IMAGE:
            lines.append(t("🟠 {platform}: новая {field}").format(platform=platform.label, field=t(label)))
        elif kind == ADMINS:
            lines += _admin_lines(platform.label, before, after)
        elif kind == COUNT:
            try:
                was, now = int(before), int(after)
            except ValueError:
                continue
            drop = was - now
            if drop >= COUNT_DROP_MIN_ABS and drop >= math.ceil(was * COUNT_DROP_MIN_PCT / 100):
                lines.append(
                    t("🔴 {platform}: {hijack} — {field}: было {was}, стало {now} (−{drop})").format(
                        platform=platform.label, hijack=t(HIJACK), field=t(label), was=was, now=now, drop=drop
                    )
                )
    return lines


def _reachability(platform: Platform, fails: int, reachable: bool) -> tuple[list[str], int]:
    """(alert lines, new count of consecutive failed fetches)."""
    if reachable:
        if fails >= UNREACHABLE_AFTER:
            return [t("✅ {label}: профиль снова доступен").format(label=platform.label)], 0
        return [], 0
    fails += 1
    if fails == UNREACHABLE_AFTER:
        return [
            t(
                "🔴 {label}: профиль не читается {n} {checks} подряд — "
                "канал удалён или скрыт, или у бота отобрали права?"
            ).format(label=platform.label, n=fails, checks=plural(fails, "проверку", "проверки", "проверок"))
        ], fails
    return [], fails


async def _send(bot: Bot, config: Config, db: Database, lines: list[str], changed: bool) -> bool:
    """changed: some lines are changes of the profile — they get the advice;
    «unreadable» and «readable again» alone do not."""
    text = t("🛡 Профиль") + "\n\n" + "\n".join(lines)
    if changed:
        text += f"\n\n{t(ADVICE)}"
    if len(text) > MESSAGE_LIMIT:
        text = text[: MESSAGE_LIMIT - 1] + "…"
    try:
        # A 🔴 line rings through quiet hours and /mute; 🟠 changes wait for the digest.
        await notifier.send(
            bot, config, db, text, notifier.priority_for(lines), no_preview=True, actions=(SECURITY,), monitor="profile"
        )
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
    for platform in platforms.enabled(config):
        if not platform.profile_fields:
            continue
        current = await platform.fetch_profile(Context(bot, session, config, db))
        fail_key, key = f"profile_fail_{platform.id}", f"profile_{platform.id}"
        fails = int(await db.get_setting(fail_key) or "0")
        stored = await db.get_setting(key)
        baseline = json.loads(stored) if stored is not None else None

        lines, new_fails = _reachability(platform, fails, current is not None)
        changes = diff(platform, baseline, current) if current is not None and baseline is not None else []
        lines += changes
        if lines:
            if not await _send(bot, config, db, lines, changed=bool(changes)):
                continue
            sent += 1

        if new_fails != fails:
            await db.set_setting(fail_key, str(new_fails))
        if current is not None:
            # Merged: a field missing from this fetch keeps its last known value.
            merged = {**(baseline or {}), **current}
            if merged != baseline:
                await db.set_setting(key, json.dumps(merged, ensure_ascii=False))
        stamp = utcnow().isoformat()
        for i, line in enumerate(changes):
            await db.add_event(f"profile:{platform.id}:{stamp}:{i}", platform.label, "profile", line)
    return sent

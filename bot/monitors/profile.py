"""Profile integrity: alert when a watched public profile field changes.

A hijacked account is usually renamed, gets a scam link in its description,
a new admin or loses its videos within minutes, long before the follower
count moves. The first look at a profile only stores the baseline.
"""

from __future__ import annotations

import json
import math
import re
from datetime import timedelta

import aiohttp
from telegram import Bot

from bot import platforms
from bot.config import Config
from bot.db import Database, utcnow
from bot.platforms.base import ADMINS, COUNT, IMAGE, TEXT, Context, Platform

CHECK_INTERVAL = timedelta(minutes=30)
# Consecutive failed fetches before "profile unreachable" is alerted (~1.5 h).
UNREACHABLE_AFTER = 3
# A drop in posts/videos is alerted when it reaches both bounds.
COUNT_DROP_MIN_ABS = 3
COUNT_DROP_MIN_PCT = 10.0
SNIPPET_LEN = 120

ADVICE = (
    "Если это сделал не ты — смени пароль, заверши чужие сеансы и проверь список админов. "
    "Если ты — всё в порядке."
)

_LINK = re.compile(r"(?:https?://|www\.|t\.me/)[^\s<>\"«»]+", re.IGNORECASE)


def _snippet(text: str) -> str:
    text = " ".join(text.split())
    if not text:
        return "(пусто)"
    return text if len(text) <= SNIPPET_LEN else text[: SNIPPET_LEN - 1] + "…"


def _admin_lines(label: str, before: str, after: str) -> list[str]:
    old = {a["id"]: a for a in json.loads(before)}
    new = {a["id"]: a for a in json.loads(after)}
    lines = [f"🚨 {label}: новый админ — {new[uid]['name']}" for uid in new.keys() - old.keys()]
    lines += [f"🟠 {label}: админ удалён — {old[uid]['name']}" for uid in old.keys() - new.keys()]
    owner_before = next((a for a in old.values() if a["status"] == "creator"), None)
    owner_after = next((a for a in new.values() if a["status"] == "creator"), None)
    if owner_before and owner_after and owner_before["id"] != owner_after["id"]:
        lines.append(f"🚨 {label}: сменился владелец — {owner_before['name']} → {owner_after['name']}")
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
            line = f"{'🚨' if added else '🟠'} {platform.label}: {label} — «{_snippet(before)}» → «{_snippet(after)}»"
            if added:
                line += "\n    новые ссылки: " + ", ".join(added)
            lines.append(line)
        elif kind == IMAGE:
            lines.append(f"🟠 {platform.label}: новая {label}")
        elif kind == ADMINS:
            lines += _admin_lines(platform.label, before, after)
        elif kind == COUNT:
            try:
                was, now = int(before), int(after)
            except ValueError:
                continue
            drop = was - now
            if drop >= COUNT_DROP_MIN_ABS and drop >= math.ceil(was * COUNT_DROP_MIN_PCT / 100):
                lines.append(f"🚨 {platform.label}: {label} — было {was}, стало {now} (−{drop})")
    return lines


async def _track_reachability(db: Database, platform: Platform, reachable: bool) -> list[str]:
    key = f"profile_fail_{platform.id}"
    fails = int(await db.get_setting(key) or "0")
    if reachable:
        if fails:
            await db.set_setting(key, "0")
        return [f"✅ {platform.label}: профиль снова доступен"] if fails >= UNREACHABLE_AFTER else []
    fails += 1
    await db.set_setting(key, str(fails))
    if fails == UNREACHABLE_AFTER:
        return [
            f"🔴 {platform.label}: профиль не читается {fails} проверки подряд — "
            f"канал удалён или скрыт, или у бота отобрали права?"
        ]
    return []


async def check(bot: Bot, config: Config, db: Database, session: aiohttp.ClientSession) -> list[str]:
    """Fetch every watched profile, log and return alert lines, keep the baseline."""
    lines: list[str] = []
    for platform in platforms.enabled(config):
        if not platform.profile_fields:
            continue
        current = await platform.fetch_profile(Context(bot, session, config, db))
        lines += await _track_reachability(db, platform, current is not None)
        if current is None:
            continue

        key = f"profile_{platform.id}"
        stored = await db.get_setting(key)
        if stored is not None:
            changes = diff(platform, json.loads(stored), current)
            stamp = utcnow().isoformat()
            for i, line in enumerate(changes):
                await db.add_event(f"profile:{platform.id}:{stamp}:{i}", platform.label, "profile", line)
            lines += changes
        if stored is None or json.loads(stored) != current:
            await db.set_setting(key, json.dumps(current, ensure_ascii=False))
    return lines

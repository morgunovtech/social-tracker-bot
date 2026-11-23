"""The one door every notification to the owner goes through.

Three priorities decide what happens with quiet hours and /mute; nothing
else in the codebase reasons about them:

    CRITICAL  rings; bypasses quiet hours and mute
    NORMAL    silent delivery (disable_notification); deferred to the queue
              during quiet hours or while muted, flushed later as one digest
    DIGEST    silent; deferred only by an explicit mute (the weekly report IS
              the digest, so it goes through quiet hours)

The icon in the first character of a line and the way the message arrives
agree (priority_for): 🚨 and 🔴 ring, everything else is silent. Which
message gets which priority:

    CRITICAL  🛡 profile alerts with a 🚨 line — a new admin or owner, a
              link in the description, a drop in videos or posts — or a 🔴
              one (the profile stopped being readable: deleted, hidden, or
              the bot lost its rights); security emails of a 🚨 kind — a new
              sign-in, a changed or reset password, a changed email or 2FA.
    NORMAL    🛡 profile alerts with only 🟠 lines (a new title, description
              or avatar, an admin removed) and ✅ recoveries; 🟠 security
              emails (a login code, a generic alert), 📨 unrecognised mail
              and Gmail's forwarding confirmation; collection alerts —
              🟠 follower drop, 🟠 bot inflow, 🎯 milestone, 🟠 expired cookie
              or rejected token, ⚠️ missing token, 🟠 failure streak; the
              mail worker unreachable and back; 🟠 a deploy that failed;
              «🔄 Бот обновился».
    DIGEST    the weekly report and its chart, the «без изменений» one-liner,
              the hygiene reminder, the monthly digest, the weekly backup,
              the weekly OSV / Dependabot notice.

Replies to the owner's own actions (a tap, a command, the error notice after
one) are not notifications: they answer right away, whatever the hour.

Files (the chart, the backup) are sent silently and never deferred: a digest
cannot hold them. The scheduler skips the chart while the report itself is
held; the «🖼 График» button has it any time.

send() returns True when the message was delivered or queued and lets a
Telegram error propagate, so the callers that retry on failure (profile,
mail) keep working; while muted or in quiet hours a NORMAL message is queued,
and deferred() tells a caller in advance whether a priority would wait.
flush_queue() runs every minute from the scheduler and right after /unmute:
when the silence is over it delivers the queue as one numbered digest with
the time of each item in the owner's zone; an item with buttons, or one too
long for the digest, goes alone, with its time above.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from enum import Enum
from zoneinfo import ZoneInfo

from telegram import Bot, InlineKeyboardMarkup

from bot.config import Config
from bot.db import Database, parse_utc, utcnow
from bot.i18n import t
from bot.monitors import NO_PREVIEW

logger = logging.getLogger(__name__)

QUIET_HOURS_KEY = "quiet_hours"      # "23-8" or absent = off
MUTE_UNTIL_KEY = "mute_until"        # ISO UTC deadline
# What the screen offers is what a button may set.
QUIET_PRESETS = ("23-8", "0-9")
MUTE_DEFAULT = timedelta(hours=8)
MUTE_MAX = timedelta(days=7)
# Telegram's limit is 4096; the digest keeps a margin for the header and numbering.
SAFE_LIMIT = 4000


class Priority(Enum):
    CRITICAL = "critical"
    NORMAL = "normal"
    DIGEST = "digest"


def priority_for(lines: list[str] | str) -> Priority:
    """The delivery class of an alert by its icons: a 🚨 or 🔴 line rings."""
    text = "\n".join(lines) if isinstance(lines, list) else lines
    for line in text.splitlines():
        if line.startswith(("🚨", "🔴")):
            return Priority.CRITICAL
    return Priority.NORMAL


# ── Quiet hours ───────────────────────────────────────────────────────────────

def parse_quiet_hours(raw: str | None) -> tuple[int, int] | None:
    """'23-8' → (23, 8); None for 'off', empty or malformed values."""
    if not raw or raw == "off" or "-" not in raw:
        return None
    start, _, end = raw.partition("-")
    try:
        start_h, end_h = int(start), int(end)
    except ValueError:
        return None
    if 0 <= start_h <= 23 and 0 <= end_h <= 23 and start_h != end_h:
        return (start_h, end_h)
    return None


def quiet_hours_pretty(hours: tuple[int, int]) -> str:
    return f"{hours[0]:02d}:00–{hours[1]:02d}:00"


async def quiet_hours(db: Database) -> tuple[int, int] | None:
    return parse_quiet_hours(await db.get_setting(QUIET_HOURS_KEY))


async def set_quiet_hours(db: Database, raw: str | None) -> None:
    """raw: a preset such as '23-8', or None to switch quiet hours off."""
    await db.set_setting(QUIET_HOURS_KEY, raw if raw else "off")


async def _tz(db: Database, config: Config) -> ZoneInfo:
    # The scheduler imports this module for sending; the zone is read at call time.
    from bot.scheduler import get_report_tz

    return await get_report_tz(db, config)


def _within(hours: tuple[int, int], hour: int) -> bool:
    start, end = hours
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


async def in_quiet_hours(db: Database, config: Config, now: datetime | None = None) -> bool:
    """True inside the configured quiet hours, told in the owner's zone."""
    hours = await quiet_hours(db)
    if hours is None:
        return False
    local = (now or utcnow()).astimezone(await _tz(db, config))
    return _within(hours, local.hour)


# ── Mute ──────────────────────────────────────────────────────────────────────

def parse_duration(arg: str | None) -> timedelta | None:
    """'1h', '8h', '30m', '1d', '45' (minutes) → timedelta; None if unparseable."""
    arg = (arg or "").strip().lower()
    if not arg:
        return None
    units = {"m": 60, "h": 3600, "d": 86400}
    if arg[-1] in units:
        try:
            num = int(arg[:-1])
        except ValueError:
            return None
        seconds = num * units[arg[-1]]
    else:
        try:
            seconds = int(arg) * 60
        except ValueError:
            return None
    # «/mute 99999999999d» must not crash timedelta: a year is the most anything here could mean.
    return timedelta(seconds=seconds) if 0 < seconds <= 366 * 86400 else None


async def mute_until(db: Database) -> datetime | None:
    """Aware UTC deadline while muted, else None."""
    raw = await db.get_setting(MUTE_UNTIL_KEY)
    if not raw:
        return None
    try:
        deadline = parse_utc(raw)
    except ValueError:
        return None
    return deadline if deadline > utcnow() else None


async def set_mute(db: Database, duration: timedelta | None) -> datetime | None:
    """Mute for `duration` (None = unmute). Returns the deadline."""
    if duration is None:
        await db.set_setting(MUTE_UNTIL_KEY, "")
        return None
    deadline = utcnow() + duration
    await db.set_setting(MUTE_UNTIL_KEY, deadline.isoformat())
    return deadline


async def mute_until_local(db: Database, config: Config) -> str | None:
    """The mute deadline as the owner reads it: '08:00', or '25.11 08:00' when it is far."""
    deadline = await mute_until(db)
    if deadline is None:
        return None
    fmt = "%H:%M" if deadline - utcnow() < timedelta(hours=20) else "%d.%m %H:%M"
    return deadline.astimezone(await _tz(db, config)).strftime(fmt)


async def silence_status(db: Database, config: Config) -> str | None:
    """The line the home and settings screens show while something is held
    back: «🔕 Тишина до 08:00» for a mute, «🌙 Тихие часы до 08:00» otherwise."""
    until = await mute_until_local(db, config)
    if until:
        return t("🔕 Тишина до {until}").format(until=until)
    if await in_quiet_hours(db, config):
        hours = await quiet_hours(db)
        return t("🌙 Тихие часы до {end:02d}:00").format(end=hours[1])
    return None


def what_rings_through() -> str:
    """What passes quiet hours and /mute — exactly what send() lets through."""
    return t(
        "🚨 и 🔴 — похоже на взлом, новый вход, смена пароля, пропавший профиль — придут сразу, со звуком. "
        "Остальное пришлю сводкой, когда тишина закончится."
    )


# ── Sending ───────────────────────────────────────────────────────────────────

async def deferred(db: Database, config: Config, priority: Priority) -> bool:
    """Would a message of this priority wait right now?"""
    if priority is Priority.CRITICAL:
        return False
    if await mute_until(db) is not None:
        return True
    return priority is Priority.NORMAL and await in_quiet_hours(db, config)


async def send(
    bot: Bot,
    config: Config,
    db: Database,
    text: str,
    priority: Priority = Priority.NORMAL,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    no_preview: bool = False,
) -> bool:
    """Deliver now, silently unless CRITICAL, or queue for the digest.
    True when delivered or queued; a Telegram error propagates. Before the
    first /start there is nobody to write to: False, and nothing is queued."""
    if config.admin_chat_id is None:
        logger.info("No owner yet — not sent: %s", text[:60])
        return False
    if await deferred(db, config, priority):
        await db.queue_notification(
            text, reply_markup.to_json() if reply_markup else None, utcnow().strftime("%Y-%m-%d %H:%M:%S")
        )
        logger.info("Queued (quiet hours / mute): %s", text[:60])
        return True
    await bot.send_message(
        chat_id=config.admin_chat_id,
        text=text,
        reply_markup=reply_markup,
        disable_notification=priority is not Priority.CRITICAL,
        link_preview_options=NO_PREVIEW if no_preview else None,
    )
    return True


async def send_photo(
    bot: Bot, config: Config, db: Database, photo: bytes, caption: str, priority: Priority = Priority.DIGEST
) -> None:
    """A picture: silent unless CRITICAL, never deferred (see the module docstring)."""
    if config.admin_chat_id is None:
        return
    await bot.send_photo(
        chat_id=config.admin_chat_id, photo=photo, caption=caption,
        disable_notification=priority is not Priority.CRITICAL,
    )


async def send_document(
    bot: Bot, config: Config, db: Database, document: bytes, filename: str, caption: str,
    priority: Priority = Priority.DIGEST,
) -> None:
    """A file: silent unless CRITICAL, never deferred."""
    if config.admin_chat_id is None:
        return
    await bot.send_document(
        chat_id=config.admin_chat_id, document=document, filename=filename, caption=caption,
        disable_notification=priority is not Priority.CRITICAL,
    )


# ── The digest after the silence ─────────────────────────────────────────────

def _stamp(created_at: str | None, tz: ZoneInfo) -> str:
    try:
        at = parse_utc(created_at).astimezone(tz) if created_at else None
    except ValueError:
        return ""
    if at is None:
        return ""
    now = utcnow().astimezone(tz)
    return at.strftime("%H:%M") if at.date() == now.date() else at.strftime("%d.%m %H:%M")


def _markup(raw: str | None) -> InlineKeyboardMarkup | None:
    if not raw:
        return None
    try:
        return InlineKeyboardMarkup.de_json(json.loads(raw), None)
    except (ValueError, TypeError, KeyError):
        return None


# A flush in progress: the minute job and /unmute may call flush_queue at the
# same moment, and both would read the queue before either deleted a row.
_flushing = False


async def flush_queue(bot: Bot, config: Config, db: Database) -> int:
    """Deliver the deferred messages as one digest once the silence is over;
    returns how many were delivered. Several messages when the backlog is
    long or an item has buttons; only rows actually sent are deleted, so a
    Telegram error leaves the rest for the next minute. A second call while
    one runs returns 0 — the running one has the whole queue."""
    global _flushing
    if _flushing:
        return 0
    _flushing = True
    try:
        return await _flush(bot, config, db)
    finally:
        _flushing = False


async def _flush(bot: Bot, config: Config, db: Database) -> int:
    if config.admin_chat_id is None or await deferred(db, config, Priority.NORMAL):
        return 0
    rows = await db.peek_notifications()
    if not rows:
        return 0
    tz = await _tz(db, config)
    header = t("🌙 Накопилось, пока было тихо:") + "\n\n"
    text, batch, delivered = header, [], 0

    async def deliver(body: str, items: list[dict], markup: InlineKeyboardMarkup | None = None) -> None:
        nonlocal delivered
        await bot.send_message(
            chat_id=config.admin_chat_id, text=body.rstrip(), reply_markup=markup,
            disable_notification=True, link_preview_options=NO_PREVIEW,
        )
        await db.delete_notifications([r["id"] for r in items])
        delivered += len(items)

    try:
        for row in rows:
            stamp = _stamp(row.get("created_at"), tz)
            markup = _markup(row.get("markup"))
            if markup is not None or len(row["text"]) > SAFE_LIMIT - len(header) - 20:
                if batch:
                    await deliver(text, batch)
                    text, batch = t("🌙 (продолжение)") + "\n\n", []
                alone = f"🕒 {stamp}\n{row['text']}" if stamp and len(row["text"]) + 20 < SAFE_LIMIT else row["text"]
                await deliver(alone, [row], markup)
                continue
            body = f"{stamp} · {row['text']}" if stamp else row["text"]
            if batch and len(text) + len(body) + 8 > SAFE_LIMIT:
                await deliver(text, batch)
                text, batch = t("🌙 (продолжение)") + "\n\n", []
            batch.append(row)
            text += f"{len(batch)}. {body}\n\n"
        if batch:
            await deliver(text, batch)
    except Exception:
        logger.exception("Digest delivery failed — the rest waits for the next minute")
    return delivered

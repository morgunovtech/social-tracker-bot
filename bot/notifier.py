"""The one door every notification to the owner goes through.

Three priorities decide what happens with quiet hours and /mute; nothing
else in the codebase reasons about them:

    CRITICAL  rings; bypasses quiet hours and mute
    NORMAL    silent delivery (disable_notification); deferred to the queue
              during quiet hours or while muted, flushed later as one digest
    DIGEST    silent; deferred only by an explicit mute (the weekly report IS
              the digest, so it goes through quiet hours)

The icon in the first character of a line and the way the message arrives
agree (priority_for): 🔴 rings, everything else is silent — the one icon
dictionary is bot/monitors/__init__.py (LEVEL_ICONS). Which message gets
which priority:

    CRITICAL  🛡 profile alerts with a 🔴 line — «похоже на взлом»: a new
              admin or owner, a link in the description, a drop in videos or
              posts; or the profile stopped being readable (deleted, hidden,
              the bot lost its rights); security emails of a critical kind
              («похоже на взлом»: a new sign-in, a changed or reset password,
              a changed email, phone or 2FA, a new token, key or app, a new
              owner of the site in Search Console); the mail worker silent for ~30 min; a
              comment the group is blocked for, at ≥ 70 % confidence; and the
              ✅ after a 🔴 outage — the profile readable again, the mail
              worker back (BOT_PRINCIPLES §1: a recovery after a real fall rings).
    NORMAL    🛡 profile alerts with only 🟠 lines (a new title, description
              or avatar, an admin removed); ✅ after a 🟠 one; 🟠 security
              emails (a login code, a generic alert), ℹ️ unrecognised mail
              and Gmail's forwarding confirmation; collection alerts —
              🟠 follower drop, 🟠 bot inflow, 🎯 milestone, 🟠 expired cookie,
              rejected or missing token, an Instagram token that expires
              within a week, 🟠 failure streak and its end;
              🟠 a deploy that failed; 🟠 a profile link that does not open
              and its ✅; 🟠 a day of outgoing deliveries that
              did not land (the site, TofsDevOps, the watchdog) and its ✅;
              «🔄 Бот обновился» and «ℹ️ После обновления я работаю иначе».
    DIGEST    the weekly report and its chart, the «без изменений» one-liner,
              ℹ️ profile links that go through a redirect or a technical host,
              the hygiene reminder, the monthly digest, the weekly backup,
              the weekly OSV / Dependabot notice.

Replies to the owner's own actions (a tap, a command, the error notice after
one) are not notifications: they answer right away, whatever the hour.

Files (the chart, the backup) and the note that brings a new reply keyboard
are sent silently and never deferred: a digest cannot hold them. The scheduler skips the chart while the report itself is
held; the «🖼 График» button has it any time.

send() returns True when the message was delivered or queued and lets a
Telegram error propagate, so the callers that retry on failure (profile,
mail) keep working; while muted or in quiet hours a NORMAL message is queued,
and deferred() tells a caller in advance whether a priority would wait.
flush_queue() runs every minute from the scheduler and right after /unmute:
when the silence is over it delivers the queue as one numbered digest of
headlines (BOT_PRINCIPLES §3) — the first line of each held message, its
icon first, 🔴 then 🟠 then the rest, each with the time it happened in the
owner's zone. «ℹ️ N» under the digest sends item N whole, below it, with the
buttons it would have had (held_item); a longer backlog, or more than
DIGEST_BUTTONS such items, continues in the next message. A card — a message
with buttons of its own, which act on its text — comes after the digest,
whole, with its time above.

Nothing held is lost: a row leaves the queue only once Telegram took the
digest with its headline; then its full text stays for «ℹ️ N» for
HELD_KEEP_DAYS (bot/db.py) — a row with nothing behind its headline is
deleted at once. Everything lives in the DB, so a restart changes nothing.

Action rows (`actions`, `monitor`): the screens an alert leads to, «🔕 Тихо
8 ч» under what may wait, «⚙️ Не присылать такие» under a 🟠 one. They are
built by bot/callbacks.py and, unlike a card's buttons, do not take a message
out of the digest: the digest gets one row for all its items, and «ℹ️ N»
brings back the item's own row, switch-off included.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from datetime import datetime, timedelta
from enum import Enum
from zoneinfo import ZoneInfo

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from bot import humanize
from bot.callbacks import DIGEST as DIGEST_CALLBACK
from bot.callbacks import actions_markup
from bot.config import Config
from bot.db import Database, parse_utc, utcnow
from bot.i18n import t
from bot.monitors import CRITICAL, NO_PREVIEW, WARNING

logger = logging.getLogger(__name__)

QUIET_HOURS_KEY = "quiet_hours"      # "23-8" or absent = off
MUTE_UNTIL_KEY = "mute_until"        # ISO UTC deadline
# What the screen offers is what a button may set.
QUIET_PRESETS = ("23-8", "0-9")
MUTE_DEFAULT = timedelta(hours=8)
MUTE_MAX = timedelta(days=7)
# Telegram's limit is 4096; the digest keeps a margin for the header and numbering.
SAFE_LIMIT = 4000
TELEGRAM_LIMIT = 4096
# The digest: one line per held message, at most this long; «ℹ️ N» buttons
# under one message — two rows of four, as in TofsDevOps — and a longer
# backlog continues in the next message.
HEADLINE_MAX = 300
DIGEST_BUTTONS = 8


class Priority(Enum):
    CRITICAL = "critical"
    NORMAL = "normal"
    DIGEST = "digest"


def priority_for(lines: list[str] | str) -> Priority:
    """The delivery class of an alert by its icons: a 🔴 line rings."""
    text = "\n".join(lines) if isinstance(lines, list) else lines
    for line in text.splitlines():
        if line.startswith(CRITICAL):
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


async def owner_tz(db: Database, config: Config) -> ZoneInfo:
    """The owner's zone, for the times an alert names. The scheduler imports
    this module for sending, so the zone is read at call time."""
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
    local = (now or utcnow()).astimezone(await owner_tz(db, config))
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
    return deadline.astimezone(await owner_tz(db, config)).strftime(fmt)


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
        "🔴 — похоже на взлом, новый вход, смена пароля, пропавший профиль, замолчавший почтовый воркер, "
        "опасный комментарий — придёт сразу, со звуком. Остальное пришлю сводкой, когда тишина закончится."
    )


# ── Sending ───────────────────────────────────────────────────────────────────

async def deferred(db: Database, config: Config, priority: Priority) -> bool:
    """Would a message of this priority wait right now?"""
    if priority is Priority.CRITICAL:
        return False
    if await mute_until(db) is not None:
        return True
    return priority is Priority.NORMAL and await in_quiet_hours(db, config)


def _actions(priority: Priority, actions: Iterable[str], monitor: str | None) -> dict:
    """The action row as stored and built: the screens, whether «🔕» belongs
    (anything but the digest), the monitor of a 🟠 message (a 🔴 one is not
    offered a switch-off)."""
    return {
        "actions": list(actions),
        "mute": priority is not Priority.DIGEST,
        "monitor": monitor if priority is Priority.NORMAL else None,
    }


async def send(
    bot: Bot,
    config: Config,
    db: Database,
    text: str,
    priority: Priority = Priority.NORMAL,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    no_preview: bool = False,
    actions: Iterable[str] = (),
    monitor: str | None = None,
    hold_on_error: bool = False,
) -> bool:
    """Deliver now, silently unless CRITICAL, or queue for the digest.
    True when delivered or queued; a Telegram error propagates — unless
    hold_on_error: then the message waits in the queue and goes out with the
    next flush, with the time it happened above it (a comment card has no
    other way back: Telegram does not send the comment again). Before the
    first /start there is nobody to write to: False, and nothing is queued.

    reply_markup is a keyboard of the message's own (a card); actions and
    monitor describe the action row (module docstring) and are ignored when
    a reply_markup is given."""
    if config.admin_chat_id is None:
        logger.info("No owner yet — not sent: %s", text[:60])
        return False
    spec = _actions(priority, actions, monitor)
    if reply_markup is None and (spec["actions"] or spec["mute"] or spec["monitor"]):
        stored = json.dumps(spec)
        markup = actions_markup(spec["actions"], mute=spec["mute"], monitor=spec["monitor"])
    else:
        stored = reply_markup.to_json() if reply_markup else None
        markup = reply_markup
    if await deferred(db, config, priority):
        await db.queue_notification(text, stored, utcnow().strftime("%Y-%m-%d %H:%M:%S"))
        logger.info("Queued (quiet hours / mute): %s", text[:60])
        return True
    try:
        await bot.send_message(
            chat_id=config.admin_chat_id,
            text=text,
            reply_markup=markup,
            disable_notification=priority is not Priority.CRITICAL,
            link_preview_options=NO_PREVIEW if no_preview else None,
        )
    except Exception:
        if not hold_on_error:
            raise
        logger.warning("Telegram did not take the message — held for the next flush: %s", text[:60], exc_info=True)
        await db.queue_notification(text, stored, utcnow().strftime("%Y-%m-%d %H:%M:%S"))
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


async def send_keyboard(bot: Bot, config: Config, db: Database, text: str, keyboard: ReplyKeyboardMarkup) -> None:
    """A message that brings the reply keyboard (Telegram shows a new one only
    with a message): silent and never deferred — a digest cannot carry it."""
    if config.admin_chat_id is None:
        return
    await bot.send_message(chat_id=config.admin_chat_id, text=text, reply_markup=keyboard, disable_notification=True)


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


def _stored(raw: str | None) -> tuple[InlineKeyboardMarkup | None, dict | None]:
    """What a queued row carries: a keyboard of its own, or an action-row spec."""
    if not raw:
        return None, None
    try:
        data = json.loads(raw)
    except ValueError:
        return None, None
    if isinstance(data, dict) and "actions" in data:
        return None, data
    try:
        return InlineKeyboardMarkup.de_json(data, None), None
    except (ValueError, TypeError, KeyError):
        return None, None


def _union(specs: list[dict]) -> InlineKeyboardMarkup | None:
    """One action row for a batch: every screen its items lead to, «🔕» if any
    of them may wait; no switch-off, which belongs to a single message."""
    screens: list[str] = []
    for spec in specs:
        for screen in spec.get("actions") or []:
            if screen not in screens:
                screens.append(screen)
    return actions_markup(screens, mute=any(spec.get("mute") for spec in specs))


# A flush in progress: the minute job and /unmute may call flush_queue at the
# same moment, and both would read the queue before either deleted a row.
_flushing = False


async def flush_queue(bot: Bot, config: Config, db: Database) -> int:
    """Deliver the deferred messages as one digest of headlines once the
    silence is over; returns how many were delivered. More messages when the
    backlog is long, and a card after the digest; a row stops waiting only
    once Telegram took the message with it, so a Telegram error leaves the
    rest for the next minute. A second call while one runs returns 0 — the
    running one has the whole queue."""
    global _flushing
    if _flushing:
        return 0
    _flushing = True
    try:
        return await _flush(bot, config, db)
    finally:
        _flushing = False


def _rank(text: str) -> int:
    """🔴 first, then 🟠, then the rest — a recovery, a fact, a report."""
    if text.startswith(CRITICAL):
        return 0
    return 1 if text.startswith(WARNING) else 2


def _head(text: str) -> str:
    """The item's line in the digest: the first line of the message, its icon
    first (BOT_PRINCIPLES §3: a digest shows the headline only)."""
    head = humanize.headline(text).rstrip().rstrip(":")
    return head if len(head) <= HEADLINE_MAX else head[: HEADLINE_MAX - 1] + "…"


def _has_more(row: dict, spec: dict | None) -> bool:
    """Is there anything behind the headline: more lines, a first line too
    long for the digest, or a «⚙️ Не присылать такие» of its own, which the
    digest's shared row leaves out."""
    first = humanize.headline(row["text"]).strip()
    return first != row["text"].strip() or len(first) > HEADLINE_MAX or bool(spec and spec.get("monitor"))


def _details_kb(details: list[tuple[int, int]], shared: InlineKeyboardMarkup | None) -> InlineKeyboardMarkup | None:
    """«ℹ️ N» buttons, four in a row, above the digest's shared action row."""
    buttons = [InlineKeyboardButton(f"ℹ️ {n}", callback_data=f"{DIGEST_CALLBACK}:{row_id}") for n, row_id in details]
    rows = [buttons[i:i + 4] for i in range(0, len(buttons), 4)]
    rows += list(shared.inline_keyboard) if shared else []
    return InlineKeyboardMarkup(rows) if rows else None


async def _flush(bot: Bot, config: Config, db: Database) -> int:
    if config.admin_chat_id is None or await deferred(db, config, Priority.NORMAL):
        return 0
    rows = await db.peek_notifications()
    if not rows:
        return 0
    tz = await owner_tz(db, config)
    # Oldest first within a level: rows come in the order they were held.
    rows = sorted(rows, key=lambda row: _rank(row["text"]))
    held = [(row, *_stored(row.get("markup"))) for row in rows]
    hint = "\n" + t("ℹ️ N — пункт целиком, с его кнопками.")
    delivered, number = 0, 0
    text, batch, specs, details = t("🌙 Накопилось, пока было тихо:") + "\n\n", [], [], []

    async def send_batch() -> None:
        nonlocal delivered, text, batch, specs, details
        body = text + (hint if details else "")
        await bot.send_message(
            chat_id=config.admin_chat_id, text=body.rstrip(), reply_markup=_details_kb(details, _union(specs)),
            disable_notification=True, link_preview_options=NO_PREVIEW,
        )
        # Telegram has the headlines: what has more behind it is kept for «ℹ️ N», the rest is done with.
        opened = {row_id for _, row_id in details}
        await db.mark_shown([r["id"] for r in batch if r["id"] in opened], utcnow())
        await db.delete_notifications([r["id"] for r in batch if r["id"] not in opened])
        delivered += len(batch)
        text, batch, specs, details = t("🌙 (продолжение)") + "\n\n", [], [], []

    try:
        for row, markup, spec in held:
            if markup is not None:
                continue                   # a card: after the digest, with its buttons
            stamp = _stamp(row.get("created_at"), tz)
            number += 1
            line = f"{number}. {stamp} · {_head(row['text'])}" if stamp else f"{number}. {_head(row['text'])}"
            more = _has_more(row, spec)
            if batch and (len(text) + len(line) + len(hint) + 2 > SAFE_LIMIT or (more and len(details) >= DIGEST_BUTTONS)):
                await send_batch()
            batch.append(row)
            if spec:
                specs.append(spec)
            if more:
                details.append((number, row["id"]))
            text += line + "\n"
        if batch:
            await send_batch()
        # A card's buttons act on its text (delete a comment, open a build log): it comes whole, on its own.
        for row, markup, _ in held:
            if markup is None:
                continue
            stamp = _stamp(row.get("created_at"), tz)
            alone = f"🕒 {stamp}\n{row['text']}" if stamp and len(row["text"]) + 20 < SAFE_LIMIT else row["text"]
            await bot.send_message(
                chat_id=config.admin_chat_id, text=alone, reply_markup=markup,
                disable_notification=True, link_preview_options=NO_PREVIEW,
            )
            await db.delete_notifications([row["id"]])
            delivered += 1
    except Exception:
        logger.exception("Digest delivery failed — the rest waits for the next minute")
    return delivered


async def held_item(db: Database, config: Config, row_id: int) -> tuple[str, InlineKeyboardMarkup | None] | None:
    """«ℹ️ N» under a digest: the held message whole, with the time it
    happened above and the buttons it would have had; None once its full
    text is gone (HELD_KEEP_DAYS after the digest)."""
    row = await db.held(row_id, utcnow())
    if row is None:
        return None
    markup, spec = _stored(row.get("markup"))
    if spec:
        markup = actions_markup(spec.get("actions") or [], mute=bool(spec.get("mute")), monitor=spec.get("monitor"))
    stamp = _stamp(row.get("created_at"), await owner_tz(db, config))
    text = f"🕒 {stamp}\n{row['text']}" if stamp and len(row["text"]) + 20 < SAFE_LIMIT else row["text"]
    return (text if len(text) <= TELEGRAM_LIMIT else text[: TELEGRAM_LIMIT - 1] + "…"), markup

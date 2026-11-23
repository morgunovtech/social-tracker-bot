"""The one door for notifications: what rings, what waits, and the digest
after the silence (bot/notifier.py)."""

from datetime import UTC, datetime, timedelta

import pytest
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot import notifier
from bot.notifier import Priority, flush_queue, parse_duration, parse_quiet_hours, send

NIGHT = datetime(2026, 11, 23, 2, 30, tzinfo=UTC)   # 02:30 UTC — inside 23-8
DAY = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)


@pytest.fixture
def clock(monkeypatch):
    """Freeze the notifier's clock."""
    state = {"now": DAY}
    monkeypatch.setattr(notifier, "utcnow", lambda: state["now"])
    return state


# --- parsing ------------------------------------------------------------------

@pytest.mark.parametrize(
    ("arg", "expected"),
    [
        ("1h", timedelta(hours=1)), ("8H", timedelta(hours=8)), ("30m", timedelta(minutes=30)),
        ("1d", timedelta(days=1)), ("45", timedelta(minutes=45)), (" ", None), ("", None), (None, None),
        ("0h", None), ("-1h", None), ("abc", None), ("99999999999d", None), ("1w", None),
    ],
)
def test_parse_duration(arg, expected):
    assert parse_duration(arg) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("23-8", (23, 8)), ("0-9", (0, 9)), ("off", None), (None, None), ("", None), ("25-3", None), ("8-8", None), ("x-y", None)],
)
def test_parse_quiet_hours(raw, expected):
    assert parse_quiet_hours(raw) == expected


def test_quiet_hours_wrap_midnight():
    assert notifier._within((23, 8), 23) and notifier._within((23, 8), 3) and not notifier._within((23, 8), 8)
    assert notifier._within((0, 9), 0) and not notifier._within((0, 9), 9) and not notifier._within((0, 9), 23)


def test_priority_follows_the_icon():
    assert notifier.priority_for(["🟠 Telegram: −50", "🎯 LinkedIn перешагнул 1 000!"]) is Priority.NORMAL
    assert notifier.priority_for(["🟠 Telegram: новая аватарка", "🚨 Telegram: новый админ — X"]) is Priority.CRITICAL
    assert notifier.priority_for("🛡 Профиль\n\n🔴 Telegram: профиль не читается") is Priority.CRITICAL
    assert notifier.priority_for("the 🚨 is not at the start of a line") is Priority.NORMAL


# --- what rings, what waits ----------------------------------------------------

async def test_by_day_everything_is_delivered_and_only_critical_rings(bot, config, db):
    await send(bot, config, db, "🚨 hijack", Priority.CRITICAL)
    await send(bot, config, db, "🟠 change")
    await send(bot, config, db, "📊 report", Priority.DIGEST)
    assert bot.messages == ["🚨 hijack", "🟠 change", "📊 report"]
    assert bot.silent == [False, True, True]
    assert await db.peek_notifications() == []


async def test_quiet_hours_hold_normal_but_not_critical_or_digest(bot, config, db, clock):
    await notifier.set_quiet_hours(db, "23-8")
    clock["now"] = NIGHT
    assert await notifier.in_quiet_hours(db, config)
    assert await send(bot, config, db, "🟠 change")                       # queued, still True
    await send(bot, config, db, "🚨 hijack", Priority.CRITICAL)
    await send(bot, config, db, "📊 report", Priority.DIGEST)
    assert bot.messages == ["🚨 hijack", "📊 report"] and bot.silent == [False, True]
    assert [r["text"] for r in await db.peek_notifications()] == ["🟠 change"]


async def test_quiet_hours_are_in_the_owners_zone(bot, config, db, clock):
    await notifier.set_quiet_hours(db, "23-8")
    await db.set_setting("report_tz", "Asia/Almaty")                       # UTC+5: 02:30 UTC is 07:30, 03:30 UTC is 08:30
    clock["now"] = NIGHT
    assert await notifier.in_quiet_hours(db, config)
    clock["now"] = NIGHT + timedelta(hours=1)
    assert not await notifier.in_quiet_hours(db, config)


async def test_mute_holds_everything_but_critical(bot, config, db, clock):
    deadline = await notifier.set_mute(db, timedelta(hours=8))
    assert deadline == DAY + timedelta(hours=8)
    assert await notifier.mute_until_local(db, config) == "20:00"
    await send(bot, config, db, "🟠 change")
    await send(bot, config, db, "📊 report", Priority.DIGEST)
    await send(bot, config, db, "🚨 hijack", Priority.CRITICAL)
    assert bot.messages == ["🚨 hijack"] and bot.silent == [False]
    assert [r["text"] for r in await db.peek_notifications()] == ["🟠 change", "📊 report"]
    # The mute runs out by itself.
    clock["now"] = DAY + timedelta(hours=9)
    assert await notifier.mute_until(db) is None
    await send(bot, config, db, "🟠 later")
    assert bot.messages[-1] == "🟠 later"


async def test_unmute_and_a_far_deadline(bot, config, db, clock):
    await notifier.set_mute(db, timedelta(days=2))
    assert await notifier.mute_until_local(db, config) == "25.11 12:00"
    await notifier.set_mute(db, None)
    assert await notifier.mute_until(db) is None and not await notifier.deferred(db, config, Priority.NORMAL)


async def test_silence_status(config, db, clock):
    assert await notifier.silence_status(db, config) is None
    await notifier.set_quiet_hours(db, "23-8")
    assert await notifier.silence_status(db, config) is None
    clock["now"] = NIGHT
    assert await notifier.silence_status(db, config) == "🌙 Тихие часы до 08:00"
    await notifier.set_mute(db, timedelta(hours=1))
    assert await notifier.silence_status(db, config) == "🔕 Тишина до 03:30"


# --- the digest ----------------------------------------------------------------

async def test_digest_comes_as_one_message_when_the_silence_ends(bot, config, db, clock):
    await notifier.set_quiet_hours(db, "23-8")
    clock["now"] = NIGHT
    await send(bot, config, db, "🟠 Telegram: −50 подписчиков за день")
    await send(bot, config, db, "🔄 Бот обновился:\n  • aiohttp 1 → 2")
    assert await flush_queue(bot, config, db) == 0                        # still night: nothing moves
    assert bot.messages == []
    clock["now"] = DAY
    assert await flush_queue(bot, config, db) == 2
    (digest,) = bot.messages
    assert digest.startswith("🌙 Накопилось, пока было тихо:\n\n")
    assert "1. 02:30 · 🟠 Telegram: −50 подписчиков за день\n\n2. 02:30 · 🔄 Бот обновился:\n  • aiohttp 1 → 2" in digest
    assert bot.silent == [True]
    assert await db.peek_notifications() == []
    assert await flush_queue(bot, config, db) == 0                        # nothing comes twice


async def test_a_message_with_buttons_or_too_long_goes_alone(bot, config, db, clock):
    await notifier.set_mute(db, timedelta(hours=1))
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("📄 Лог сборки", url="https://example.com/log")]])
    await send(bot, config, db, "🟠 first")
    await send(bot, config, db, "🟠 Новая версия бота не запустилась", reply_markup=markup)
    await send(bot, config, db, "📊 " + "x" * 4200, Priority.DIGEST)
    await send(bot, config, db, "🟠 last")
    await notifier.set_mute(db, None)
    assert await flush_queue(bot, config, db) == 4
    assert [m.split("\n")[0] for m in bot.messages] == [
        "🌙 Накопилось, пока было тихо:", "🕒 12:00", "📊 " + "x" * 4200, "🌙 (продолжение)",
    ]
    assert bot.markups[1].inline_keyboard[0][0].url == "https://example.com/log"
    assert "1. 12:00 · 🟠 first" in bot.messages[0] and "1. 12:00 · 🟠 last" in bot.messages[3]


async def test_a_failed_digest_keeps_the_rows(bot, config, db, clock):
    await notifier.set_mute(db, timedelta(hours=1))
    await send(bot, config, db, "🟠 one")
    await notifier.set_mute(db, None)

    async def broken(*args, **kwargs):
        raise RuntimeError("Telegram is down")

    bot.send_message = broken
    assert await flush_queue(bot, config, db) == 0
    assert [r["text"] for r in await db.peek_notifications()] == ["🟠 one"]


async def test_queue_keeps_the_newest_rows(db, monkeypatch):
    monkeypatch.setattr("bot.db.PENDING_MAX", 3)
    for i in range(5):
        await db.queue_notification(f"m{i}")
    assert [r["text"] for r in await db.peek_notifications()] == ["m2", "m3", "m4"]


async def test_backup_leaves_the_queue_behind(db, tmp_path):
    await db.queue_notification("held")
    copy = tmp_path / "copy.db"
    await db.snapshot_without_secrets(str(copy))
    import sqlite3
    with sqlite3.connect(copy) as conn:
        assert conn.execute("SELECT COUNT(*) FROM pending_notifications").fetchone()[0] == 0


async def test_files_are_silent_and_never_wait(bot, config, db, clock):
    await notifier.set_mute(db, timedelta(hours=1))
    await notifier.send_photo(bot, config, db, b"png", "chart")
    await notifier.send_document(bot, config, db, b"db", "f.db", "backup")
    assert bot.photos[0]["silent"] and bot.documents[0]["silent"]




async def test_two_flushes_at_once_deliver_the_queue_once(bot, config, db, clock):
    import asyncio

    await notifier.set_mute(db, timedelta(hours=1))
    await send(bot, config, db, "🟠 held", Priority.NORMAL)
    await notifier.set_mute(db, None)
    # The minute job and /unmute at the same moment: one of them has the queue, the other steps aside.
    results = await asyncio.gather(flush_queue(bot, config, db), flush_queue(bot, config, db))
    assert sorted(results) == [0, 1] and len(bot.messages) == 1       # one digest, not two

"""The one door for notifications: what rings, what waits, and the digest
after the silence (bot/notifier.py)."""

from datetime import UTC, datetime, timedelta

import pytest
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot import notifier
from bot.db import HELD_KEEP_DAYS, Database
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
    assert notifier.priority_for(["🟠 Telegram: новая аватарка", "🔴 Telegram: похоже на взлом — новый админ X"]) is Priority.CRITICAL
    assert notifier.priority_for("🛡 Профиль\n\n🔴 Telegram: профиль не читается") is Priority.CRITICAL
    assert notifier.priority_for("the 🔴 is not at the start of a line") is Priority.NORMAL
    assert notifier.priority_for("⚠️ не смог проверить\nℹ️ факт") is Priority.NORMAL


# --- what rings, what waits ----------------------------------------------------

async def test_by_day_everything_is_delivered_and_only_critical_rings(bot, config, db):
    await send(bot, config, db, "🔴 hijack", Priority.CRITICAL)
    await send(bot, config, db, "🟠 change")
    await send(bot, config, db, "📊 report", Priority.DIGEST)
    assert bot.messages == ["🔴 hijack", "🟠 change", "📊 report"]
    assert bot.silent == [False, True, True]
    assert await db.peek_notifications() == []


async def test_quiet_hours_hold_normal_but_not_critical_or_digest(bot, config, db, clock):
    await notifier.set_quiet_hours(db, "23-8")
    clock["now"] = NIGHT
    assert await notifier.in_quiet_hours(db, config)
    assert await send(bot, config, db, "🟠 change")                       # queued, still True
    await send(bot, config, db, "🔴 hijack", Priority.CRITICAL)
    await send(bot, config, db, "📊 report", Priority.DIGEST)
    assert bot.messages == ["🔴 hijack", "📊 report"] and bot.silent == [False, True]
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
    await send(bot, config, db, "🔴 hijack", Priority.CRITICAL)
    assert bot.messages == ["🔴 hijack"] and bot.silent == [False]
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

def _alert(head: str) -> str:
    """A held alert in the one shape: headline, meaning, steps, the technical line."""
    return f"{head}\n\nЧто это значит.\n\nЧто делать:\n• шаг\n\nТех.: деталь"


def _details(markup) -> dict[str, str]:
    """The «ℹ️ N» buttons under a digest: label → callback data."""
    return {b.text: b.callback_data for row in markup.inline_keyboard for b in row if b.text.startswith("ℹ️")}


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
    assert "1. 02:30 · 🟠 Telegram: −50 подписчиков за день\n2. 02:30 · 🔄 Бот обновился\n" in digest
    assert "aiohttp" not in digest                                        # the headline only
    assert list(_details(bot.markups[0])) == ["ℹ️ 2"]                     # item 1 has nothing behind its line
    assert bot.silent == [True]
    assert await db.peek_notifications() == []
    assert await flush_queue(bot, config, db) == 0                        # nothing comes twice


async def test_the_digest_is_headlines_red_then_orange_with_a_button_each(bot, config, db, clock):
    await notifier.set_mute(db, timedelta(hours=1))
    await send(bot, config, db, "✅ YouTube: данные снова собираются. Ничего делать не нужно.")
    await send(bot, config, db, _alert("🟠 Telegram: −50 подписчиков за день"), actions=("dyn",), monitor="followers")
    await send(bot, config, db, _alert("🔴 Telegram: похоже на взлом — новый админ X"), actions=("sec",))
    await send(bot, config, db, _alert("🟠 Instagram: пришёл код входа"), actions=("sec",), monitor="mail")
    await notifier.set_mute(db, None)
    assert await flush_queue(bot, config, db) == 4
    (digest,) = bot.messages
    assert digest.split("\n")[2:6] == [
        "1. 12:00 · 🔴 Telegram: похоже на взлом — новый админ X",
        "2. 12:00 · 🟠 Telegram: −50 подписчиков за день",
        "3. 12:00 · 🟠 Instagram: пришёл код входа",
        "4. 12:00 · ✅ YouTube: данные снова собираются. Ничего делать не нужно.",
    ]
    assert "Что делать" not in digest and "Тех.:" not in digest
    assert digest.endswith("ℹ️ N — пункт целиком, с его кнопками.")
    held = {r["text"].split("\n")[0]: r["id"] for r in await _all_rows(db)}
    assert _details(bot.markups[0]) == {
        "ℹ️ 1": f"dg:{held['🔴 Telegram: похоже на взлом — новый админ X']}",
        "ℹ️ 2": f"dg:{held['🟠 Telegram: −50 подписчиков за день']}",
        "ℹ️ 3": f"dg:{held['🟠 Instagram: пришёл код входа']}",
    }
    # Under the buttons, the digest's shared row: every screen its items lead to, «🔕».
    shared = [b.callback_data for b in bot.markups[0].inline_keyboard[-1]]
    assert shared == ["open:sec", "open:dyn", "mute:8h"]
    # The one-liner had nothing more: it is done with; the others wait for «ℹ️ N».
    assert len(held) == 3 and await db.peek_notifications() == []


async def _all_rows(db) -> list[dict]:
    import sqlite3

    with sqlite3.connect(db._db_path) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute("SELECT * FROM pending_notifications ORDER BY id")]


async def test_info_n_sends_the_item_whole_with_its_own_buttons(bot, config, db, clock):
    await notifier.set_mute(db, timedelta(hours=1))
    full = _alert("🟠 Telegram: −50 подписчиков за день")
    await send(bot, config, db, full, actions=("dyn",), monitor="followers")
    await notifier.set_mute(db, None)
    await flush_queue(bot, config, db)
    row_id = int(_details(bot.markups[0])["ℹ️ 1"].split(":")[1])
    clock["now"] = DAY + timedelta(hours=3)
    text, markup = await notifier.held_item(db, config, row_id)
    assert text == f"🕒 12:00\n{full}"                                     # when it happened, not when opened
    assert [b.callback_data for row in markup.inline_keyboard for b in row] == ["open:dyn", "mute:8h", "mod:followers:off"]
    assert await notifier.held_item(db, config, row_id) is not None        # a second tap works the same


async def test_the_full_texts_are_kept_for_a_week(bot, config, db, clock):
    await notifier.set_mute(db, timedelta(hours=1))
    await send(bot, config, db, _alert("🟠 one"))
    await notifier.set_mute(db, None)
    await flush_queue(bot, config, db)
    row_id = int(_details(bot.markups[0])["ℹ️ 1"].split(":")[1])
    assert await db.held(row_id, DAY + timedelta(days=HELD_KEEP_DAYS, minutes=-1)) is not None
    assert await db.held(row_id, DAY + timedelta(days=HELD_KEEP_DAYS, minutes=1)) is None
    assert (await db.prune(DAY + timedelta(days=HELD_KEEP_DAYS, minutes=1)))["pending_notifications"] == 1
    assert await _all_rows(db) == []


async def test_nothing_held_is_lost_across_a_restart(bot, config, db, clock):
    await notifier.set_mute(db, timedelta(hours=1))
    await send(bot, config, db, _alert("🟠 one"))
    await send(bot, config, db, _alert("🟠 two"))
    await notifier.set_mute(db, None)
    send_message = bot.send_message

    async def broken(*args, **kwargs):
        raise RuntimeError("Telegram is down")

    bot.send_message = broken
    assert await flush_queue(bot, config, db) == 0                        # the digest did not go out
    bot.send_message = send_message

    # The process restarts: a new connection to the same file, a fresh notifier state.
    restarted = Database(db._db_path)
    await restarted.init()
    notifier._flushing = False
    assert len(await restarted.peek_notifications()) == 2
    assert await flush_queue(bot, config, restarted) == 2
    row_id = int(_details(bot.markups[0])["ℹ️ 2"].split(":")[1])

    again = Database(db._db_path)
    await again.init()
    text, _ = await notifier.held_item(again, config, row_id)
    assert text.endswith(_alert("🟠 two"))


async def test_a_card_comes_whole_after_the_digest(bot, config, db, clock):
    await notifier.set_mute(db, timedelta(hours=1))
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("📄 Лог сборки", url="https://example.com/log")]])
    await send(bot, config, db, "🟠 first")
    await send(bot, config, db, "🟠 Новая версия бота не запустилась", reply_markup=markup)
    await send(bot, config, db, "📊 " + "x" * 4200, Priority.DIGEST)
    await send(bot, config, db, "🟠 last")
    await notifier.set_mute(db, None)
    assert await flush_queue(bot, config, db) == 4
    assert len(bot.messages) == 2
    digest, card = bot.messages
    assert "1. 12:00 · 🟠 first\n2. 12:00 · 🟠 last\n3. 12:00 · 📊 " in digest and len(digest) < 1000
    assert list(_details(bot.markups[0])) == ["ℹ️ 3"]                     # the long one: a clipped line and a button
    assert card == "🕒 12:00\n🟠 Новая версия бота не запустилась"
    assert bot.markups[1].inline_keyboard[0][0].url == "https://example.com/log"
    text, _ = await notifier.held_item(db, config, int(_details(bot.markups[0])["ℹ️ 3"].split(":")[1]))
    assert len(text) <= 4096 and text.startswith("📊 xxx")


async def test_a_long_backlog_continues_with_the_numbers(bot, config, db, clock):
    await notifier.set_mute(db, timedelta(hours=1))
    for i in range(notifier.DIGEST_BUTTONS + 2):
        await send(bot, config, db, _alert(f"🟠 item {i + 1}"))
    await notifier.set_mute(db, None)
    assert await flush_queue(bot, config, db) == notifier.DIGEST_BUTTONS + 2
    first, second = bot.messages
    assert list(_details(bot.markups[0])) == [f"ℹ️ {n}" for n in range(1, notifier.DIGEST_BUTTONS + 1)]
    assert [len(row) for row in bot.markups[0].inline_keyboard[:2]] == [4, 4]
    assert second.startswith("🌙 (продолжение)\n\n9. 12:00 · 🟠 item 9\n10. 12:00 · 🟠 item 10")
    assert list(_details(bot.markups[1])) == ["ℹ️ 9", "ℹ️ 10"]


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
    await db.queue_notification("shown")
    (shown,) = await db.peek_notifications()
    await db.mark_shown([shown["id"]])
    for i in range(5):
        await db.queue_notification(f"m{i}")
    assert [r["text"] for r in await db.peek_notifications()] == ["m2", "m3", "m4"]
    assert await db.held(shown["id"]) is not None              # a full text behind «ℹ️ N» is not in the count


async def test_an_older_db_gets_the_column_and_keeps_its_queue(tmp_path):
    import sqlite3

    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE pending_notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL, "
                     "markup TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        conn.execute("INSERT INTO pending_notifications (text) VALUES ('🟠 held before the update')")
    db = Database(str(path))
    await db.init()
    await db.init()                                            # twice: every start runs it
    assert [r["text"] for r in await db.peek_notifications()] == ["🟠 held before the update"]


async def test_backup_leaves_the_queue_behind(db, tmp_path):
    await db.queue_notification("shown in a digest")
    await db.mark_shown([(await db.peek_notifications())[0]["id"]])
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

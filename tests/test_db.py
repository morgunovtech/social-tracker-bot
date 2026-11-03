import os
import sqlite3

import pytest
from conftest import COOKIE

from bot.db import Database


async def test_upsert_keeps_one_row_per_platform_per_day(db):
    await db.upsert("telegram", 1000)
    await db.upsert("telegram", 1005, source="manual")
    await db.upsert("youtube", 128)
    history = await db.get_history("telegram", 7)
    assert [(r["count"], r["source"]) for r in history] == [(1005, "manual")]
    assert (await db.get_latest("youtube"))["count"] == 128
    assert await db.get_latest("linkedin") is None


async def test_history_and_by_date(db, insert):
    insert("telegram", 990, 10)
    insert("telegram", 1000, 3)
    insert("telegram", 1010, 0)
    assert [r["count"] for r in await db.get_history("telegram", 7)] == [1000, 1010]
    assert (await db.get_latest("telegram"))["count"] == 1010


async def test_settings(db):
    assert await db.get_setting("missing") is None
    assert await db.get_setting("missing", "dflt") == "dflt"
    await db.set_setting("report_dow", "sat")
    await db.set_setting("report_dow", "mon")
    assert await db.get_setting("report_dow") == "mon"


async def test_snapshot_drops_the_cookie_completely(db, tmp_path):
    await db.set_setting("linkedin_li_at", COOKIE)
    await db.set_setting("report_dow", "sat")
    await db.upsert("telegram", 1000)
    dest = str(tmp_path / "snapshot.db")

    await db.snapshot_without_secrets(dest)

    with sqlite3.connect(dest) as conn:
        keys = {row[0] for row in conn.execute("SELECT key FROM settings")}
        counts = conn.execute("SELECT count FROM followers").fetchall()
    assert keys == {"report_dow"} and counts == [(1000,)]
    # Not just unlisted: the bytes must not survive in free pages either.
    assert COOKIE.encode() not in open(dest, "rb").read()
    assert await db.get_setting("linkedin_li_at") == COOKIE        # live DB untouched


@pytest.mark.skipif(os.getuid() == 0, reason="root can write anywhere")
async def test_unwritable_data_dir_explains_the_fix(tmp_path):
    readonly = tmp_path / "data"
    readonly.mkdir()
    readonly.chmod(0o500)
    try:
        with pytest.raises(RuntimeError, match="chown"):
            await Database(str(readonly / "followers.db")).init()
    finally:
        readonly.chmod(0o700)


# --- restore -----------------------------------------------------------------

async def _backup_db(path, rows, settings) -> Database:
    """A backup file as the bot itself writes it: same schema, given content."""
    backup = Database(str(path))
    await backup.init()
    with sqlite3.connect(backup._db_path) as conn:
        conn.executemany(
            "INSERT INTO followers (platform, count, source, collected_at) "
            "VALUES (?, ?, 'api', DATETIME('now', ?))",
            [(platform, count, f"-{days} days") for platform, count, days in rows],
        )
        conn.executemany("INSERT INTO settings (key, value) VALUES (?, ?)", settings.items())
    return backup


async def test_restore_merges_and_live_data_wins(db, insert, tmp_path):
    backup = await _backup_db(
        tmp_path / "backup.db",
        rows=[("telegram", 900, 3), ("telegram", 950, 0), ("youtube", 100, 3)],
        settings={"report_time": "09:15", "quiet_if_no_change": "1",
                  "linkedin_li_at": "OLD-COOKIE", "linkedin_li_at_set_at": "2026-01-01T00:00:00+00:00"},
    )
    insert("telegram", 1000, 0)                                   # collected after the wipe
    await db.set_setting("quiet_if_no_change", "0")
    await db.set_setting("linkedin_li_at", COOKIE)

    result = await db.restore_from(backup._db_path)

    assert result["added"] == 2 and result["total"] == 3
    assert [r["count"] for r in await db.get_history("telegram", 7)] == [900, 1000]
    assert await db.get_setting("report_time") == "09:15"         # missing → taken from backup
    assert await db.get_setting("quiet_if_no_change") == "0"      # live wins
    assert await db.get_setting("linkedin_li_at") == COOKIE       # live cookie kept...
    assert await db.get_setting("linkedin_li_at_set_at") is None  # ...without the old one's age


async def test_restore_brings_back_the_cookie_when_live_has_none(db, tmp_path):
    backup = await _backup_db(
        tmp_path / "backup.db", rows=[],
        settings={"linkedin_li_at": "OLD-COOKIE", "linkedin_li_at_set_at": "2026-01-01T00:00:00+00:00"},
    )
    await db.restore_from(backup._db_path)
    assert await db.get_setting("linkedin_li_at") == "OLD-COOKIE"
    assert await db.get_setting("linkedin_li_at_set_at") == "2026-01-01T00:00:00+00:00"


async def test_restore_twice_adds_nothing(db, tmp_path):
    backup = await _backup_db(tmp_path / "backup.db", rows=[("youtube", 100, 3)], settings={})
    assert (await db.restore_from(backup._db_path))["added"] == 1
    assert (await db.restore_from(backup._db_path))["added"] == 0


async def test_restore_rejects_foreign_files(db, tmp_path):
    text = tmp_path / "notes.db"
    text.write_text("definitely not sqlite " * 100)
    with pytest.raises(ValueError, match="SQLite"):
        await db.restore_from(str(text))

    other = tmp_path / "other.db"
    with sqlite3.connect(other) as conn:
        conn.execute("CREATE TABLE photos (id INTEGER)")
    with pytest.raises(ValueError, match="таблиц"):
        await db.restore_from(str(other))
    assert await db.get_latest("telegram") is None


async def test_security_events_dedup_by_uid(db):
    assert await db.add_event("mail:1", "Google", "new_login", "🚨 Google: новый вход")
    assert not await db.add_event("mail:1", "Google", "new_login", "🚨 Google: новый вход")
    await db.add_event("mail:2", "LinkedIn", "login_code", "🟠 LinkedIn: код входа")
    assert [e["uid"] for e in await db.recent_events()] == ["mail:2", "mail:1"]


async def test_restore_merges_security_events(db, tmp_path):
    await db.add_event("mail:1", "Google", "new_login", "старое событие")
    backup = str(tmp_path / "backup.db")
    await db.snapshot_without_secrets(backup)

    live = Database(str(tmp_path / "live.db"))
    await live.init()
    await live.add_event("mail:2", "LinkedIn", "login_code", "новое событие")
    await live.restore_from(backup)
    await live.restore_from(backup)                        # twice: still no duplicates
    assert sorted(e["uid"] for e in await live.recent_events()) == ["mail:1", "mail:2"]


async def test_restore_accepts_a_backup_without_the_security_log(db, tmp_path):
    await db.upsert("telegram", 1000)
    backup = str(tmp_path / "old.db")
    await db.snapshot_without_secrets(backup)
    with sqlite3.connect(backup) as conn:
        conn.execute("DROP TABLE security_events")
    live = Database(str(tmp_path / "live.db"))
    await live.init()
    assert (await live.restore_from(backup))["total"] == 1


async def test_restore_skips_live_state(db, tmp_path):
    await db.set_setting("profile_telegram", '{"title": "old"}')
    await db.set_setting("profile_fail_telegram", "5")
    await db.set_setting("fail_streak_youtube", "3")
    await db.set_setting("hygiene_youtube_2fa", "app")
    backup = str(tmp_path / "backup.db")
    await db.snapshot_without_secrets(backup)

    live = Database(str(tmp_path / "live.db"))
    await live.init()
    await live.restore_from(backup)
    for key in ("profile_telegram", "profile_fail_telegram", "fail_streak_youtube"):
        assert await live.get_setting(key) is None
    assert await live.get_setting("hygiene_youtube_2fa") == "app"

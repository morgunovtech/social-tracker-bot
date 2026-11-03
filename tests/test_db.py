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

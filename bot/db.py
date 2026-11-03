from __future__ import annotations

import logging
import os
import sqlite3
from datetime import UTC, date, datetime, timedelta

import aiosqlite

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(UTC)


def parse_utc(ts: str) -> datetime:
    """Parse an ISO/SQLite timestamp; naive values are assumed to be UTC."""
    dt = datetime.fromisoformat(ts)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS followers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    count INTEGER NOT NULL,
    source TEXT DEFAULT 'api',
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_UNIQUE_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_platform_date
ON followers (platform, DATE(collected_at));
"""

_CREATE_SETTINGS = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# Security log: profile changes and security emails. platform is a display
# name ("Google" for mail about a Google account); uid dedups re-deliveries
# and restores.
_CREATE_EVENTS = """
CREATE TABLE IF NOT EXISTS security_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid TEXT NOT NULL UNIQUE,
    platform TEXT NOT NULL,
    kind TEXT NOT NULL,
    detail TEXT NOT NULL,
    occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# Settings that must never leave the server (wiped from off-site backups).
_SECRET_SETTINGS = ("linkedin_li_at",)


def _check_backup(path: str) -> None:
    """Raise ValueError unless path is an intact SQLite file with this bot's tables."""
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("файл повреждён")
            columns = {row[1] for row in conn.execute("PRAGMA table_info(followers)")}
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    except sqlite3.DatabaseError as e:
        raise ValueError("это не файл базы SQLite") from e
    if not {"platform", "count", "source", "collected_at"} <= columns or "settings" not in tables:
        raise ValueError("в файле нет таблиц бота")


async def _scalar(db: aiosqlite.Connection, sql: str):
    row = await (await db.execute(sql)).fetchone()
    return row[0]


class Database:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def init(self) -> None:
        db_dir = os.path.dirname(self._db_path) or "."
        os.makedirs(db_dir, exist_ok=True)
        if not os.access(db_dir, os.W_OK):
            # Typical cause: Docker created the ./data bind mount as root on a Linux host.
            raise RuntimeError(
                f"Database directory {db_dir!r} is not writable by uid {os.getuid()}. "
                f"On the host run: sudo chown -R {os.getuid()} ./data"
            )
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(_CREATE_TABLE)
            await db.execute(_CREATE_UNIQUE_INDEX)
            await db.execute(_CREATE_SETTINGS)
            await db.execute(_CREATE_EVENTS)
            await db.commit()
        logger.info("Database initialized at %s", self._db_path)

    async def snapshot_without_secrets(self, dest_path: str) -> None:
        """Write a consistent copy of the DB to dest_path with secret settings wiped."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("VACUUM INTO ?", (dest_path,))
        async with aiosqlite.connect(dest_path) as db:
            placeholders = ",".join("?" * len(_SECRET_SETTINGS))
            await db.execute(f"DELETE FROM settings WHERE key IN ({placeholders})", _SECRET_SETTINGS)
            await db.commit()
            # Rebuild the file so deleted values don't linger in free pages.
            await db.execute("VACUUM")

    async def restore_from(self, backup_path: str) -> dict:
        """Merge a backup file into the live DB; the live DB wins every conflict.

        Follower rows are added only for (platform, day) pairs the live DB lacks,
        so data collected since the backup is kept. Settings are added only when
        missing; the cookie and its timestamp travel as a pair, so a live cookie
        is never replaced by an older one. Raises ValueError for a file that is
        not an intact backup of this bot.
        """
        _check_backup(backup_path)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("ATTACH DATABASE ? AS backup", (backup_path,))
            try:
                before = await _scalar(db, "SELECT COUNT(*) FROM followers")
                await db.execute(
                    """
                    INSERT OR IGNORE INTO followers (platform, count, source, collected_at)
                    SELECT platform, count, source, collected_at FROM backup.followers
                    """
                )
                cookie_keys = ("linkedin_li_at", "linkedin_li_at_set_at")
                has_cookie = await _scalar(db, "SELECT COUNT(*) FROM settings WHERE key = 'linkedin_li_at'")
                skip = cookie_keys if has_cookie else ()
                await db.execute(
                    f"""
                    INSERT OR IGNORE INTO settings (key, value)
                    SELECT key, value FROM backup.settings
                    WHERE key NOT IN ({",".join("?" * len(skip)) or "''"})
                    """,
                    skip,
                )
                # Backups made before the security log existed have no such table.
                if await _scalar(
                    db, "SELECT COUNT(*) FROM backup.sqlite_master WHERE name = 'security_events'"
                ):
                    await db.execute(
                        """
                        INSERT OR IGNORE INTO security_events (uid, platform, kind, detail, occurred_at)
                        SELECT uid, platform, kind, detail, occurred_at FROM backup.security_events
                        """
                    )
                await db.commit()
                after = await _scalar(db, "SELECT COUNT(*) FROM followers")
                first, last = await (
                    await db.execute("SELECT MIN(DATE(collected_at)), MAX(DATE(collected_at)) FROM followers")
                ).fetchone()
            finally:
                await db.rollback()  # no-op after commit; DETACH fails inside a transaction
                await db.execute("DETACH DATABASE backup")
        return {"added": after - before, "total": after, "first": first, "last": last}

    async def get_setting(self, key: str, default: str | None = None) -> str | None:
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = await cursor.fetchone()
            return row[0] if row else default

    async def set_setting(self, key: str, value: str) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            await db.commit()

    async def upsert(self, platform: str, count: int, source: str = "api") -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO followers (platform, count, source, collected_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT (platform, DATE(collected_at))
                DO UPDATE SET count = excluded.count,
                              source = excluded.source,
                              collected_at = excluded.collected_at
                """,
                (platform, count, source),
            )
            await db.commit()

    async def get_latest(self, platform: str) -> dict | None:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM followers WHERE platform = ? ORDER BY collected_at DESC LIMIT 1",
                (platform,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_by_date(self, platform: str, target_date: date) -> dict | None:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM followers WHERE platform = ? AND DATE(collected_at) = ? ORDER BY collected_at DESC LIMIT 1",
                (platform, target_date.isoformat()),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_history(self, platform: str, days: int) -> list[dict]:
        since = (utcnow() - timedelta(days=days)).date()
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM followers
                WHERE platform = ? AND DATE(collected_at) >= ?
                ORDER BY collected_at ASC
                """,
                (platform, since.isoformat()),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def add_event(self, uid: str, platform: str, kind: str, detail: str) -> bool:
        """Log a security event; False when this uid is already logged."""
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "INSERT OR IGNORE INTO security_events (uid, platform, kind, detail) VALUES (?, ?, ?, ?)",
                (uid, platform, kind, detail),
            )
            await db.commit()
            return cursor.rowcount == 1

    async def has_event(self, uid: str) -> bool:
        async with aiosqlite.connect(self._db_path) as db:
            row = await (await db.execute("SELECT 1 FROM security_events WHERE uid = ?", (uid,))).fetchone()
            return row is not None

    async def recent_events(self, limit: int = 5) -> list[dict]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM security_events ORDER BY occurred_at DESC, id DESC LIMIT ?", (limit,)
            )
            return [dict(r) for r in await cursor.fetchall()]

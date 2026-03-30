from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta

import aiosqlite

logger = logging.getLogger(__name__)

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


class Database:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def init(self) -> None:
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(_CREATE_TABLE)
            await db.execute(_CREATE_UNIQUE_INDEX)
            await db.execute(_CREATE_SETTINGS)
            await db.commit()
        logger.info("Database initialized at %s", self._db_path)

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
        since = (datetime.utcnow() - timedelta(days=days)).date()
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

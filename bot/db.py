from __future__ import annotations

import logging
import os
import sqlite3
from datetime import UTC, date, datetime, timedelta

import aiosqlite

from bot.i18n import t

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(UTC)


def utc_stamp(dt: datetime) -> str:
    """A moment as the tables keep it: 'YYYY-MM-DD HH:MM:SS' in UTC, the
    format of CURRENT_TIMESTAMP, so stored and computed stamps compare."""
    return dt.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


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
# and restores; detail is the line before translation, a JSON phrase
# (bot/humanize.py) — rows written by 1.5.0 and earlier hold finished
# text, which bot/security_log.py reads too.
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

# Notifications held back by quiet hours or /mute (bot/notifier.py), delivered
# as one digest of headlines when the silence ends. markup is the inline
# keyboard as JSON. shown_at is NULL while a row waits; once the digest with
# its headline went out, the full text stays for «ℹ️ N» under the digest
# until HELD_KEEP_DAYS have passed.
_CREATE_PENDING = """
CREATE TABLE IF NOT EXISTS pending_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    markup TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    shown_at TIMESTAMP
);
"""
# The queue keeps the newest this many waiting rows: a week of /mute must not
# turn into a hundred-message morning.
PENDING_MAX = 100

# Comments of the channel's discussion group that the classifier looked at
# (bot/monitors/comments.py): one row per message, the text excerpt kept only
# when the message was flagged. action is what the owner did from the card
# (deleted, banned, unbanned), label what they said about the verdict
# (confirmed, false_positive) — the numbers the accuracy table is made of.
_CREATE_COMMENTS = """
CREATE TABLE IF NOT EXISTS comment_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    user_id INTEGER,
    sender_chat_id INTEGER,
    user_name TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL DEFAULT '',
    media TEXT NOT NULL DEFAULT '',
    link TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL,
    confidence INTEGER NOT NULL DEFAULT 0,
    reason TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL DEFAULT '',
    label TEXT NOT NULL DEFAULT '',
    reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    acted_at TIMESTAMP,
    edited_at TIMESTAMP,
    UNIQUE (chat_id, message_id)
);
"""

# Life of the channel (bot/monitors/channel.py): every join and leave the
# Bot API reports to an admin bot, and every post with the reactions it
# gathered. One channel is tracked, so queries don't filter by chat_id; the
# column is kept so a changed TELEGRAM_CHANNEL_ID is still told apart.
_CREATE_CHANNEL_EVENTS = """
CREATE TABLE IF NOT EXISTS channel_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    user_name TEXT NOT NULL DEFAULT '',
    via TEXT NOT NULL DEFAULT '',
    occurred_at TIMESTAMP NOT NULL,
    UNIQUE (chat_id, kind, user_id, occurred_at)
);
"""
# posted_at is NULL for a post from before the bot watched, known only by
# its reactions: it counts for reactions, not as a publication.
_CREATE_CHANNEL_POSTS = """
CREATE TABLE IF NOT EXISTS channel_posts (
    chat_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    kind TEXT NOT NULL DEFAULT '',
    posted_at TIMESTAMP,
    reactions INTEGER NOT NULL DEFAULT 0,
    reactions_json TEXT NOT NULL DEFAULT '',
    reacted_at TIMESTAMP,
    PRIMARY KEY (chat_id, message_id)
);
"""

# What the comment check spent: per UTC day and model (a fallback may answer
# with another model), the calls and the tokens Anthropic bills for. No text,
# no author — the backup may carry it.
_CREATE_API_USAGE = """
CREATE TABLE IF NOT EXISTS api_usage (
    day TEXT NOT NULL,
    model TEXT NOT NULL,
    calls INTEGER NOT NULL DEFAULT 0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, model)
);
"""

# Settings that must never leave the server (wiped from off-site backups):
# the cookie, the token and the watchdog address — whoever has it can ping
# in the bot's name.
_SECRET_SETTINGS = ("linkedin_li_at", "instagram_token", "watchdog_url",
                    # the reputation report's read-only keys (bot/reputation/)
                    "rep_google_key", "rep_yandex_token", "rep_cloudflare_token",
                    # keys connected from the chat (bot/connections.py)
                    "conn_youtube_api_key", "conn_anthropic_api_key")
# Each secret with the settings that describe it (when it was set, when it dies).
_SECRET_KEYS: dict[str, tuple[str, ...]] = {
    "linkedin_li_at": ("linkedin_li_at", "linkedin_li_at_set_at"),
    "instagram_token": ("instagram_token", "instagram_token_set_at", "instagram_user_id", "instagram_username"),
    "watchdog_url": ("watchdog_url", "watchdog_last"),
    "rep_google_key": ("rep_google_key",),
    "rep_yandex_token": ("rep_yandex_token",),
    "rep_cloudflare_token": ("rep_cloudflare_token",),
    "conn_youtube_api_key": ("conn_youtube_api_key",),
    "conn_anthropic_api_key": ("conn_anthropic_api_key",),
}

# Retention, applied once a day by the scheduler (prune). A join and a flagged
# comment name a person, and the weekly backup carries every row to the chat,
# so nothing stays longer than a screen reads it: /channel and /comments look
# 30 days back, the report 7.
REVIEW_OK_KEEP_DAYS = 30          # comments the model called fine: only a count on /comments
REVIEW_FLAGGED_KEEP_DAYS = 180    # cards: their buttons keep working for a while
CHANNEL_EVENTS_KEEP_DAYS = 90     # joins and leaves, with names
HELD_KEEP_DAYS = 7                # full texts behind a digest's «ℹ️ N»: as long as the longest /mute
API_USAGE_KEEP_DAYS = 90          # what the comment check spent: 💬 Комментарии reads 7 days


def _check_backup(path: str) -> None:
    """Raise ValueError unless path is an intact SQLite file with this bot's tables."""
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError(t("файл повреждён"))
            columns = {row[1] for row in conn.execute("PRAGMA table_info(followers)")}
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    except sqlite3.DatabaseError as e:
        raise ValueError(t("это не файл базы SQLite")) from e
    if not {"platform", "count", "source", "collected_at"} <= columns or "settings" not in tables:
        raise ValueError(t("в файле нет таблиц бота"))


async def _scalar(db: aiosqlite.Connection, sql: str, params: tuple = ()):
    row = await (await db.execute(sql, params)).fetchone()
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
            await db.execute(_CREATE_PENDING)
            # Added with the headline digest: an older DB gets the column, its waiting rows stay waiting.
            pending = {row[1] for row in await (await db.execute("PRAGMA table_info(pending_notifications)")).fetchall()}
            if "shown_at" not in pending:
                await db.execute("ALTER TABLE pending_notifications ADD COLUMN shown_at TIMESTAMP")
            await db.execute(_CREATE_COMMENTS)
            reviews = {row[1] for row in await (await db.execute("PRAGMA table_info(comment_reviews)")).fetchall()}
            if "edited_at" not in reviews:
                await db.execute("ALTER TABLE comment_reviews ADD COLUMN edited_at TIMESTAMP")
            if "sender_chat_id" not in reviews:
                await db.execute("ALTER TABLE comment_reviews ADD COLUMN sender_chat_id INTEGER")
            await db.execute(_CREATE_CHANNEL_EVENTS)
            await db.execute(_CREATE_CHANNEL_POSTS)
            await db.execute(_CREATE_API_USAGE)
            await db.commit()
        logger.info("Database initialized at %s", self._db_path)

    async def snapshot_without_secrets(self, dest_path: str) -> None:
        """Write a consistent copy of the DB to dest_path with secret settings wiped."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("VACUUM INTO ?", (dest_path,))
        async with aiosqlite.connect(dest_path) as db:
            placeholders = ",".join("?" * len(_SECRET_SETTINGS))
            await db.execute(f"DELETE FROM settings WHERE key IN ({placeholders})", _SECRET_SETTINGS)
            # Held-back alerts and the full texts behind a digest's «ℹ️ N» are live state, not history.
            await db.execute("DELETE FROM pending_notifications")
            await db.commit()
            # Rebuild the file so deleted values don't linger in free pages.
            await db.execute("VACUUM")

    async def restore_from(self, backup_path: str) -> dict:
        """Merge a backup file into the live DB; the live DB wins every conflict.

        Follower rows are added only for (platform, day) pairs the live DB lacks,
        so data collected since the backup is kept. Settings are added only when
        missing; the cookie and its timestamp travel as a pair, so a live cookie
        is never replaced by an older one; profile baselines and failure
        streaks are live state and never restored. Security events are merged
        by uid. Raises ValueError for a file that is not an intact backup of
        this bot.
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
                # A secret and its dates travel together. A live secret keeps its
                # own; a backup without the secret (every Sunday backup: the
                # secrets are wiped from it) brings no dates either, or the
                # LinkedIn screen would age a cookie the bot does not have.
                skip: tuple[str, ...] = ()
                for secret, keys in _SECRET_KEYS.items():
                    live = await _scalar(db, "SELECT COUNT(*) FROM settings WHERE key = ? AND value != ''", (secret,))
                    saved = await _scalar(
                        db, "SELECT COUNT(*) FROM backup.settings WHERE key = ? AND value != ''", (secret,)
                    )
                    if live or not saved:
                        skip += keys
                await db.execute(
                    f"""
                    INSERT OR IGNORE INTO settings (key, value)
                    SELECT key, value FROM backup.settings
                    WHERE key NOT IN ({",".join("?" * len(skip)) or "''"})
                      -- Live state, not history: an old profile baseline would alert on
                      -- every change made since the backup, an old failure streak on
                      -- a recovery that never happened.
                      AND key NOT LIKE 'profile\\_%' ESCAPE '\\'
                      AND key NOT LIKE '%fail%'
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
                # The channel's events and posts: history too, merged the same way.
                if await _scalar(db, "SELECT COUNT(*) FROM backup.sqlite_master WHERE name = 'channel_events'"):
                    await db.execute(
                        """
                        INSERT OR IGNORE INTO channel_events (chat_id, kind, user_id, user_name, via, occurred_at)
                        SELECT chat_id, kind, user_id, user_name, via, occurred_at FROM backup.channel_events
                        """
                    )
                if await _scalar(db, "SELECT COUNT(*) FROM backup.sqlite_master WHERE name = 'channel_posts'"):
                    await db.execute(
                        """
                        INSERT OR IGNORE INTO channel_posts
                            (chat_id, message_id, kind, posted_at, reactions, reactions_json, reacted_at)
                        SELECT chat_id, message_id, kind, posted_at, reactions, reactions_json, reacted_at
                        FROM backup.channel_posts
                        """
                    )
                # What the comment check spent: the live days win, older days come back.
                if await _scalar(db, "SELECT COUNT(*) FROM backup.sqlite_master WHERE name = 'api_usage'"):
                    await db.execute(
                        """
                        INSERT OR IGNORE INTO api_usage (day, model, calls, input_tokens, output_tokens)
                        SELECT day, model, calls, input_tokens, output_tokens FROM backup.api_usage
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

    async def get_on_or_before(self, platform: str, target_date: date, max_back_days: int) -> dict | None:
        """The newest row dated target_date or up to max_back_days earlier:
        a baseline that a single missed collection does not erase."""
        earliest = target_date - timedelta(days=max_back_days)
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM followers
                WHERE platform = ? AND DATE(collected_at) <= ? AND DATE(collected_at) >= ?
                ORDER BY collected_at DESC LIMIT 1
                """,
                (platform, target_date.isoformat(), earliest.isoformat()),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_history(self, platform: str, days: int) -> list[dict]:
        """The rows of the last `days` UTC days, today included: 7 is a week, not eight days."""
        since = (utcnow() - timedelta(days=max(days, 1) - 1)).date()
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
                "SELECT * FROM security_events WHERE kind != 'info' ORDER BY occurred_at DESC, id DESC LIMIT ?",
                (limit,),
            )
            return [dict(r) for r in await cursor.fetchall()]

    # --- the quiet queue (bot/notifier.py) ---------------------------------

    async def queue_notification(self, text: str, markup: str | None = None, created_at: str | None = None) -> None:
        """Hold a message for the digest, stamped with when it happened; the
        oldest waiting rows beyond PENDING_MAX are dropped."""
        created_at = created_at or utcnow().strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO pending_notifications (text, markup, created_at) VALUES (?, ?, ?)",
                (text, markup, created_at),
            )
            await db.execute(
                """
                DELETE FROM pending_notifications WHERE shown_at IS NULL AND id NOT IN (
                    SELECT id FROM pending_notifications WHERE shown_at IS NULL ORDER BY id DESC LIMIT ?
                )
                """,
                (PENDING_MAX,),
            )
            await db.commit()

    async def peek_notifications(self) -> list[dict]:
        """The rows still waiting for a digest, oldest first."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM pending_notifications WHERE shown_at IS NULL ORDER BY id ASC")
            return [dict(r) for r in await cursor.fetchall()]

    async def mark_shown(self, ids: list[int], at: datetime | None = None) -> None:
        """The digest with these rows' headlines went out: they stop waiting
        and their full texts stay for «ℹ️ N» (held)."""
        if not ids:
            return
        stamp = (at or utcnow()).astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                f"UPDATE pending_notifications SET shown_at = ? WHERE id IN ({','.join('?' * len(ids))})",
                (stamp, *ids),
            )
            await db.commit()

    async def held(self, row_id: int, now: datetime | None = None) -> dict | None:
        """A row a digest showed as a headline, while its full text is kept."""
        since = ((now or utcnow()) - timedelta(days=HELD_KEEP_DAYS)).astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            row = await (await db.execute(
                "SELECT * FROM pending_notifications WHERE id = ? AND shown_at >= ?", (row_id, since)
            )).fetchone()
            return dict(row) if row else None

    async def delete_notifications(self, ids: list[int]) -> None:
        if not ids:
            return
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                f"DELETE FROM pending_notifications WHERE id IN ({','.join('?' * len(ids))})", ids
            )
            await db.commit()

    # --- comments of the discussion group (bot/monitors/comments.py) --------

    async def add_review(
        self, chat_id: int, message_id: int, user_id: int | None, user_name: str, text: str, media: str,
        link: str, category: str, confidence: int, reason: str, sender_chat_id: int | None = None,
    ) -> int | None:
        """Record a classified comment; None when this message is already recorded
        (Telegram re-delivered the update). sender_chat_id: the channel the
        comment was written as, instead of a user_id."""
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                """
                INSERT OR IGNORE INTO comment_reviews
                    (chat_id, message_id, user_id, sender_chat_id, user_name, text, media, link, category,
                     confidence, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (chat_id, message_id, user_id, sender_chat_id, user_name, text, media, link, category,
                 confidence, reason),
            )
            await db.commit()
            return cursor.lastrowid if cursor.rowcount == 1 else None

    async def get_review(self, review_id: int) -> dict | None:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            row = await (await db.execute("SELECT * FROM comment_reviews WHERE id = ?", (review_id,))).fetchone()
            return dict(row) if row else None

    async def get_review_by_message(self, chat_id: int, message_id: int) -> dict | None:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            row = await (
                await db.execute(
                    "SELECT * FROM comment_reviews WHERE chat_id = ? AND message_id = ?", (chat_id, message_id)
                )
            ).fetchone()
            return dict(row) if row else None

    async def rereview(
        self, review_id: int, user_name: str, text: str, media: str, category: str, confidence: int, reason: str,
        edited_at: datetime | None = None,
    ) -> None:
        """An edited comment classified again: the new verdict replaces the
        old one, and the owner's action and label on the old text go with it —
        the card is about what the comment says now. reviewed_at moves, so the
        edit counts toward the daily limit. edited_at is Telegram's time of the
        edit (now when unknown): the same edit delivered again is told by it."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                UPDATE comment_reviews SET user_name = ?, text = ?, media = ?, category = ?, confidence = ?,
                    reason = ?, action = '', label = '', acted_at = NULL,
                    reviewed_at = CURRENT_TIMESTAMP, edited_at = ?
                WHERE id = ?
                """,
                (user_name, text, media, category, confidence, reason, utc_stamp(edited_at or utcnow()), review_id),
            )
            await db.commit()

    async def touch_review(self, review_id: int, edited_at: datetime | None = None) -> None:
        """An edit the model called fine still counts toward the daily limit,
        and is remembered by its time like a flagged one (see rereview)."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE comment_reviews SET reviewed_at = CURRENT_TIMESTAMP, edited_at = ? WHERE id = ?",
                (utc_stamp(edited_at or utcnow()), review_id),
            )
            await db.commit()

    async def update_review(self, review_id: int, *, action: str | None = None, label: str | None = None) -> None:
        """What the owner did with a card: the action, the label, or both."""
        sets, params = [], []
        if action is not None:
            sets += ["action = ?", "acted_at = CURRENT_TIMESTAMP"]
            params.append(action)
        if label is not None:
            sets.append("label = ?")
            params.append(label)
        if not sets:
            return
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(f"UPDATE comment_reviews SET {', '.join(sets)} WHERE id = ?", (*params, review_id))
            await db.commit()

    async def count_reviews_since(self, since: datetime) -> int:
        """How many comments were classified since the moment (the daily limit)."""
        stamp = since.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(self._db_path) as db:
            return await _scalar(db, "SELECT COUNT(*) FROM comment_reviews WHERE reviewed_at >= ?", (stamp,))

    async def prune(self, now: datetime | None = None) -> dict[str, int]:
        """Drop what no screen reads any more; returns the rows removed per table."""
        now = now or utcnow()

        def before(days: int) -> str:
            return (now - timedelta(days=days)).astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")

        async with aiosqlite.connect(self._db_path) as db:
            ok = await db.execute(
                "DELETE FROM comment_reviews WHERE category = 'ok' AND reviewed_at < ?", (before(REVIEW_OK_KEEP_DAYS),)
            )
            flagged = await db.execute(
                "DELETE FROM comment_reviews WHERE category != 'ok' AND reviewed_at < ?",
                (before(REVIEW_FLAGGED_KEEP_DAYS),),
            )
            events = await db.execute(
                "DELETE FROM channel_events WHERE occurred_at < ?", (before(CHANNEL_EVENTS_KEEP_DAYS),)
            )
            held = await db.execute(
                "DELETE FROM pending_notifications WHERE shown_at < ?", (before(HELD_KEEP_DAYS),)
            )
            usage = await db.execute(
                "DELETE FROM api_usage WHERE day < ?", (before(API_USAGE_KEEP_DAYS)[:10],)
            )
            await db.commit()
        return {
            "comment_reviews": ok.rowcount + flagged.rowcount,
            "channel_events": events.rowcount,
            "pending_notifications": held.rowcount,
            "api_usage": usage.rowcount,
        }

    async def add_api_usage(self, model: str, input_tokens: int, output_tokens: int, day: date | None = None) -> None:
        """One billed call of the comment check, added to its day and model."""
        key = (day or utcnow().date()).isoformat()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO api_usage (day, model, calls, input_tokens, output_tokens) VALUES (?, ?, 1, ?, ?)
                ON CONFLICT (day, model) DO UPDATE SET calls = calls + 1,
                    input_tokens = input_tokens + excluded.input_tokens,
                    output_tokens = output_tokens + excluded.output_tokens
                """,
                (key, model, max(0, input_tokens), max(0, output_tokens)),
            )
            await db.commit()

    async def api_usage(self, days: int, today: date | None = None) -> list[dict]:
        """Per model, the calls and tokens of the last `days` UTC days (today included)."""
        since = ((today or utcnow().date()) - timedelta(days=days - 1)).isoformat()
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (await db.execute(
                """
                SELECT model, SUM(calls) AS calls, SUM(input_tokens) AS input_tokens,
                       SUM(output_tokens) AS output_tokens
                FROM api_usage WHERE day >= ? GROUP BY model ORDER BY SUM(calls) DESC, model
                """,
                (since,),
            )).fetchall()
        return [dict(row) for row in rows]

    async def count_author_reviews(self, chat_id: int, user_id: int | None, sender_chat_id: int | None = None) -> int:
        """How many messages of this author the bot has already seen in the
        group: a person by user_id, a channel writing as itself by sender_chat_id."""
        column, author = ("sender_chat_id", sender_chat_id) if user_id is None else ("user_id", user_id)
        async with aiosqlite.connect(self._db_path) as db:
            return await _scalar(
                db, f"SELECT COUNT(*) FROM comment_reviews WHERE chat_id = ? AND {column} = ?", (chat_id, author)
            )

    # --- life of the channel (bot/monitors/channel.py) ----------------------

    async def add_channel_event(
        self, chat_id: int, kind: str, user_id: int, user_name: str, via: str, occurred_at: datetime
    ) -> bool:
        """A join or a leave; False when this very event is already stored
        (Telegram re-delivered the update)."""
        stamp = occurred_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                """
                INSERT OR IGNORE INTO channel_events (chat_id, kind, user_id, user_name, via, occurred_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (chat_id, kind, user_id, user_name, via, stamp),
            )
            await db.commit()
            return cursor.rowcount == 1

    async def add_channel_post(self, chat_id: int, message_id: int, kind: str, posted_at: datetime) -> bool:
        """A new post; False when it is already stored. A row made earlier by
        the post's reactions gets its kind and date."""
        stamp = posted_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO channel_posts (chat_id, message_id, kind, posted_at) VALUES (?, ?, ?, ?)
                ON CONFLICT (chat_id, message_id) DO UPDATE
                    SET kind = excluded.kind, posted_at = excluded.posted_at
                    WHERE channel_posts.posted_at IS NULL
                """,
                (chat_id, message_id, kind, stamp),
            )
            await db.commit()
            return cursor.rowcount == 1

    async def set_post_reactions(
        self, chat_id: int, message_id: int, total: int, reactions_json: str, at: datetime
    ) -> None:
        """The current reactions of a post (a snapshot, not a delta); a post
        the bot never saw posted gets a row without a date."""
        stamp = at.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO channel_posts (chat_id, message_id, reactions, reactions_json, reacted_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (chat_id, message_id) DO UPDATE
                    SET reactions = excluded.reactions, reactions_json = excluded.reactions_json,
                        reacted_at = excluded.reacted_at
                """,
                (chat_id, message_id, total, reactions_json, stamp),
            )
            await db.commit()

    async def channel_has_data(self) -> bool:
        async with aiosqlite.connect(self._db_path) as db:
            events = await _scalar(db, "SELECT COUNT(*) FROM channel_events")
            posts = await _scalar(db, "SELECT COUNT(*) FROM channel_posts")
            return bool(events or posts)

    async def channel_counts(self, since: datetime) -> dict[str, int]:
        """Joins, leaves and posts since the moment, and the reactions the
        posts of that period have gathered."""
        stamp = since.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(self._db_path) as db:
            joins = await _scalar(
                db, "SELECT COUNT(*) FROM channel_events WHERE kind = 'join' AND occurred_at >= ?", (stamp,)
            )
            leaves = await _scalar(
                db, "SELECT COUNT(*) FROM channel_events WHERE kind = 'leave' AND occurred_at >= ?", (stamp,)
            )
            posts, reactions = await (
                await db.execute(
                    "SELECT COUNT(*), COALESCE(SUM(reactions), 0) FROM channel_posts WHERE posted_at >= ?", (stamp,)
                )
            ).fetchone()
        return {"joins": joins, "leaves": leaves, "posts": posts, "reactions": reactions}

    async def channel_sources(self, since: datetime) -> list[tuple[str, int]]:
        """Where the joins came from: (via, count), most first."""
        stamp = since.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(self._db_path) as db:
            rows = await (
                await db.execute(
                    """
                    SELECT via, COUNT(*) AS n FROM channel_events
                    WHERE kind = 'join' AND occurred_at >= ?
                    GROUP BY via ORDER BY n DESC, via ASC
                    """,
                    (stamp,),
                )
            ).fetchall()
        return [(row[0], row[1]) for row in rows]

    async def channel_top_posts(self, since: datetime, limit: int) -> list[dict]:
        stamp = since.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (
                await db.execute(
                    """
                    SELECT * FROM channel_posts
                    WHERE reactions > 0 AND (posted_at >= ? OR (posted_at IS NULL AND reacted_at >= ?))
                    ORDER BY reactions DESC, message_id DESC LIMIT ?
                    """,
                    (stamp, stamp, limit),
                )
            ).fetchall()
        return [dict(r) for r in rows]

    async def channel_recent_events(self, limit: int) -> list[dict]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (
                await db.execute(
                    "SELECT * FROM channel_events ORDER BY occurred_at DESC, id DESC LIMIT ?", (limit,)
                )
            ).fetchall()
        return [dict(r) for r in rows]

    async def review_stats(self, days: int = 30) -> dict:
        """The accuracy table: how many comments were checked, and per category
        how many were flagged, acted on, confirmed and marked false."""
        since = (utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            total = await _scalar(db, "SELECT COUNT(*) FROM comment_reviews WHERE reviewed_at >= ?", (since,))
            rows = await (
                await db.execute(
                    """
                    SELECT category,
                           COUNT(*) AS flagged,
                           SUM(action IN ('deleted', 'banned')) AS acted,
                           SUM(label = 'confirmed') AS confirmed,
                           SUM(label = 'false_positive') AS false_positive
                    FROM comment_reviews
                    WHERE reviewed_at >= ? AND category != 'ok'
                    GROUP BY category
                    """,
                    (since,),
                )
            ).fetchall()
        return {"checked": total, "categories": {r["category"]: dict(r) for r in rows}}

"""Test environment: env vars are set BEFORE bot.config is imported, so every
test sees the same deterministic configuration and a developer's local .env
(load_dotenv never overrides variables that are already set) can't leak in.
Optional integrations are set to "" on purpose: no test may push to a real
site, ping a real watchdog or use a real cookie."""

import os

os.environ.update({
    "BOT_TOKEN": "123456:TEST",
    "ADMIN_CHAT_ID": "42",
    "TELEGRAM_CHANNEL_ID": "@test_channel",
    "YOUTUBE_API_KEY": "test-key",
    "YOUTUBE_CHANNEL_ID": "UCtest",
    "LINKEDIN_PROFILE_URL": "https://www.linkedin.com/in/test/",
    "LINKEDIN_LI_AT": "",
    "LINKEDIN_STALE_DAYS": "7",
    "REPORT_HOUR_UTC": "8",
    "REPORT_MINUTE": "0",
    "REPORT_DOW": "sat",
    "QUIET_IF_NO_CHANGE": "0",
    "SITE_INGEST_URL": "",
    "SOCIALBOT_INGEST_TOKEN": "",
    "HEALTHCHECK_URL": "",
    "UPDATE_WATCH": "0",
    "APP_COMMIT": "",
    "RAILWAY_GIT_COMMIT_SHA": "",
    "GITHUB_REPOSITORY": "",
    "RAILWAY_GIT_REPO_OWNER": "",
    "RAILWAY_GIT_REPO_NAME": "",
    "GITHUB_TOKEN": "",
})

import dataclasses  # noqa: E402
import sqlite3  # noqa: E402
from datetime import timedelta  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import pytest  # noqa: E402

from bot.config import Config  # noqa: E402
from bot.db import Database, utcnow  # noqa: E402

ADMIN_ID = 42
STRANGER_ID = 7
COOKIE = "AQEDA" + "x" * 80


class FakeBot:
    """Records what the bot would have sent."""

    def __init__(self):
        self.messages: list[str] = []
        self.photos: list[dict] = []
        self.documents: list[dict] = []

    async def send_message(self, chat_id, text, **kwargs):
        self.messages.append(text)

    async def send_photo(self, chat_id, photo, caption=None, **kwargs):
        self.photos.append({"photo": photo, "caption": caption})

    async def send_document(self, chat_id, document, filename=None, caption=None, **kwargs):
        self.documents.append({"document": document, "filename": filename, "caption": caption})


class FakeMessage:
    def __init__(self, text: str = ""):
        self.text = text
        self.document = None
        self.reply_to_message = None
        self.replies: list[str] = []
        self.photos: list[bytes] = []
        self.deleted = False

    async def reply_text(self, text, **kwargs):
        self.replies.append(text)

    async def reply_photo(self, photo, **kwargs):
        self.photos.append(photo)

    async def delete(self):
        self.deleted = True


class FakeChat:
    def __init__(self):
        self.sent: list[str] = []

    async def send_message(self, text, **kwargs):
        self.sent.append(text)


class FakeQuery:
    def __init__(self, data: str):
        self.data = data
        self.answers: list[dict] = []
        self.edits: list[str] = []

    async def answer(self, text=None, show_alert=False):
        self.answers.append({"text": text, "show_alert": show_alert})

    async def edit_message_text(self, text, **kwargs):
        self.edits.append(text)


@pytest.fixture
def config(tmp_path) -> Config:
    return dataclasses.replace(Config.from_env(), db_path=str(tmp_path / "followers.db"))


@pytest.fixture
async def db(config) -> Database:
    database = Database(config.db_path)
    await database.init()
    return database


@pytest.fixture
def bot() -> FakeBot:
    return FakeBot()


@pytest.fixture
def insert(db):
    """Insert a follower row collected `days_ago` days back (UTC)."""

    def _insert(platform: str, count: int, days_ago: int = 0, source: str = "api") -> None:
        ts = (utcnow() - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(db._db_path) as conn:
            conn.execute(
                "INSERT INTO followers (platform, count, source, collected_at) VALUES (?, ?, ?, ?)",
                (platform, count, source, ts),
            )

    return _insert


@pytest.fixture
def make_update():
    """Build a fake Update for a command, a plain message or a button press."""

    def _make(user_id: int = ADMIN_ID, text: str = "", callback: str | None = None):
        query = FakeQuery(callback) if callback is not None else None
        return SimpleNamespace(
            effective_user=SimpleNamespace(id=user_id),
            effective_chat=FakeChat(),
            message=None if query else FakeMessage(text),
            callback_query=query,
        )

    return _make


@pytest.fixture
def make_context(bot, config, db):
    def _make(*args: str, scheduler=None):
        bot_data = {"config": config, "db": db}
        if scheduler is not None:
            bot_data["scheduler"] = scheduler
        return SimpleNamespace(bot=bot, bot_data=bot_data, args=list(args))

    return _make

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
    "INSTAGRAM_USERNAME": "",
    "INSTAGRAM_ACCESS_TOKEN": "",
    "LINKEDIN_PROFILE_URL": "https://www.linkedin.com/in/test/",
    "LINKEDIN_LI_AT": "",
    "LINKEDIN_STALE_DAYS": "7",
    "REPORT_HOUR": "8",
    "REPORT_HOUR_UTC": "",
    "REPORT_TZ": "UTC",
    "TIMEZONE": "",
    "REPORT_MINUTE": "0",
    "REPORT_DOW": "sat",
    "QUIET_IF_NO_CHANGE": "0",
    "BOT_LANG": "",
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
    "SECURITY_MAIL_URL": "",
    "SECURITY_MAIL_TOKEN": "",
    "ANTHROPIC_API_KEY": "",
    "COMMENTS_MODEL": "",
    "COMMENTS_CHAT_ID": "",
})

import asyncio  # noqa: E402
import dataclasses  # noqa: E402
import sqlite3  # noqa: E402
from datetime import UTC, datetime, timedelta  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import pytest  # noqa: E402

from bot.config import Config  # noqa: E402
from bot.db import Database, utcnow  # noqa: E402

ADMIN_ID = 42
STRANGER_ID = 7
COOKIE = "AQEDA" + "x" * 80


class FakeBot:
    """Records what the bot would have sent; .silent says whether each message
    came without a sound (disable_notification), in the order of .messages."""

    def __init__(self):
        self.messages: list[str] = []
        self.silent: list[bool] = []
        self.markups: list = []
        self.photos: list[dict] = []
        self.documents: list[dict] = []
        # The discussion group (tests/test_comments.py): what the bot did there.
        self.deleted: list[tuple[int, int]] = []
        self.banned: list[tuple[int, int]] = []
        self.unbanned: list[tuple[int, int]] = []
        self.banned_chats: list[tuple[int, int]] = []     # ban_chat_sender_chat: a channel writing as itself
        self.unbanned_chats: list[tuple[int, int]] = []
        self.files: dict[str, bytes] = {}
        self.chats: dict = {}
        self.admins: list = []
        self.fail_with: Exception | None = None

    async def send_message(self, chat_id, text, **kwargs):
        self.messages.append(text)
        self.silent.append(bool(kwargs.get("disable_notification")))
        self.markups.append(kwargs.get("reply_markup"))

    async def send_photo(self, chat_id, photo, caption=None, **kwargs):
        self.photos.append({"photo": photo, "caption": caption, "silent": bool(kwargs.get("disable_notification"))})

    async def send_document(self, chat_id, document, filename=None, caption=None, **kwargs):
        self.documents.append({
            "document": document, "filename": filename, "caption": caption,
            "silent": bool(kwargs.get("disable_notification")),
        })

    async def get_chat(self, chat_id):
        return self.chats[chat_id]

    async def get_chat_administrators(self, chat_id):
        return self.admins

    async def get_file(self, file_id):
        data = self.files[file_id]

        async def download_as_bytearray():
            return bytearray(data)

        return SimpleNamespace(file_size=len(data), download_as_bytearray=download_as_bytearray)

    async def delete_message(self, chat_id, message_id):
        if self.fail_with:
            raise self.fail_with
        self.deleted.append((chat_id, message_id))

    async def ban_chat_member(self, chat_id, user_id, **kwargs):
        if self.fail_with:
            raise self.fail_with
        self.banned.append((chat_id, user_id))

    async def unban_chat_member(self, chat_id, user_id, **kwargs):
        self.unbanned.append((chat_id, user_id))

    async def ban_chat_sender_chat(self, chat_id, sender_chat_id):
        if self.fail_with:
            raise self.fail_with
        self.banned_chats.append((chat_id, sender_chat_id))

    async def unban_chat_sender_chat(self, chat_id, sender_chat_id):
        self.unbanned_chats.append((chat_id, sender_chat_id))

    # The ☰ command list and the menu button at startup (bot/main.py).
    async def delete_my_commands(self, **kwargs):
        self.calls = [*getattr(self, "calls", []), "delete_my_commands"]

    async def set_chat_menu_button(self, **kwargs):
        self.calls = [*getattr(self, "calls", []), "set_chat_menu_button"]


class FakeMessage:
    """An incoming message; replies and later edits of a reply land in .replies,
    their inline keyboards in .markups."""

    def __init__(self, text: str = ""):
        self.text = text
        self.document = None
        self.reply_to_message = None
        self.replies: list[str] = []
        self.markups: list = []
        self.photos: list[bytes] = []
        self.deleted = False

    async def reply_text(self, text, **kwargs):
        self.replies.append(text)
        self.markups.append(kwargs.get("reply_markup"))
        return FakeSent(self)

    async def reply_photo(self, photo, **kwargs):
        self.photos.append(photo)

    async def delete(self):
        self.deleted = True


class FakeSent:
    """A message the bot sent: editing it is recorded on the message it replied to."""

    def __init__(self, parent: FakeMessage):
        self.parent = parent

    async def edit_text(self, text, **kwargs):
        self.parent.replies.append(text)
        self.parent.markups.append(kwargs.get("reply_markup"))


class FakeApplication:
    """application.create_task as the handlers use it: the coroutine runs as a
    task on the loop, and a test awaits .tasks[-1] to see its effect."""

    def __init__(self):
        self.tasks: list[asyncio.Task] = []

    def create_task(self, coroutine, update=None):
        task = asyncio.ensure_future(coroutine)
        self.tasks.append(task)
        return task


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
        self.markups: list = []

    async def answer(self, text=None, show_alert=False):
        self.answers.append({"text": text, "show_alert": show_alert})

    async def edit_message_text(self, text, **kwargs):
        self.edits.append(text)
        self.markups.append(kwargs.get("reply_markup"))


def buttons(markup) -> dict[str, str]:
    """callback_data -> label of an inline keyboard."""
    if markup is None:
        return {}
    return {b.callback_data: b.text for row in markup.inline_keyboard for b in row}


def labels(markup) -> list[str]:
    return [b.text for row in markup.inline_keyboard for b in row]


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
    """Insert a follower row collected `days_ago` days back (UTC) — counted
    from `now` when a test pins the clock, else from the real one."""

    def _insert(
        platform: str, count: int, days_ago: int = 0, source: str = "api", now: datetime | None = None,
    ) -> None:
        ts = ((now or utcnow()).astimezone(UTC) - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
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
        return SimpleNamespace(
            bot=bot, bot_data=bot_data, args=list(args), application=FakeApplication(), user_data={}
        )

    return _make

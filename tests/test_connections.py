"""Networks connected from the chat (bot/connections.py, 🔌 Подключения → «➕ …»):
the value is checked, kept in the database, laid over the config at once and
at startup, and «-» brings .env back."""

from __future__ import annotations

import dataclasses
import sqlite3
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from conftest import ADMIN_ID, STRANGER_ID, buttons
from telegram import (
    Chat,
    ChatMemberAdministrator,
    ChatMemberLeft,
    ChatMemberUpdated,
    Message,
    MessageOriginChannel,
    PhotoSize,
    Update,
    User,
)
from telegram.ext import Application, ApplicationHandlerStop, ConversationHandler

from bot import connections, handlers, i18n, ui
from bot.db import Database

YT_CHANNEL = "UC" + "a" * 22
YT_KEY = "AIza" + "x" * 35


@pytest.fixture
def bare(config):
    """A fresh install: only the bot token, no network in .env."""
    return dataclasses.replace(config, telegram_channel_id=None, youtube_api_key=None, youtube_channel_id=None,
                               instagram_username=None, linkedin_profile_url=None)


@pytest.fixture
def ctx(make_context, bare):
    context = make_context()
    context.bot_data["config"] = bare
    return context


async def _send(make_update, context, entry: str, *texts: str):
    """Press «➕ …», then send each text; returns the last update and its state."""
    start = make_update(callback=entry)
    assert await handlers.input_conv_start(start, context) == handlers.AWAITING_INPUT
    update = state = None
    for text in texts:
        update = make_update(text=text)
        state = await handlers.input_conv_value(update, context)
    return start, update, state


@pytest.mark.parametrize(("raw", "expected"), [
    ("@my_channel", "@my_channel"), ("my_channel", "@my_channel"), ("https://t.me/my_channel", "@my_channel"),
    ("t.me/my_channel/", "@my_channel"), ("-1001234567890", "-1001234567890"),
    ("my channel", None), ("@ab", None), ("https://example.com/my_channel", None), ("-42", None),
])
def test_telegram_channel_forms(raw, expected):
    assert connections.telegram_channel(raw) == expected


@pytest.mark.parametrize(("raw", "expected"), [
    (YT_CHANNEL, YT_CHANNEL), (f"https://www.youtube.com/channel/{YT_CHANNEL}", YT_CHANNEL),
    ("@handle", None), ("UCshort", None),
])
def test_youtube_channel_forms(raw, expected):
    assert connections.youtube_channel(raw) == expected


@pytest.mark.parametrize(("raw", "expected"), [
    ("@Some.Name", "some.name"), ("https://www.instagram.com/some_name/", "some_name"), ("two words", None),
])
def test_instagram_username_forms(raw, expected):
    assert connections.instagram_username(raw) == expected


@pytest.mark.parametrize(("raw", "expected"), [
    ("https://www.linkedin.com/in/some-name/", "https://www.linkedin.com/in/some-name/"),
    ("linkedin.com/in/some-name?utm=1", "https://www.linkedin.com/in/some-name/"),
    ("https://www.linkedin.com/company/acme/", None), ("https://example.com/in/x", None),
])
def test_linkedin_url_forms(raw, expected):
    assert connections.linkedin_url(raw) == expected


async def test_a_fresh_install_offers_every_network(bare, db):
    screen = await ui.connections(db, bare)
    assert set(buttons(screen.keyboard)) >= {"conn:tg", "conn:yt", "conn:ig", "conn:li"}
    assert buttons(screen.keyboard)["conn:tg"] == "➕ Telegram"
    assert ".env и перезапуском" not in screen.text


async def test_a_telegram_channel_is_checked_and_works_at_once(make_update, ctx, bare, db, monkeypatch):
    seen = []

    async def count(bot, channel):
        seen.append(channel)
        return 1234 if channel == "@real_channel" else None

    monkeypatch.setattr(handlers, "collect_telegram", count)
    start, update, state = await _send(make_update, ctx, "conn:tg", "nonsense !", "t.me/ghost_channel", "@real_channel")
    assert start.callback_query.edits[0].startswith("📣 Пришли @username канала")
    assert seen == ["@ghost_channel", "@real_channel"]                 # a malformed value never reaches Telegram
    assert state == ConversationHandler.END
    assert bare.telegram_channel_id == "@real_channel" and "telegram" in bare.enabled_platforms
    assert update.message.replies[0].startswith("✅ Telegram-канал @real_channel подключён: сейчас 1\xa0234")
    assert await db.get_setting("conn_telegram_channel_id") == "@real_channel"


async def test_a_channel_the_bot_cannot_see_keeps_the_step_open(make_update, ctx, bare, monkeypatch):
    async def count(bot, channel):
        return None

    monkeypatch.setattr(handlers, "collect_telegram", count)
    _, update, state = await _send(make_update, ctx, "conn:tg", "@ghost_channel")
    assert state == handlers.AWAITING_INPUT and bare.telegram_channel_id is None
    assert "Не вижу канал @ghost_channel" in update.effective_chat.sent[0]


async def test_youtube_takes_two_steps_and_the_key_leaves_the_chat(make_update, ctx, bare, db, monkeypatch):
    asked = []

    async def count(session, key, channel):
        asked.append((key, channel))
        return 128 if key == YT_KEY else None

    monkeypatch.setattr(handlers, "collect_youtube", count)
    start = make_update(callback="conn:yt")
    await handlers.input_conv_start(start, ctx)
    step1 = make_update(text=f"https://youtube.com/channel/{YT_CHANNEL}")
    assert await handlers.input_conv_value(step1, ctx) == handlers.AWAITING_INPUT
    assert step1.effective_chat.sent[0].startswith("🔑 Шаг 2 из 2") and not step1.message.deleted
    wrong = make_update(text="AIza" + "y" * 35)
    assert await handlers.input_conv_value(wrong, ctx) == handlers.AWAITING_INPUT
    assert wrong.message.deleted and "YouTube не отдал число" in wrong.effective_chat.sent[0]
    assert bare.youtube_api_key is None                                # nothing kept until the pair works
    good = make_update(text=YT_KEY)
    assert await handlers.input_conv_value(good, ctx) == ConversationHandler.END
    assert good.message.deleted and asked[-1] == (YT_KEY, YT_CHANNEL)
    assert (bare.youtube_channel_id, bare.youtube_api_key) == (YT_CHANNEL, YT_KEY) and "youtube" in bare.enabled_platforms
    assert good.message.replies[0].startswith("✅ YouTube подключён: сейчас 128")
    assert YT_KEY not in "".join(good.message.replies + good.effective_chat.sent)


async def test_instagram_and_linkedin_point_at_their_next_step(make_update, ctx, bare):
    _, update, state = await _send(make_update, ctx, "conn:ig", "https://instagram.com/Some.Name/")
    assert state == ConversationHandler.END and bare.instagram_username == "some.name"
    assert "Остался токен" in update.message.replies[0] and "ig" in buttons(update.message.markups[0])
    _, update, state = await _send(make_update, ctx, "conn:li", "not a link", "linkedin.com/in/some-name")
    assert state == ConversationHandler.END and bare.linkedin_profile_url == "https://www.linkedin.com/in/some-name/"
    assert "li" in buttons(update.message.markups[0])


async def test_the_chat_wins_over_env_survives_a_restart_and_a_dash_brings_env_back(make_update, make_context, config, db, monkeypatch):
    async def count(bot, channel):
        return 10

    monkeypatch.setattr(handlers, "collect_telegram", count)
    context = make_context()                                           # .env says @test_channel
    await connections.restore(config, db)
    await _send(make_update, context, "conn:tg", "@other_channel")
    assert config.telegram_channel_id == "@other_channel"

    restarted = dataclasses.replace(config, telegram_channel_id="@test_channel")
    await connections.restore(restarted, db)
    assert restarted.telegram_channel_id == "@other_channel"

    _, update, state = await _send(make_update, context, "conn:tg", "-")
    assert state == ConversationHandler.END and config.telegram_channel_id == "@test_channel"
    assert update.message.replies[0].startswith("Убрал то, что было задано в чате")
    again = dataclasses.replace(config, telegram_channel_id="@test_channel")
    await connections.restore(again, db)
    assert again.telegram_channel_id == "@test_channel"


async def test_the_youtube_key_stays_out_of_the_backup(config, db, tmp_path):
    await connections.save(config, db, youtube_channel_id=YT_CHANNEL, youtube_api_key=YT_KEY)
    path = str(tmp_path / "backup.db")
    await db.snapshot_without_secrets(path)
    with sqlite3.connect(path) as conn:
        kept = dict(conn.execute("SELECT key, value FROM settings WHERE key LIKE 'conn_%'").fetchall())
    assert kept == {"conn_youtube_channel_id": YT_CHANNEL}
    assert await Database(config.db_path).get_setting("conn_youtube_api_key") == YT_KEY


async def test_the_whole_flow_reads_in_english(make_update, ctx, bare, monkeypatch):
    async def count(bot, channel):
        return None

    monkeypatch.setattr(handlers, "collect_telegram", count)
    i18n.set_language("en")
    cyrillic = __import__("re").compile("[А-Яа-яЁё]")
    for entry in ("conn:tg", "conn:yt", "conn:ig", "conn:li"):
        start, update, _ = await _send(make_update, ctx, entry, "???")
        shown = start.callback_query.edits + update.effective_chat.sent + update.message.replies
        assert shown and not cyrillic.search(" ".join(shown)), entry
    _, update, _ = await _send(make_update, ctx, "conn:tg", "@ghost_channel")
    assert not cyrillic.search(update.effective_chat.sent[0])
    assert not cyrillic.search((await ui.connections(ctx.bot_data["db"], bare)).text)


# --- a private channel: no @username, and its -100… id is shown nowhere --------

PRIVATE = Chat(id=-1006025849509, type="channel", title="Мой канал")
ME = User(id=1000, first_name="Social Tracker", is_bot=True)
AT = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)


def _admin(user: User) -> ChatMemberAdministrator:
    return ChatMemberAdministrator(user, False, False, True, *[False] * 9)


def promoted(by: int = ADMIN_ID, *, was_admin: bool = False) -> Update:
    """The my_chat_member update Telegram sends when the bot is made a channel admin."""
    return Update(update_id=9, my_chat_member=ChatMemberUpdated(
        chat=PRIVATE, from_user=User(id=by, first_name="Owner", is_bot=False), date=AT,
        old_chat_member=_admin(ME) if was_admin else ChatMemberLeft(ME), new_chat_member=_admin(ME),
    ))


async def _count_private(bot, channel):
    return 2 if channel == str(PRIVATE.id) else None


async def test_the_bot_offers_the_channel_the_owner_made_it_an_admin_of(ctx, bot):
    with pytest.raises(ApplicationHandlerStop):
        await handlers.on_group_update(promoted(), ctx)
    [text] = bot.messages
    assert text.startswith("📣 Ты сделал меня администратором канала «Мой канал». Подключить его?")
    assert buttons(bot.markups[0])["conn:pick:-1006025849509"] == "✅ Подключить канал"


async def test_no_offer_for_new_rights_someone_else_or_a_second_channel(ctx, bot, bare):
    for update in (promoted(by=STRANGER_ID), promoted(was_admin=True)):
        with pytest.raises(ApplicationHandlerStop):
            await handlers.on_group_update(update, ctx)
    ctx.bot_data["config"] = dataclasses.replace(bare, telegram_channel_id="@test_channel")
    with pytest.raises(ApplicationHandlerStop):
        await handlers.on_group_update(promoted(), ctx)
    assert bot.messages == []


async def test_the_offer_button_connects_the_channel_by_its_title(make_update, ctx, bot, bare, monkeypatch):
    monkeypatch.setattr(handlers, "collect_telegram", _count_private)
    bot.chats[str(PRIVATE.id)] = SimpleNamespace(title="Мой канал")
    press = make_update(callback="conn:pick:-1006025849509")
    await handlers.on_callback(press, ctx)
    assert bare.telegram_channel_id == "-1006025849509"
    [screen] = press.callback_query.edits
    assert screen.startswith("✅ Telegram-канал «Мой канал» подключён: сейчас 2.\n")     # an admin: no hint
    assert "Telegram — «Мой канал» ·" in screen                                       # 🔌 names it too


async def test_the_offer_button_of_a_channel_the_bot_lost_connects_nothing(make_update, ctx, bare, monkeypatch):
    monkeypatch.setattr(handlers, "collect_telegram", _count_private)
    press = make_update(callback="conn:pick:-1009999999999")
    await handlers.on_callback(press, ctx)
    assert bare.telegram_channel_id is None and press.callback_query.edits == []
    assert press.callback_query.answers[0]["text"].startswith("❌ Не вижу этот канал")


async def test_a_post_forwarded_from_a_private_channel_connects_it(make_update, ctx, bot, bare, monkeypatch):
    monkeypatch.setattr(handlers, "collect_telegram", _count_private)
    bot.member_status = "left"
    await handlers.input_conv_start(make_update(callback="conn:tg"), ctx)
    forwarded = make_update()                  # a photo post: no text at all
    forwarded.message.text = None
    forwarded.message.forward_origin = MessageOriginChannel(date=AT, chat=PRIVATE, message_id=3)
    assert await handlers.input_conv_value(forwarded, ctx) == ConversationHandler.END
    assert bare.telegram_channel_id == "-1006025849509"
    # No title from Telegram: the id; not an admin: what that costs.
    assert forwarded.message.replies[0].startswith(
        "✅ Telegram-канал -1006025849509 подключён: сейчас 2. Чтобы видеть вступления, посты и реакции, "
        "добавь меня в администраторы канала.")


def test_the_input_step_takes_a_forwarded_post_without_text(config, tmp_path):
    app = Application.builder().token("123456:TEST").build()
    handlers.register_handlers(app, config, Database(str(tmp_path / "x.db")))
    [conv] = [h for hs in app.handlers.values() for h in hs
              if isinstance(h, ConversationHandler) and handlers.AWAITING_INPUT in h.states
              and any(getattr(s, "callback", None) is handlers.input_conv_value for s in h.states[handlers.AWAITING_INPUT])]
    photo = Message(1, AT, Chat(ADMIN_ID, "private"), photo=[PhotoSize("f", "u", 10, 10)],
                    forward_origin=MessageOriginChannel(date=AT, chat=PRIVATE, message_id=3))
    update = Update(1, message=photo)
    takers = [s.callback for s in conv.states[handlers.AWAITING_INPUT] if s.check_update(update)]
    assert takers == [handlers.input_conv_value]


async def test_an_invite_link_gets_told_what_works_instead(make_update, ctx, bare, monkeypatch):
    monkeypatch.setattr(handlers, "collect_telegram", _count_private)
    for link in ("https://t.me/+AbCdEf123", "t.me/joinchat/AbCdEf123"):
        _, update, state = await _send(make_update, ctx, "conn:tg", link)
        assert state == handlers.AWAITING_INPUT and bare.telegram_channel_id is None
        assert update.effective_chat.sent[0].startswith("❌ По ссылке-приглашению я не узнаю, какой это канал.")


async def test_the_offer_and_the_answers_read_in_english(ctx, bot):
    i18n.set_language("en")
    cyrillic = __import__("re").compile("[А-Яа-яЁё]")
    screen = ui.channel_offer("My channel", PRIVATE.id)
    assert not cyrillic.search(screen.text + " ".join(buttons(screen.keyboard).values()))



# --- the first value and the watchdog, right when a network is connected ------

async def test_a_connected_channel_has_its_first_value_and_the_watchdog_is_offered(
        make_update, ctx, bot, bare, db, monkeypatch):
    """«сейчас 2» is today's value at once — 🔌 says «собирается», not «первый
    сбор ещё не был» — and the watchdog the greeting promised after the first
    network comes below, once."""
    monkeypatch.setattr(handlers, "collect_telegram", _count_private)
    bot.chats[str(PRIVATE.id)] = SimpleNamespace(title="Мой канал")
    press = make_update(callback="conn:pick:-1006025849509")
    await handlers.on_callback(press, ctx)
    assert (await db.get_latest("telegram"))["count"] == 2
    assert "Telegram — «Мой канал» · ✅ собирается" in press.callback_query.edits[0]
    assert [m for m in bot.messages if m.startswith("⏱ Ещё один шаг — сторож")] != []
    sent = len(bot.messages)
    await handlers.on_callback(make_update(callback="conn:pick:-1006025849509"), ctx)
    assert len(bot.messages) == sent                                   # offered once, ever


async def test_a_reconnect_keeps_the_collected_history(make_update, ctx, bot, bare, db, monkeypatch):
    monkeypatch.setattr(handlers, "collect_telegram", _count_private)
    await db.upsert("telegram", 1500)                                  # collected before, today
    await handlers.on_callback(make_update(callback="conn:pick:-1006025849509"), ctx)
    assert (await db.get_latest("telegram"))["count"] == 1500          # the connect check doesn't overwrite it


async def test_no_watchdog_offer_when_one_is_set(make_update, ctx, bot, bare, db, monkeypatch):
    from bot import watchdog
    monkeypatch.setattr(handlers, "collect_telegram", _count_private)
    monkeypatch.setattr(watchdog, "url", lambda *a: _async("https://hc-ping.com/x"))
    await handlers.on_callback(make_update(callback="conn:pick:-1006025849509"), ctx)
    assert not [m for m in bot.messages if m.startswith("⏱")]


async def _async(value):
    return value

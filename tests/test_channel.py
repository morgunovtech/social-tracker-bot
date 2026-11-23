"""Life of the channel: what an admin bot's updates become, what the screen
and the report say, and that channel traffic is routed before everything."""

from __future__ import annotations

import dataclasses
import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from conftest import buttons
from telegram import (
    Chat,
    ChatInviteLink,
    ChatMemberLeft,
    ChatMemberMember,
    ChatMemberUpdated,
    Message,
    MessageReactionCountUpdated,
    PhotoSize,
    ReactionCount,
    ReactionTypeCustomEmoji,
    ReactionTypeEmoji,
    ReactionTypePaid,
    Update,
    User,
)
from telegram.ext import Application, ApplicationHandlerStop

from bot import handlers, monitors, ui
from bot.db import Database
from bot.monitors import channel
from bot.scheduler import build_stats

CHANNEL = Chat(id=-1001000, type="channel", username="test_channel")
OTHER = Chat(id=-1002000, type="channel", username="other")
NOW = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)


def user(uid: int = 5, name: str = "Иван", username: str | None = "ivan", is_bot: bool = False) -> User:
    return User(id=uid, first_name=name, is_bot=is_bot, username=username)


def joined(u: User | None = None, at: datetime = NOW, chat: Chat = CHANNEL, *, link: ChatInviteLink | None = None,
           request: bool = False, folder: bool = False) -> Update:
    u = u or user()
    return Update(update_id=1, chat_member=ChatMemberUpdated(
        chat=chat, from_user=u, date=at, old_chat_member=ChatMemberLeft(u), new_chat_member=ChatMemberMember(u),
        invite_link=link, via_join_request=request, via_chat_folder_invite_link=folder,
    ))


def left(u: User | None = None, at: datetime = NOW, chat: Chat = CHANNEL) -> Update:
    u = u or user()
    return Update(update_id=1, chat_member=ChatMemberUpdated(
        chat=chat, from_user=u, date=at, old_chat_member=ChatMemberMember(u), new_chat_member=ChatMemberLeft(u),
    ))


def post(message_id: int = 10, at: datetime = NOW, chat: Chat = CHANNEL, **fields) -> Update:
    return Update(update_id=2, channel_post=Message(message_id=message_id, date=at, chat=chat, **fields))


def reacted(message_id: int, counts: dict[str, int], at: datetime = NOW, chat: Chat = CHANNEL, *,
            custom: int = 0, paid: int = 0) -> Update:
    reactions = [ReactionCount(ReactionTypeEmoji(emoji), n) for emoji, n in counts.items()]
    if custom:
        reactions.append(ReactionCount(ReactionTypeCustomEmoji("5000"), custom))
    if paid:
        reactions.append(ReactionCount(ReactionTypePaid(), paid))
    return Update(update_id=3, message_reaction_count=MessageReactionCountUpdated(chat, message_id, at, reactions))


def link(name: str | None) -> ChatInviteLink:
    return ChatInviteLink("https://t.me/+abc", user(1, "Owner"), False, False, False, name=name)


# --- which chat, which event -------------------------------------------------

def test_the_channel_is_known_by_username_or_id(config):
    assert channel.is_channel(CHANNEL, config) and not channel.is_channel(OTHER, config)
    assert channel.is_channel(Chat(id=1, type="channel", username="TEST_CHANNEL"), config)
    by_id = dataclasses.replace(config, telegram_channel_id="-1001000")
    assert channel.is_channel(CHANNEL, by_id) and not channel.is_channel(OTHER, by_id)
    assert not channel.is_channel(None, config)
    assert not channel.is_channel(CHANNEL, dataclasses.replace(config, telegram_channel_id=None))


def test_member_events():
    event = channel.member_event(joined().chat_member)
    assert (event.kind, event.user_id, event.user_name, event.via, event.at) == ("join", 5, "Иван (@ivan)", "", NOW)
    assert channel.member_event(left(user(6, "Пётр", None)).chat_member).kind == "leave"
    assert channel.member_event(left(user(6, "Пётр", None)).chat_member).user_name == "Пётр"
    assert channel.member_event(joined(link=link("Из инсты")).chat_member).via == "Из инсты"
    assert channel.member_event(joined(link=link(None)).chat_member).via == channel.VIA_LINK
    assert channel.member_event(joined(request=True).chat_member).via == channel.VIA_REQUEST
    assert channel.member_event(joined(folder=True).chat_member).via == channel.VIA_FOLDER
    # A bot made admin is not a subscriber; a promotion moves nobody in or out.
    assert channel.member_event(joined(user(9, "Bot", "bot", is_bot=True)).chat_member) is None
    u = user()
    promoted = SimpleNamespace(
        chat=CHANNEL, date=NOW, old_chat_member=ChatMemberMember(u),
        new_chat_member=SimpleNamespace(status="administrator", user=u),
        invite_link=None, via_chat_folder_invite_link=False, via_join_request=False,
    )
    assert channel.member_event(promoted) is None
    # Restricted but still a member counts as a member.
    restricted = SimpleNamespace(status="restricted", is_member=True, user=u)
    came_back = SimpleNamespace(
        chat=CHANNEL, date=NOW, old_chat_member=ChatMemberLeft(u), new_chat_member=restricted,
        invite_link=None, via_chat_folder_invite_link=False, via_join_request=False,
    )
    assert channel.member_event(came_back).kind == "join"


def test_post_kinds_and_reaction_counts():
    assert channel.post_kind(post(text="hello").channel_post) == "text"
    assert channel.post_kind(post(photo=[PhotoSize("f", "u", 1, 1)], caption="pic").channel_post) == "photo"
    pinned = Message(message_id=1, date=NOW, chat=CHANNEL, text="x")
    assert channel.post_kind(post(pinned_message=pinned).channel_post) is None            # a service message
    counts = channel.reaction_counts(reacted(10, {"👍": 3, "❤": 1}, custom=2, paid=1).message_reaction_count)
    assert counts == {"👍": 3, "❤": 1, channel.CUSTOM_EMOJI: 2, channel.PAID: 1}
    assert channel.reactions_label('{"👍": 3, "❤": 5}') == "❤ 5 · 👍 3"
    assert channel.reactions_label("") == "" and channel.reactions_label("{") == ""


# --- recording ----------------------------------------------------------------

async def test_joins_leaves_and_their_sources_are_recorded_once(config, db):
    assert await channel.record(db, config, joined()) == "join"
    assert await channel.record(db, config, joined()) is None                     # re-delivered: already stored
    assert await channel.record(db, config, joined(user(6, "Анна"), link=link("Из инсты"))) == "join"
    assert await channel.record(db, config, joined(user(7, "Олег"), request=True)) == "join"
    assert await channel.record(db, config, left(user(8, "Пётр"), at=NOW + timedelta(minutes=1))) == "leave"
    assert await channel.record(db, config, joined(chat=OTHER)) is None            # another channel
    assert await channel.record(db, config, joined(user(9, "Bot", is_bot=True))) is None
    counts = await db.channel_counts(NOW - timedelta(days=1))
    assert counts == {"joins": 3, "leaves": 1, "posts": 0, "reactions": 0}
    assert await db.channel_sources(NOW - timedelta(days=1)) == [("", 1), ("request", 1), ("Из инсты", 1)]
    recent = await db.channel_recent_events(2)
    assert [(e["kind"], e["user_name"]) for e in recent] == [("leave", "Пётр (@ivan)"), ("join", "Олег (@ivan)")]
    assert await channel.has_data(db)


async def test_posts_and_their_reactions(config, db):
    assert await channel.record(db, config, post(10, text="hello")) == "post"
    assert await channel.record(db, config, post(10, text="hello")) is None       # re-delivered
    assert await channel.record(db, config, post(11, pinned_message=Message(1, NOW, CHANNEL, text="x"))) is None
    assert await channel.record(db, config, post(12, chat=OTHER, text="x")) is None
    assert await channel.record(db, config, reacted(10, {"👍": 3})) == "reactions"
    assert await channel.record(db, config, reacted(10, {"👍": 4, "❤": 1})) == "reactions"   # a snapshot, not a delta
    # A reaction on a post from before the watch: counted among the top posts, not as a publication.
    assert await channel.record(db, config, reacted(3, {"🔥": 9})) == "reactions"
    counts = await db.channel_counts(NOW - timedelta(days=1))
    assert counts["posts"] == 1 and counts["reactions"] == 5
    top = await db.channel_top_posts(NOW - timedelta(days=30), 3)
    assert [(p["message_id"], p["reactions"], p["posted_at"] is None) for p in top] == [(3, 9, True), (10, 5, False)]
    # The old post turns up later (an edit re-sent as a post is not expected, but the row heals).
    assert await db.add_channel_post(-1001000, 3, "text", NOW - timedelta(days=2))
    assert (await db.channel_counts(NOW - timedelta(days=3)))["posts"] == 2


async def test_switched_off_nothing_is_recorded(config, db):
    await monitors.toggle(db, channel.MONITOR_ID)
    assert await channel.record(db, config, joined()) is None
    assert await channel.record(db, config, post(10, text="x")) is None
    assert not await channel.has_data(db)
    assert await channel.report_line(db, config) is None


async def test_a_broken_update_is_logged_not_raised(config, db):
    broken = SimpleNamespace(chat_member=SimpleNamespace(chat=CHANNEL), channel_post=None, message_reaction_count=None)
    assert await channel.record(db, config, broken) is None


# --- what the owner reads ------------------------------------------------------

async def fill(config, db) -> None:
    await channel.record(db, config, joined())
    await channel.record(db, config, joined(user(6, "Анна", None), link=link("Из инсты")))
    await channel.record(db, config, left(user(8, "Пётр", None), at=NOW + timedelta(minutes=1)))
    await channel.record(db, config, post(10, text="hello"))
    await channel.record(db, config, reacted(10, {"👍": 3, "❤": 1}))


async def test_screen_and_report_line(config, db, monkeypatch):
    monkeypatch.setattr(channel, "utcnow", lambda: NOW + timedelta(hours=2))
    empty = await ui.channel_screen(db, config)
    assert empty.text.startswith("<b>📣 Канал @test_channel</b>") and "Пока пусто" in empty.text
    assert buttons(empty.keyboard) == {"home": "← Главная"}
    assert await channel.report_line(db, config) is None

    await fill(config, db)
    screen = await ui.channel_screen(db, config)
    assert "<b>За 24 часа</b>: +2 · −1 · 1 пост · 4 реакции" in screen.text
    assert "<b>За 30 дней</b>: +2 · −1 · 1 пост · 4 реакции" in screen.text
    assert "• по ссылке «Из инсты» — 1" in screen.text and "• напрямую — 1" in screen.text
    assert '• 👍 3 · ❤ 1 — <a href="https://t.me/test_channel/10">23.11</a>' in screen.text
    assert "− Пётр" in screen.text and "+ Анна — по ссылке «Из инсты»" in screen.text
    assert "Статистика" in screen.text
    assert await channel.report_line(db, config) == "📣 Канал за 7 дн.: +2 подписки · −1 отписка · 1 пост · 4 реакции"

    await monitors.toggle(db, channel.MONITOR_ID)
    assert "⬜ Выключено в /modules" in (await ui.channel_screen(db, config)).text
    assert await channel.report_line(db, config) is None

    unconfigured = dataclasses.replace(config, telegram_channel_id=None)
    assert "Не подключено" in (await ui.channel_screen(db, unconfigured)).text
    assert "ch" not in buttons((await ui.home(db, unconfigured)).keyboard)


async def test_the_report_carries_the_channel_line(config, db, insert, monkeypatch):
    monkeypatch.setattr(channel, "utcnow", lambda: NOW + timedelta(hours=2))
    insert("telegram", 1000)
    await fill(config, db)
    report, _ = await build_stats(db, config)
    assert "📣 Канал за 7 дн.: +2 подписки" in report
    assert report.index("Telegram") < report.index("📣 Канал")


async def test_the_command_and_the_button(config, db, make_update, make_context):
    update = make_update(text="/channel")
    await handlers.cmd_channel(update, make_context())
    assert update.message.replies[0].startswith("<b>📣 Канал")
    home = make_update()
    await handlers.cmd_home(home, make_context())
    assert buttons(home.message.markups[0])["ch"] == "📣 Канал"
    pressed = make_update(callback="ch")
    await handlers.on_callback(pressed, make_context())
    assert pressed.callback_query.edits[0].startswith("<b>📣 Канал")


# --- routing ---------------------------------------------------------------------

async def test_channel_updates_are_recorded_by_the_router(config, db, make_context):
    context = make_context()
    for update in (joined(), post(10, text="x"), reacted(10, {"👍": 1})):
        with pytest.raises(ApplicationHandlerStop):
            await handlers.on_group_update(update, context)
    counts = await db.channel_counts(NOW - timedelta(days=1))
    assert counts == {"joins": 1, "leaves": 0, "posts": 1, "reactions": 1}


def _first_handler(app: Application, update: Update):
    """What PTB would run first: the first matching handler of the lowest group."""
    for group in sorted(app.handlers):
        for handler in app.handlers[group]:
            if handler.check_update(update):
                return handler.callback
    return None


def test_group_and_channel_traffic_is_routed_before_everything_else(config, tmp_path):
    app = Application.builder().token("123456:TEST").build()
    handlers.register_handlers(app, config, Database(str(tmp_path / "x.db")))
    comment = Update(1, message=Message(1, NOW, Chat(-100, "supergroup"), from_user=user(), text="hi"))
    assert _first_handler(app, comment) is handlers.on_group_update
    assert _first_handler(app, joined()) is handlers.on_group_update
    # Each of the two early handlers has a group of its own: PTB runs one handler per group,
    # so two in one group would leave the second one never called.
    groups = {getattr(h, "callback", None): g for g, hs in app.handlers.items() for h in hs}
    assert groups[handlers.on_group_update] < groups[handlers.drop_stale_messages] < 0
    # Joins, leaves and reactions are not delivered unless asked for.
    assert {Update.CHAT_MEMBER, Update.MESSAGE_REACTION_COUNT, Update.CHANNEL_POST, Update.MESSAGE,
            Update.CALLBACK_QUERY} <= set(handlers.ALLOWED_UPDATES)


# --- the backup ---------------------------------------------------------------------

async def test_restore_merges_the_channel_history(config, db, tmp_path):
    await fill(config, db)
    backup = str(tmp_path / "backup.db")
    await db.snapshot_without_secrets(backup)
    fresh = Database(str(tmp_path / "fresh.db"))
    await fresh.init()
    await fresh.restore_from(backup)
    assert (await fresh.channel_counts(NOW - timedelta(days=1)))["joins"] == 2
    assert (await fresh.channel_top_posts(NOW - timedelta(days=30), 1))[0]["reactions"] == 4
    await fresh.restore_from(backup)                                              # twice: nothing doubles
    assert (await fresh.channel_counts(NOW - timedelta(days=1)))["joins"] == 2
    os.remove(backup)

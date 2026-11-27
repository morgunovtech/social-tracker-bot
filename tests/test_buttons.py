"""What the CJM review added: the reply keyboard, the action rows under
alerts and reports, the 🔌 Подключения screen, the home screen's chips, the
text-input conversations (a cookie, a token, a time zone by button) and a
restore from a file sent without a caption."""

from __future__ import annotations

import shutil
from datetime import timedelta
from types import SimpleNamespace

import pytest
from conftest import COOKIE, STRANGER_ID, buttons
from telegram.ext import ConversationHandler

from bot import callbacks as cb
from bot import handlers, main, monitors, notifier, scheduler, ui
from bot.db import Database
from bot.notifier import Priority, flush_queue, send
from bot.scheduler import CollectOutcome, _scheduled_job, send_alerts, setup_scheduler


@pytest.fixture
async def sched(bot, config, db):
    return await setup_scheduler(bot, config, db)


async def press(make_update, make_context, data: str, **context_kwargs):
    update = make_update(callback=data)
    await handlers.on_callback(update, make_context(**context_kwargs))
    return update.callback_query


def _document(source_path: str, name: str = "followers-2026-11-22.db", size: int = 1024):
    async def download_to_drive(path):
        shutil.copy(source_path, path)

    async def get_file():
        return SimpleNamespace(download_to_drive=download_to_drive)

    return SimpleNamespace(file_size=size, file_name=name, mime_type="application/octet-stream", get_file=get_file)


# --- the rows under alerts and reports -----------------------------------------

async def test_action_rows_follow_the_priority(bot, config, db):
    await send(bot, config, db, "🟠 x", Priority.NORMAL, actions=(cb.SECURITY,), monitor="profile")
    assert buttons(bot.markups[0]) == {
        "open:sec": "🛡 Безопасность", "mute:8h": "🔕 Тихо 8 ч", "mod:profile:off": "⚙️ Не присылать такие",
    }
    await send(bot, config, db, "🔴 x", Priority.CRITICAL, actions=(cb.SECURITY,), monitor="profile")
    assert buttons(bot.markups[1]) == {"open:sec": "🛡 Безопасность", "mute:8h": "🔕 Тихо 8 ч"}   # no switch-off for a 🔴
    await send(bot, config, db, "📊 report", Priority.DIGEST, actions=(cb.DYNAMICS, cb.CHANNEL))
    assert buttons(bot.markups[2]) == {"open:dyn": "📈 Динамика", "open:ch": "📣 Канал"}            # nothing to mute
    await send(bot, config, db, "plain")
    assert buttons(bot.markups[3]) == {"mute:8h": "🔕 Тихо 8 ч"}


async def test_the_digest_gets_one_row_for_all_its_items(bot, config, db):
    await notifier.set_mute(db, timedelta(hours=1))
    await send(bot, config, db, "🟠 one", actions=(cb.SECURITY,), monitor="profile")
    await send(bot, config, db, "🟠 two", actions=(cb.DYNAMICS,), monitor="followers")
    await send(bot, config, db, "📊 three", Priority.DIGEST, actions=(cb.DYNAMICS,))
    await notifier.set_mute(db, None)
    assert await flush_queue(bot, config, db) == 3
    (digest,) = bot.messages
    assert "1. " in digest and "3. " in digest                              # still one message
    shared = bot.markups[0].inline_keyboard[-1]
    assert {b.callback_data: b.text for b in shared} == {
        "open:sec": "🛡 Безопасность", "open:dyn": "📈 Динамика", "mute:8h": "🔕 Тихо 8 ч",
    }
    # The switch-offs stay with their items: «ℹ️ N» brings each one back with its own row.
    assert [b.text for b in bot.markups[0].inline_keyboard[0]] == ["ℹ️ 1", "ℹ️ 2"]


async def test_info_n_under_a_digest_sends_the_item_below_it(make_update, make_context, bot, config, db):
    await notifier.set_mute(db, timedelta(hours=1))
    full = "🟠 Telegram: −50 подписчиков за день\n\nЧто делать:\n• посмотреть 📈 Динамику"
    await send(bot, config, db, full, actions=(cb.DYNAMICS,), monitor="followers")
    await notifier.set_mute(db, None)
    await flush_queue(bot, config, db)
    data = next(b.callback_data for row in bot.markups[0].inline_keyboard for b in row if b.text == "ℹ️ 1")
    query = await press(make_update, make_context, data)
    assert query.edits == []                                                # the digest stays as it is
    assert bot.messages[-1].startswith("🕒 ") and bot.messages[-1].endswith(full)
    assert buttons(bot.markups[-1]) == {
        "open:dyn": "📈 Динамика", "mute:8h": "🔕 Тихо 8 ч", "mod:followers:off": "⚙️ Не присылать такие",
    }
    sent = len(bot.messages)
    query = await press(make_update, make_context, "dg:999")
    assert query.answers[0]["text"] == "Полного текста уже нет: я храню его 7 дн. после сводки."
    assert len(bot.messages) == sent


async def test_the_report_and_the_alerts_carry_their_rows(bot, config, db, insert, monkeypatch):
    async def _collect(b, c, database):
        report, has_change = await scheduler.build_report(database)
        return CollectOutcome(report=report, has_change=has_change)

    monkeypatch.setattr(scheduler, "collect_and_report", _collect)
    insert("telegram", 1000, 0)
    await db.set_setting("report_dow", "*")
    await _scheduled_job(bot, config, db, scheduler.AsyncIOScheduler(timezone=scheduler.UTC))
    assert buttons(bot.markups[0]) == {"open:dyn": "📈 Динамика", "open:sec": "🛡 Безопасность", "open:ch": "📣 Канал"}

    bot.messages.clear()
    bot.markups.clear()
    drop = CollectOutcome(report="", has_change=True, drops={"telegram": (1000, 900)})
    await send_alerts(bot, config, db, drop)
    assert buttons(bot.markups[0]) == {
        "open:dyn": "📈 Динамика", "mute:8h": "🔕 Тихо 8 ч", "mod:followers:off": "⚙️ Не присылать такие",
    }
    mixed = CollectOutcome(report="", has_change=True, drops={"youtube": (100, 50)}, errors={"linkedin_cookie_expired": True})
    await send_alerts(bot, config, db, mixed)
    # One message per problem, each with its own monitor's switch-off (BOT_PRINCIPLES §3).
    assert len(bot.messages) == 3 and bot.messages[1].startswith("🟠 LinkedIn cookie истёк")
    assert buttons(bot.markups[1]) == {
        "open:conn": "🔌 Подключения", "mute:8h": "🔕 Тихо 8 ч", "mod:collection:off": "⚙️ Не присылать такие",
    }
    assert "mod:followers:off" in buttons(bot.markups[2])


# --- the routes behind the rows ------------------------------------------------

async def test_open_sends_the_screen_as_a_new_message(make_update, make_context, bot, insert):
    insert("telegram", 1000, 0)
    query = await press(make_update, make_context, "open:sec")
    assert query.edits == [] and bot.messages[-1].startswith("<b>🛡 Безопасность")
    assert "home" in buttons(bot.markups[-1])
    query = await press(make_update, make_context, "open:nope")
    assert query.answers[0]["text"].startswith("Кнопка устарела") and bot.messages[-1].startswith("<b>📊")


async def test_mute_is_a_toast_under_an_alert_and_a_rerender_on_home(make_update, make_context, db):
    query = await press(make_update, make_context, "mute:8h")
    assert query.edits == [] and query.answers[0]["text"].startswith("🔕 Молчу до ")
    assert await notifier.mute_until(db) is not None
    query = await press(make_update, make_context, "mute:off:home")
    assert await notifier.mute_until(db) is None and query.edits[0].startswith("🔔 Снова пишу обо всём.")
    query = await press(make_update, make_context, "mute:8h:home")
    assert "🔔 Снять тишину" in buttons(query.markups[0]).values() and "🔕 Тишина до" in query.edits[0]


async def test_a_monitor_is_switched_off_from_its_alert_and_toggled_on_its_screen(make_update, make_context, db):
    query = await press(make_update, make_context, "mod:profile:off")
    assert query.edits == [] and query.answers[0]["text"].startswith("Профиль: выключено")
    assert not await monitors.is_switched_on(db, "profile")
    query = await press(make_update, make_context, "mod:comments:cm")
    assert query.edits[0].startswith("<b>💬 Комментарии") and not await monitors.is_switched_on(db, "comments")
    query = await press(make_update, make_context, "mod:channel:ch")
    assert not await monitors.is_switched_on(db, "channel")
    assert buttons(query.markups[0])["mod:channel:ch"] == "⬜ Жизнь канала" and "⬜ Выключено —" in query.edits[0]


async def test_backup_now(make_update, make_context, bot, db):
    await db.upsert("telegram", 1000)
    query = await press(make_update, make_context, "backup")
    assert query.answers[0]["text"].startswith("📦") and bot.documents[0]["filename"].startswith("followers-")


async def test_the_error_notice_carries_a_way_home(make_context, bot):
    from datetime import UTC, datetime

    from conftest import ADMIN_ID
    from telegram import Chat, Message, Update, User

    user = User(ADMIN_ID, "Owner", False)
    update = Update(1, message=Message(1, datetime.now(UTC), Chat(ADMIN_ID, "private"), from_user=user, text="/now"))
    context = make_context()
    context.error = RuntimeError("boom")
    await handlers.on_error(update, context)
    assert buttons(bot.markups[0]) == {"open:home": "🏠 Главная"}


# --- the reply keyboard ---------------------------------------------------------

async def test_the_three_reply_buttons_act(make_update, make_context, db):
    assert [b.text for row in ui.persistent_keyboard().keyboard for b in row] == ["🏠 Главная", "📖 Что я умею", "❓ Значки"]

    update = make_update(text="🏠 Главная")
    await handlers._reply_button(update, make_context())
    assert update.message.replies[0].startswith("<b>📊")
    assert {"now", "mute", "set"} <= set(buttons(update.message.markups[0]))       # refresh and silence: one tap

    update = make_update(text="📖 Что я умею")
    await handlers._reply_button(update, make_context())
    text = update.message.replies[0]
    assert text.startswith("<b>📖 Что я умею</b>") and buttons(update.message.markups[0]) == {"home": "🏠 Главная"}
    for name in handlers.COMMANDS:                                             # every command is listed
        assert f"/{name}" in text, name
    assert "/setcookie" in text and "/igtoken" in text and "/cancel" in text

    update = make_update(text="❓ Значки")
    await handlers._reply_button(update, make_context())
    text = update.message.replies[0]
    assert text.startswith("<b>❓ Значки</b>") and "🔴 нужно действие сейчас" in text and "Звонит только 🔴" in text


async def test_the_buttons_of_the_old_keyboard_keep_working(make_update, make_context, db, monkeypatch):
    async def collect(*args, **kwargs):
        return CollectOutcome(report="📊 r", has_change=False)

    monkeypatch.setattr(handlers, "collect_and_report", collect)
    update = make_update(text="🔄 Обновить")
    await handlers._reply_button(update, make_context())
    assert update.message.replies[0].startswith("⏳") and update.message.replies[-1].startswith("<b>📊 r</b>")

    update = make_update(text="🔕 Тихо 8 ч")
    await handlers._reply_button(update, make_context())
    assert update.message.replies[0].startswith("🔕 Молчу до") and await notifier.mute_until(db) is not None
    assert "mute:off:home" in buttons(update.message.markups[0])

    for old in ("🏠 Меню", "📊 Меню", "🏠 Menu"):
        update = make_update(text=old)
        await handlers._reply_button(update, make_context())
        assert "<b>📊" in update.message.replies[0], old
    assert handlers._REFRESH_BUTTON.filter(SimpleNamespace(text="🔄 Обновить"))
    assert not handlers._REFRESH_BUTTON.filter(SimpleNamespace(text="Обновить"))

    # Mid-conversation the buttons win over the number parser.
    update = make_update(text="🔕 Тихо 8 ч")
    assert await handlers.li_conv_menu(update, make_context()) == ConversationHandler.END
    assert update.message.replies[0].startswith("🔕 Молчу до")


# --- the home screen ------------------------------------------------------------

async def test_home_shows_the_last_collection_and_what_is_left_to_set_up(make_update, make_context, db, insert,
                                                                         monkeypatch):
    monkeypatch.setenv("REPORT_TZ", "")            # a fresh install: no zone on the host either
    update = make_update()
    await handlers.cmd_home(update, make_context())
    text, markup = update.message.replies[0], update.message.markups[0]
    assert "🧭 Осталось настроить:" in text and "часовой пояс — пока UTC" in text and "LinkedIn — cookie" in text
    assert "🕒" not in text and {"set:tz", "conn"} <= set(buttons(markup))

    insert("telegram", 1000, 0)
    await db.set_setting("report_tz", "UTC")
    await db.upsert("linkedin", 100, source="manual")
    update = make_update()
    await handlers.cmd_home(update, make_context())
    text, markup = update.message.replies[0], update.message.markups[0]
    assert "🕒 Последний сбор: сегодня" in text and "🧭" not in text and "set:tz" not in buttons(markup)


# --- 🔌 Подключения ------------------------------------------------------------

async def test_connections_screen_states(config, db):
    screen = await ui.connections(db, config)
    assert "Telegram — @test_channel · ⏳ первый сбор ещё не был" in screen.text
    assert "➖ Instagram — не подключено\n" in screen.text
    assert "LinkedIn — https://www.linkedin.com/in/test/ · ✏️ число вручную" in screen.text
    assert buttons(screen.keyboard) == {
        "conn:ig": "➕ Instagram", "li": "💼 LinkedIn", "wd": "⏱ Сторож", "rep": "🔎 Репутация", "cm": "💬 Комментарии", "mail": "✉️ Письма безопасности",
        "conn:tg": "✏️ Telegram", "conn:yt": "✏️ YouTube", "conn:li": "✏️ LinkedIn", "home": "🏠 Главная"}
    await db.set_setting("linkedin_li_at", COOKIE)
    assert "🟠 подтверди первое число" in (await ui.connections(db, config)).text
    await db.upsert("linkedin", 4500, source="cookie")
    assert "LinkedIn — https://www.linkedin.com/in/test/ · ✅ собирается" in (await ui.connections(db, config)).text
    await db.set_setting("cookie_expired_alerted", "1")
    assert "🟠 cookie отклонён" in (await ui.connections(db, config)).text
    assert {"li:cookie", "li:enter", "conn"} <= set(buttons((await ui.linkedin(db, config)).keyboard))


async def test_no_command_list_and_the_new_keyboard_is_brought_once(bot, config, db, monkeypatch):
    async def nothing(*args, **kwargs):
        return None

    monkeypatch.setattr(main, "report_startup_changes", nothing)
    app = SimpleNamespace(bot=bot, bot_data={"config": config, "db": db})
    await main._post_init(app)
    app.bot_data["scheduler"].shutdown(wait=False)
    assert bot.calls == ["delete_my_commands", "set_chat_menu_button"]           # no ☰ list (§2)
    assert len(bot.messages) == 1 and bot.messages[0].startswith("Главные кнопки теперь под полем ввода")
    assert [b.text for row in bot.markups[0].keyboard for b in row] == ["🏠 Главная", "📖 Что я умею", "❓ Значки"]
    assert bot.silent == [True]
    assert not await handlers.show_keyboard_once(bot, config, db)                # once
    assert "connections" in handlers.COMMANDS and "icons" in handlers.COMMANDS


async def test_mute_picker_on_home(make_update, make_context, db):
    query = await press(make_update, make_context, "mute")
    assert query.edits[0].startswith("<b>🔕 Помолчать</b>") and "🔴" in query.edits[0]
    assert set(buttons(query.markups[0])) == {"mute:1h:home", "mute:4h:home", "mute:8h:home", "mute:1d:home", "home"}
    query = await press(make_update, make_context, "mute:4h:home")
    assert query.edits[0].startswith("🔕 Молчу до") and "mute:off:home" in buttons(query.markups[0])
    assert await notifier.mute_until(db) is not None


async def test_setcookie_and_igtoken_without_a_value_ask_for_it(make_update, make_context):
    for command, kind in (("setcookie", "cookie"), ("igtoken", "token")):
        update, context = make_update(text=f"/{command}"), make_context()
        assert await getattr(handlers, f"cmd_{command}")(update, context) == handlers.AWAITING_INPUT
        assert context.user_data["awaiting"] == kind
        assert update.message.replies[0].startswith("🔑 Пришли")
        assert buttons(update.message.markups[0]) == {"input:cancel": "✖️ Отмена"}


# --- a cookie, a token, a zone by button ------------------------------------------

async def test_a_cookie_by_button(make_update, make_context, db, monkeypatch):
    async def collect(session, profile_url=None, li_at=None, prev=None):
        return 4530, "cookie"

    monkeypatch.setattr(handlers, "collect_linkedin", collect)
    update, context = make_update(callback="li:cookie"), make_context()
    assert await handlers.input_conv_start(update, context) == handlers.AWAITING_INPUT
    assert update.callback_query.edits[0].startswith("🔑 Пришли cookie li_at") and context.user_data["awaiting"] == "cookie"
    assert "input:cancel" in buttons(update.callback_query.markups[0])
    value = make_update(text=COOKIE)
    assert await handlers.input_conv_value(value, context) == ConversationHandler.END
    assert value.message.deleted and await db.get_setting("linkedin_li_at") == COOKIE
    assert "/linkedin 4530" in value.effective_chat.sent[-1]           # no baseline: confirm the first number


async def test_a_token_by_button(make_update, make_context, db):
    update, context = make_update(callback="ig:token"), make_context()
    await handlers.input_conv_start(update, context)
    value = make_update(text="short")
    assert await handlers.input_conv_value(value, context) == ConversationHandler.END
    assert value.message.deleted and "не похоже на токен" in value.effective_chat.sent[0]


async def test_a_time_zone_by_text(make_update, make_context, db, sched):
    update, context = make_update(callback="set:tz:other"), make_context(scheduler=sched)
    await handlers.input_conv_start(update, context)
    bad = make_update(text="Mars/Olympus")
    assert await handlers.input_conv_value(bad, context) == handlers.AWAITING_INPUT
    assert bad.message.replies[0].startswith("Не знаю такой пояс")
    good = make_update(text="asia/tashkent")
    assert await handlers.input_conv_value(good, context) == ConversationHandler.END
    assert await db.get_setting("report_tz") == "Asia/Tashkent" and "Ташкент" in good.message.replies[0]
    assert "set:tz:Asia/Tashkent" in buttons((await ui.timezone(db, context.bot_data["config"])).keyboard)


async def test_a_stranger_cannot_start_an_input(make_update, make_context):
    update = make_update(user_id=STRANGER_ID, callback="li:cookie")
    assert await handlers.input_conv_start(update, make_context()) == ConversationHandler.END
    assert update.callback_query.answers[0]["show_alert"]


# --- a backup file without a caption -------------------------------------------------

async def test_a_backup_file_is_offered_for_a_restore(make_update, make_context, db, sched, tmp_path):
    backup = Database(str(tmp_path / "backup.db"))
    await backup.init()
    await backup.upsert("youtube", 128)
    update = make_update()
    update.message.document = _document(backup._db_path)
    await handlers.on_document(update, make_context())
    assert update.message.replies[0].startswith("Это бэкап базы?")
    assert set(buttons(update.message.markups[0])) == {"restore:yes", "restore:no"}

    confirm = make_update(callback="restore:yes")
    confirm.callback_query.message = SimpleNamespace(reply_to_message=SimpleNamespace(document=update.message.document))
    await handlers.on_callback(confirm, make_context(scheduler=sched))
    assert confirm.callback_query.edits[0].startswith("✅ Восстановлено, добавлено записей: 1.")
    assert (await db.get_latest("youtube"))["count"] == 128

    lost = await press(make_update, make_context, "restore:yes")        # the prompt's file is gone
    assert lost.answers[0]["text"].startswith("Файл не нашёл")
    no = await press(make_update, make_context, "restore:no")
    assert no.edits[0].startswith("Отменено.")


async def test_other_files_get_a_hint(make_update, make_context):
    update = make_update()
    update.message.document = SimpleNamespace(file_name="photo.jpg", mime_type="image/jpeg", file_size=10)
    await handlers.on_document(update, make_context())
    assert update.message.replies[0].startswith("Не знаю, что делать с этим файлом")

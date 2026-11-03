import shutil
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from conftest import ADMIN_ID, COOKIE, STRANGER_ID
from telegram import Chat, Message, Update, User
from telegram.error import BadRequest, Conflict, NetworkError
from telegram.ext import ApplicationHandlerStop, ConversationHandler

from bot import handlers
from bot.db import Database, utcnow
from bot.scheduler import CollectOutcome, setup_scheduler


@pytest.fixture
async def sched(bot, config, db):
    return await setup_scheduler(bot, config, db)


# --- access ------------------------------------------------------------------

async def test_strangers_are_denied(make_update, make_context):
    update = make_update(user_id=STRANGER_ID)
    await handlers.cmd_stats(update, make_context())
    assert update.message.replies == ["⛔ Доступ запрещён."]


async def test_stranger_button_press_is_answered_once_with_the_alert(make_update, make_context):
    update = make_update(user_id=STRANGER_ID, callback="stats")
    await handlers.on_callback(update, make_context())
    assert update.callback_query.answers == [{"text": "⛔ Доступ запрещён.", "show_alert": True}]
    assert update.callback_query.edits == []


# --- reading -----------------------------------------------------------------

async def test_stats_and_buttons(make_update, make_context, insert):
    insert("telegram", 1000, 0)
    update = make_update()
    await handlers.cmd_stats(update, make_context())
    assert "Telegram: 1,000" in update.message.replies[0]

    press = make_update(callback="stats")
    await handlers.on_callback(press, make_context())
    assert press.callback_query.answers == [{"text": None, "show_alert": False}]
    assert "Telegram: 1,000" in press.callback_query.edits[0]


async def test_history_command(make_update, make_context, insert):
    insert("telegram", 1000, 0)
    update = make_update()
    await handlers.cmd_history(update, make_context("telegram", "7"))
    assert update.message.replies[0].startswith("📊 Telegram")

    for args in (("all", "365"), ("all", "0"), ("all", "-5")):
        update = make_update()
        await handlers.cmd_history(update, make_context(*args))
        assert "от 1 до 90" in update.message.replies[0]

    update = make_update()
    await handlers.cmd_history(update, make_context("instagram", "7"))
    assert "Неизвестная платформа" in update.message.replies[0]


async def test_stats_show_the_security_score_while_hygiene_is_on(make_update, make_context, db, insert):
    insert("telegram", 1000, 0)
    update = make_update()
    await handlers.cmd_stats(update, make_context())
    assert "🛡 Безопасность: 0/10 — /security" in update.message.replies[0]

    await db.set_setting("monitor_hygiene", "off")
    update = make_update()
    await handlers.cmd_stats(update, make_context())
    assert "🛡" not in update.message.replies[0]


# --- security & modules ------------------------------------------------------

async def test_security_checklist_flow(make_update, make_context, db):
    update = make_update()
    await handlers.cmd_security(update, make_context())
    assert update.message.replies[0].startswith("🛡 Безопасность — 0/10")

    press = make_update(callback="sec:edit:youtube")
    await handlers.on_callback(press, make_context())
    assert "Пароль вводить не нужно" in press.callback_query.edits[0]

    for data in ("sec:set:youtube:2fa:app", "sec:set:youtube:backup:yes", "sec:pwd:youtube:30"):
        press = make_update(callback=data)
        await handlers.on_callback(press, make_context())
    assert "1. Двухфакторная защита: приложение/ключ" in press.callback_query.edits[0]
    assert "5. Последняя смена пароля: 30 дн. назад" in press.callback_query.edits[0]
    assert await db.get_setting("hygiene_reviewed_at") == utcnow().date().isoformat()

    press = make_update(callback="sec")
    await handlers.on_callback(press, make_context())
    assert "YouTube (Google-аккаунт канала) — 7/10" in press.callback_query.edits[0]


@pytest.mark.parametrize(
    "data",
    ["sec:set:youtube:2fa:maybe", "sec:set:youtube:nope:yes", "sec:pwd:youtube:7", "sec:edit:myspace", "sec:x"],
)
async def test_forged_security_callbacks_change_nothing(make_update, make_context, db, data):
    press = make_update(callback=data)
    await handlers.on_callback(press, make_context())
    assert press.callback_query.edits == []
    assert await db.get_setting("hygiene_reviewed_at") is None


async def test_modules_screen_and_toggle(make_update, make_context, db):
    update = make_update()
    await handlers.cmd_modules(update, make_context())
    text = update.message.replies[0]
    assert "✅ Telegram — @test_channel" in text
    assert "⚪ Письма безопасности — нужно: SECURITY_MAIL_URL" in text

    press = make_update(callback="mod:profile")
    await handlers.on_callback(press, make_context())
    assert "⏸ Профиль" in press.callback_query.edits[0]
    assert await db.get_setting("monitor_profile") == "off"


async def test_history_buttons(make_update, make_context, insert):
    insert("youtube", 128, 0)
    press = make_update(callback="history:youtube")
    await handlers.on_callback(press, make_context())
    assert "Выберите период" in press.callback_query.edits[0]
    press = make_update(callback="history:all:7")
    await handlers.on_callback(press, make_context())
    assert "128" in press.callback_query.edits[0]


# --- collecting --------------------------------------------------------------

@pytest.mark.parametrize("via_button", [False, True])
async def test_manual_collect_sends_alerts(make_update, make_context, bot, monkeypatch, via_button):
    async def collect(*args, **kwargs):
        return CollectOutcome(report="📊 report", has_change=True, spikes={"youtube": (126, 226)})

    monkeypatch.setattr(handlers, "collect_and_report", collect)
    if via_button:
        update = make_update(callback="now")
        await handlers.on_callback(update, make_context())
        assert update.callback_query.edits[-1] == "📊 report"
    else:
        update = make_update()
        await handlers.cmd_now(update, make_context())
        assert update.message.replies[-1] == "📊 report"
    assert any("наплыв ботов" in m for m in bot.messages)


# --- manual LinkedIn ---------------------------------------------------------

async def test_linkedin_command(make_update, make_context, db):
    update = make_update()
    await handlers.cmd_linkedin(update, make_context("4520"))
    latest = await db.get_latest("linkedin")
    assert (latest["count"], latest["source"]) == (4520, "manual")

    update = make_update()
    await handlers.cmd_linkedin(update, make_context("many"))
    assert "целое число" in update.message.replies[0]


async def test_linkedin_conversation(make_update, make_context, db):
    update = make_update(text="4 520")
    assert await handlers.li_conv_number(update, make_context()) == ConversationHandler.END
    assert (await db.get_latest("linkedin"))["count"] == 4520

    update = make_update(text="abc")
    assert await handlers.li_conv_number(update, make_context()) == handlers.LI_AWAITING_NUMBER


# --- settings ----------------------------------------------------------------

async def test_settime(make_update, make_context, db, sched):
    update = make_update()
    await handlers.cmd_settime(update, make_context("09:30", scheduler=sched))
    assert await db.get_setting("report_time") == "09:30"
    assert str(sched.get_job("scheduled_report").trigger.fields[5]) == "9"   # hour field

    update = make_update()
    await handlers.cmd_settime(update, make_context("25:00", scheduler=sched))
    assert "Неверный формат" in update.message.replies[0]


async def test_setday(make_update, make_context, db, sched):
    update = make_update()
    await handlers.cmd_setday(update, make_context("Mon-Fri", scheduler=sched))
    assert await db.get_setting("report_dow") == "mon-fri"
    assert "Пн–Пт" in update.message.replies[0]

    update = make_update()
    await handlers.cmd_setday(update, make_context("someday", scheduler=sched))
    assert update.message.replies[0].startswith("❌")


async def test_quiet_mode_command_and_toggle(make_update, make_context, db):
    await handlers.cmd_setquiet(make_update(), make_context("on"))
    assert await db.get_setting("quiet_if_no_change") == "1"
    press = make_update(callback="quiet:toggle")
    await handlers.on_callback(press, make_context())
    assert await db.get_setting("quiet_if_no_change") == "0"
    assert "Настройки" in press.callback_query.edits[0]


# --- cookie ------------------------------------------------------------------

@pytest.fixture
def fake_linkedin(monkeypatch):
    calls: list[dict] = []
    result = {"value": (4530, "cookie")}

    async def collect(session, profile_url=None, li_at=None, prev=None):
        calls.append({"li_at": li_at, "prev": prev})
        return result["value"]

    monkeypatch.setattr(handlers, "collect_linkedin", collect)
    return result, calls


async def test_setcookie_deletes_the_message_even_when_rejected(make_update, make_context, db, fake_linkedin):
    result, _ = fake_linkedin
    update = make_update()
    await handlers.cmd_setcookie(update, make_context("short"))
    assert update.message.deleted and "слишком короткое" in update.effective_chat.sent[0]

    result["value"] = (None, "cookie_expired")
    update = make_update()
    await handlers.cmd_setcookie(update, make_context(COOKIE))
    assert update.message.deleted and "LinkedIn отклонил cookie" in update.effective_chat.sent[-1]
    assert await db.get_setting("linkedin_li_at") is None


async def test_setcookie_saves_cookie_but_guards_the_baseline(make_update, make_context, db, insert, fake_linkedin):
    result, calls = fake_linkedin
    insert("linkedin", 4500, 3)
    result["value"] = (120000, "cookie")                       # someone else's counter
    update = make_update()
    await handlers.cmd_setcookie(update, make_context(COOKIE))
    assert calls[-1] == {"li_at": COOKIE, "prev": 4500}
    assert await db.get_setting("linkedin_li_at") == COOKIE
    assert (await db.get_latest("linkedin"))["count"] == 4500
    assert "число не записано" in update.effective_chat.sent[-1]

    result["value"] = (4530, "cookie")
    await handlers.cmd_setcookie(make_update(), make_context(COOKIE))
    assert (await db.get_latest("linkedin"))["count"] == 4530


async def test_cookieage(make_update, make_context, db):
    update = make_update()
    await handlers.cmd_cookieage(update, make_context())
    assert "не настроен" in update.message.replies[0]

    await db.set_setting("linkedin_li_at", COOKIE)
    await db.set_setting("linkedin_li_at_set_at", "2026-01-01T00:00:00+00:00")
    update = make_update()
    await handlers.cmd_cookieage(update, make_context())
    assert "дней назад" in update.message.replies[0]


# --- restore -----------------------------------------------------------------

def _document(source_path: str, size: int = 1024):
    async def download_to_drive(path):
        shutil.copy(source_path, path)

    async def get_file():
        return SimpleNamespace(download_to_drive=download_to_drive)

    return SimpleNamespace(file_size=size, get_file=get_file)


async def test_restore_without_a_file_explains_how(make_update, make_context):
    update = make_update(text="/restore")
    await handlers.cmd_restore(update, make_context())
    assert "ответь командой /restore" in update.message.replies[0]


async def test_restore_as_reply_to_the_backup(make_update, make_context, db, sched, tmp_path):
    backup = Database(str(tmp_path / "backup.db"))
    await backup.init()
    await backup.upsert("youtube", 128)
    await backup.set_setting("report_time", "09:15")

    update = make_update(text="/restore")
    update.message.reply_to_message = SimpleNamespace(document=_document(backup._db_path))
    await handlers.cmd_restore(update, make_context(scheduler=sched))

    assert update.message.replies[-1].startswith("✅ Восстановлено: +1 записей")
    assert (await db.get_latest("youtube"))["count"] == 128
    assert str(sched.get_job("scheduled_report").trigger.fields[5]) == "9"   # backup's report time applied


async def test_restore_rejects_a_foreign_file(make_update, make_context, tmp_path):
    junk = tmp_path / "junk.db"
    junk.write_text("not a database " * 100)
    update = make_update()
    update.message.document = _document(str(junk))
    await handlers.cmd_restore(update, make_context())
    assert update.message.replies[-1].startswith("❌ Не похоже на бэкап")


async def test_restore_refuses_files_telegram_cannot_serve(make_update, make_context, tmp_path):
    update = make_update()
    update.message.document = _document(str(tmp_path / "x.db"), size=handlers.RESTORE_MAX_BYTES + 1)
    await handlers.cmd_restore(update, make_context())
    assert "20 МБ" in update.message.replies[0]


# --- errors ------------------------------------------------------------------

def _real_update(user_id: int) -> Update:
    user = User(user_id, "someone", is_bot=False)
    chat = Chat(user_id, Chat.PRIVATE)
    return Update(1, message=Message(1, datetime.now(UTC), chat, from_user=user, text="/now"))


async def test_errors_reach_the_admin_only(make_context, bot):
    context = make_context()
    context.error = RuntimeError("boom")
    await handlers.on_error(_real_update(ADMIN_ID), context)
    assert bot.messages == ["⚠️ Не получилось: RuntimeError. Подробности в логах."]

    await handlers.on_error(_real_update(STRANGER_ID), context)
    await handlers.on_error(None, context)                         # job/polling errors: log only
    assert len(bot.messages) == 1


async def test_polling_conflict_during_deploy_is_quiet(make_context, bot):
    context = make_context()
    context.error = Conflict("terminated by other getUpdates request")
    await handlers.on_error(None, context)
    assert bot.messages == []


async def test_polling_network_error_is_quiet(make_context, bot, caplog):
    context = make_context()
    context.error = NetworkError("httpx.ConnectError")
    await handlers.on_error(None, context)
    assert bot.messages == [] and "retrying" in caplog.text and "Traceback" not in caplog.text


# --- updates queued during a restart -----------------------------------------

async def test_late_button_answer_does_not_block_the_action(make_update, make_context, insert):
    insert("telegram", 1000, 0)
    press = make_update(callback="stats")

    async def too_old(*args, **kwargs):
        raise BadRequest("Query is too old and response timeout expired or query id is invalid")

    press.callback_query.answer = too_old
    await handlers.on_callback(press, make_context())
    assert "Telegram: 1,000" in press.callback_query.edits[0]      # pressed during the restart, still done


async def test_other_answer_errors_still_surface(make_update, make_context):
    press = make_update(callback="stats")

    async def broken(*args, **kwargs):
        raise BadRequest("Chat not found")

    press.callback_query.answer = broken
    with pytest.raises(BadRequest, match="Chat not found"):
        await handlers.on_callback(press, make_context())


@pytest.mark.parametrize(("age_minutes", "dropped"), [(1, False), (9, False), (11, True), (600, True)])
async def test_queued_messages_are_handled_unless_stale(make_update, make_context, age_minutes, dropped):
    update = make_update(text="/now")
    update.message.date = utcnow() - timedelta(minutes=age_minutes)
    if dropped:
        with pytest.raises(ApplicationHandlerStop):
            await handlers.drop_stale_messages(update, make_context())
    else:
        assert await handlers.drop_stale_messages(update, make_context()) is None


async def test_button_presses_are_never_dropped_as_stale(make_update, make_context):
    # A press has no send time of its own: the menu it sits on may be days old.
    assert await handlers.drop_stale_messages(make_update(callback="stats"), make_context()) is None

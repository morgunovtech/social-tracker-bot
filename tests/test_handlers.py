import pytest
from conftest import COOKIE, STRANGER_ID
from telegram.ext import ConversationHandler

from bot import handlers
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

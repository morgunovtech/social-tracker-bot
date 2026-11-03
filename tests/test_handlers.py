import shutil
from collections import deque
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from types import SimpleNamespace

import pytest
from conftest import ADMIN_ID, COOKIE, STRANGER_ID, buttons, labels
from telegram import Chat, Message, Update, User
from telegram.error import BadRequest, Conflict, NetworkError
from telegram.ext import ApplicationHandlerStop, ConversationHandler

from bot import handlers, ui
from bot.db import Database, utcnow
from bot.scheduler import CollectOutcome, setup_scheduler

NBSP = " "


@pytest.fixture
async def sched(bot, config, db):
    return await setup_scheduler(bot, config, db)


async def press(make_update, make_context, data: str, **context_kwargs):
    update = make_update(callback=data)
    await handlers.on_callback(update, make_context(**context_kwargs))
    return update.callback_query


class _TelegramHTML(HTMLParser):
    """Fails on what Telegram refuses to parse: unknown or unbalanced tags."""

    ALLOWED = {"b", "i", "u", "s", "code", "pre", "a", "blockquote"}

    def __init__(self):
        super().__init__()
        self.stack: list[str] = []

    def handle_starttag(self, tag, attrs):
        assert tag in self.ALLOWED, f"<{tag}> is not Telegram HTML"
        self.stack.append(tag)

    def handle_endtag(self, tag):
        assert self.stack and self.stack.pop() == tag, f"unbalanced </{tag}>"


def assert_telegram_html(text: str) -> None:
    parser = _TelegramHTML()
    parser.feed(text)
    parser.close()
    assert parser.stack == [], f"unclosed {parser.stack}"


# --- access ------------------------------------------------------------------

async def test_strangers_are_denied(make_update, make_context):
    update = make_update(user_id=STRANGER_ID)
    await handlers.cmd_home(update, make_context())
    assert update.message.replies == ["⛔ Доступ запрещён."]

    update = make_update(user_id=STRANGER_ID)
    await handlers.cmd_start(update, make_context())
    assert update.message.replies == ["Это личный бот: он отвечает только своему владельцу."]


async def test_stranger_button_press_is_answered_once_with_the_alert(make_update, make_context):
    update = make_update(user_id=STRANGER_ID, callback="home")
    await handlers.on_callback(update, make_context())
    assert update.callback_query.answers == [{"text": "⛔ Доступ запрещён.", "show_alert": True}]
    assert update.callback_query.edits == []


# --- navigation --------------------------------------------------------------

async def test_every_button_answers_once_and_leads_back(make_update, make_context, bot, insert, monkeypatch):
    """Walk the whole menu from the home screen: no dead button, no dead end."""
    insert("telegram", 1000, 1)
    insert("telegram", 1010, 0)
    insert("youtube", 128, 0)

    async def collect(*args, **kwargs):
        return CollectOutcome(report="📊 Подписчики · сегодня", has_change=False)

    monkeypatch.setattr(handlers, "collect_and_report", collect)

    start = make_update()
    await handlers.cmd_home(start, make_context())
    seen: set[str] = set()
    queue = deque(buttons(start.message.markups[0]))
    while queue:
        data = queue.popleft()
        if data in seen:
            continue
        seen.add(data)
        assert len(data.encode()) <= 64, data                       # Telegram's callback_data limit
        if data == ui.LI_ENTER:                                     # the conversation's entry point
            continue
        photos = len(bot.photos)
        query = await press(make_update, make_context, data)
        assert len(query.answers) == 1, data                        # answered exactly once
        assert query.edits or query.answers[0]["text"] or len(bot.photos) > photos, f"{data} did nothing"
        for text, markup in zip(query.edits, query.markups, strict=True):
            assert_telegram_html(text)
            targets = buttons(markup)
            if markup is not None and data not in (ui.HOME, ui.NOW):
                assert any(label.startswith("← ") for label in targets.values()), f"{data}: no way back"
            queue.extend(targets)
    assert {ui.DYNAMICS, ui.TABLE, ui.SECURITY, "sec:ask:youtube:pwd", "set:hour:9", ui.MONITORS, ui.HELP} <= seen


async def test_home_is_the_report_with_the_next_run(make_update, make_context, insert):
    insert("telegram", 1000, 0)
    update = make_update()
    await handlers.cmd_home(update, make_context())
    text = update.message.replies[0]
    assert text.startswith("<b>📊 Подписчики") and f"Telegram — 1{NBSP}000" in text
    assert "⏭ Следующий отчёт:" in text and "UTC" in text
    assert {"now", "dyn", "sec", "set", "help"} <= set(buttons(update.message.markups[0]))


async def test_start_greets_and_sets_the_menu_button(make_update, make_context):
    update = make_update()
    await handlers.cmd_start(update, make_context())
    greeting, home = update.message.replies
    assert "Пока всё в порядке, я молчу" in greeting
    assert update.message.markups[0].keyboard[0][0].text == ui.MENU_BUTTON_TEXT
    assert home.startswith("<b>📊 Подписчики")


def test_menu_button_of_older_versions_still_works():
    for label in (ui.MENU_BUTTON_TEXT, *ui.LEGACY_MENU_BUTTON_TEXTS):
        assert handlers._MENU_BUTTON.pattern.match(label)
    assert not handlers._MENU_BUTTON.pattern.match("Меню")


async def test_buttons_of_the_old_menu_open_the_new_one(make_update, make_context, insert):
    insert("telegram", 1000, 0)
    query = await press(make_update, make_context, "stats")         # renamed screen: mapped
    assert f"Telegram — 1{NBSP}000" in query.edits[0] and query.answers == [{"text": None, "show_alert": False}]

    query = await press(make_update, make_context, "history:all:7")
    assert "📋 Все платформы · 7 дн." in query.edits[0]

    query = await press(make_update, make_context, "quiet:toggle")  # gone: home, with a word why
    assert query.answers[0]["text"] == "Это меню устарело — вот актуальное"
    assert query.edits[0].startswith("<b>📊 Подписчики")


async def test_unknown_text_and_commands_get_a_hint(make_update, make_context):
    update = make_update(text="привет")
    await handlers.on_unknown_text(update, make_context())
    assert "/help" in update.message.replies[0] and update.message.markups[0].keyboard

    update = make_update(text="/foo")
    await handlers.on_unknown_command(update, make_context())
    assert update.message.replies == ["Такой команды нет. Все команды — в /help."]


# --- followers ---------------------------------------------------------------

async def test_history_command(make_update, make_context, insert):
    insert("telegram", 1000, 0)
    update = make_update()
    await handlers.cmd_history(update, make_context("telegram", "7"))
    assert "📋 Telegram · 7 дн." in update.message.replies[0]
    assert {"✅ Telegram", "YouTube", "✅ 7 дн.", "30 дн."} <= set(labels(update.message.markups[0]))

    update = make_update()
    await handlers.cmd_history(update, make_context())
    assert "📋 Все платформы · 7 дн." in update.message.replies[0]

    for args in (("all", "365"), ("all", "0"), ("all", "-5")):
        update = make_update()
        await handlers.cmd_history(update, make_context(*args))
        assert "от 1 до 90" in update.message.replies[0]

    update = make_update()
    await handlers.cmd_history(update, make_context("instagram", "7"))
    assert "Неизвестная платформа" in update.message.replies[0]


async def test_table_switches_platform_and_period_in_place(make_update, make_context, insert):
    insert("youtube", 128, 0)
    query = await press(make_update, make_context, "tbl:youtube:30")
    assert "📋 YouTube · 30 дн." in query.edits[0] and "<pre>" in query.edits[0]
    assert {"✅ YouTube", "✅ 30 дн.", "Все"} <= set(labels(query.markups[0]))

    query = await press(make_update, make_context, "tbl:myspace:9999")      # forged: the default table
    assert "📋 Все платформы · 7 дн." in query.edits[0]


async def test_week_command_sends_the_chart(make_update, make_context, insert):
    insert("telegram", 1000, 3)
    insert("telegram", 1010, 0)
    update = make_update()
    await handlers.cmd_week(update, make_context())
    assert update.message.replies[0].startswith("<b>📅 Неделя") and update.message.photos


async def test_chart_button_without_data_explains_why(make_update, make_context, bot):
    query = await press(make_update, make_context, "chart")
    assert "мало данных" in query.answers[0]["text"] and bot.photos == []


async def test_stats_show_the_security_score_while_hygiene_is_on(make_update, make_context, db, insert):
    insert("telegram", 1000, 0)
    update = make_update()
    await handlers.cmd_home(update, make_context())
    assert "🛡 Безопасность: 0 из 10 — /security" in update.message.replies[0]

    await db.set_setting("monitor_hygiene", "off")
    update = make_update()
    await handlers.cmd_home(update, make_context())
    assert "🛡 Безопасность:" not in update.message.replies[0]


# --- collecting --------------------------------------------------------------

@pytest.mark.parametrize("via_button", [False, True])
async def test_manual_collect_sends_alerts(make_update, make_context, bot, monkeypatch, via_button):
    async def collect(*args, **kwargs):
        return CollectOutcome(report="📊 report", has_change=True, spikes={"youtube": (126, 226)})

    monkeypatch.setattr(handlers, "collect_and_report", collect)
    if via_button:
        query = await press(make_update, make_context, "now")
        assert query.edits[0].startswith("⏳") and query.edits[-1].startswith("<b>📊 report</b>")
    else:
        update = make_update()
        await handlers.cmd_now(update, make_context())
        assert update.message.replies[0].startswith("⏳")                  # then edited in place
        assert update.message.replies[-1].startswith("<b>📊 report</b>")
    assert any("наплыв ботов" in m for m in bot.messages)


async def test_a_second_tap_while_collecting_does_not_collect_twice(make_update, make_context, monkeypatch):
    calls = []

    async def collect(*args, **kwargs):
        calls.append(1)
        return CollectOutcome(report="📊 report", has_change=False)

    monkeypatch.setattr(handlers, "collect_and_report", collect)
    context = make_context()
    lock = handlers._collect_lock(context)
    await lock.acquire()
    update = make_update(callback="now")
    await handlers.on_callback(update, context)
    assert update.callback_query.answers[0]["text"].startswith("Уже собираю") and calls == []
    lock.release()


async def test_failed_collect_keeps_the_menu(make_update, make_context, monkeypatch):
    async def collect(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(handlers, "collect_and_report", collect)
    query = await press(make_update, make_context, "now")
    assert query.edits[-1].startswith("⚠️ Собрать данные не получилось") and "now" in buttons(query.markups[-1])


# --- security ----------------------------------------------------------------

async def test_checklist_is_asked_one_question_at_a_time(make_update, make_context, db):
    update = make_update()
    await handlers.cmd_security(update, make_context())
    assert update.message.replies[0].startswith("<b>🛡 Безопасность: 0 из 10</b>")
    assert buttons(update.message.markups[0])["sec:edit:youtube"] == "❓ YouTube · не заполнено"

    query = await press(make_update, make_context, "sec:edit:youtube")
    assert "Пароль вводить не нужно" in query.edits[0]
    assert buttons(query.markups[0])["sec:ask:youtube:2fa"] == "❓ 2FA: не отмечено"

    query = await press(make_update, make_context, "sec:ask:youtube:2fa")
    assert "вопрос 1 из 5" in query.edits[0] and "Как включена двухфакторная защита?" in query.edits[0]

    query = await press(make_update, make_context, "sec:set:youtube:2fa:app")
    assert query.answers[0]["text"] == "Сохранено"
    assert "вопрос 2 из 5" in query.edits[0]                         # straight on to the next one

    for data in ("sec:set:youtube:backup:yes", "sec:set:youtube:recovery:no", "sec:set:youtube:unique:yes"):
        query = await press(make_update, make_context, data)
    assert "вопрос 5 из 5" in query.edits[0]
    query = await press(make_update, make_context, "sec:pwd:youtube:30")
    assert query.edits[0].startswith("<b>🛡 YouTube: 8 из 10</b>")      # all marked: back to the list
    labels = buttons(query.markups[0])
    assert labels["sec:ask:youtube:2fa"] == "✅ 2FA: приложение/ключ"
    assert labels["sec:ask:youtube:recovery"] == "⚠️ Почта и телефон актуальны: нет"
    assert labels["sec:ask:youtube:pwd"] == "✅ Смена пароля: 30 дн. назад"
    assert await db.get_setting("hygiene_reviewed_at") == utcnow().date().isoformat()

    query = await press(make_update, make_context, "sec:set:youtube:2fa:sms")   # editing one: back to the list
    assert query.edits[0].startswith("<b>🛡 YouTube: 6 из 10</b>")

    query = await press(make_update, make_context, "sec")
    assert "⚠️ YouTube (Google-аккаунт канала) — 6 из 10" in query.edits[0]


@pytest.mark.parametrize(
    "data",
    [
        "sec:set:youtube:2fa:maybe", "sec:set:youtube:nope:yes", "sec:pwd:youtube:7",
        "sec:edit:myspace", "sec:ask:youtube:nope", "sec:x",
    ],
)
async def test_forged_security_callbacks_change_nothing(make_update, make_context, db, data):
    query = await press(make_update, make_context, data)
    assert query.edits == [] and len(query.answers) == 1
    assert await db.get_setting("hygiene_reviewed_at") is None


# --- monitors ----------------------------------------------------------------

async def test_monitors_screen_and_toggle(make_update, make_context, db):
    update = make_update()
    await handlers.cmd_modules(update, make_context())
    text = update.message.replies[0]
    assert "✅ Telegram — @test_channel" in text
    assert "➖ Письма безопасности — нужно: SECURITY_MAIL_URL" in text
    assert "mod:mail" not in buttons(update.message.markups[0])          # unavailable: no switch

    query = await press(make_update, make_context, "mod:profile")
    assert "⬜ Профиль" in query.edits[0] and query.answers[0]["text"] == "Профиль: выключено"
    assert buttons(query.markups[0])["mod:profile"] == "⬜ Профиль"
    assert await db.get_setting("monitor_profile") == "off"


# --- manual LinkedIn ---------------------------------------------------------

async def test_linkedin_command(make_update, make_context, db):
    update = make_update()
    await handlers.cmd_linkedin(update, make_context("4520"))
    latest = await db.get_latest("linkedin")
    assert (latest["count"], latest["source"]) == (4520, "manual")
    assert update.message.replies[0].startswith(f"✅ LinkedIn: 4{NBSP}520 — сохранено")

    update = make_update()
    await handlers.cmd_linkedin(update, make_context("many"))
    assert "целое число" in update.message.replies[0]


async def test_linkedin_conversation(make_update, make_context, db):
    update = make_update(text="4 520")
    assert await handlers.li_conv_number(update, make_context()) == ConversationHandler.END
    assert (await db.get_latest("linkedin"))["count"] == 4520

    update = make_update(text="abc")
    assert await handlers.li_conv_number(update, make_context()) == handlers.LI_AWAITING_NUMBER
    assert "не похоже на число" in update.message.replies[0]


async def test_a_far_off_linkedin_number_is_confirmed_first(make_update, make_context, db, insert):
    insert("linkedin", 4520, 1, source="manual")
    update = make_update(text="45200")                                    # an extra zero
    assert await handlers.li_conv_number(update, make_context()) == ConversationHandler.END
    assert "Проверь число" in update.message.replies[0]
    assert (await db.get_latest("linkedin"))["count"] == 4520
    assert "li:save:45200" in buttons(update.message.markups[0])

    query = await press(make_update, make_context, "li:save:45200")
    assert (await db.get_latest("linkedin"))["count"] == 45200 and query.answers[0]["text"] == "Сохранено"


async def test_linkedin_input_button_shows_only_while_it_is_typed_by_hand(make_update, make_context, db):
    update = make_update()
    await handlers.cmd_home(update, make_context())
    assert ui.LI_ENTER in buttons(update.message.markups[0])

    await db.set_setting("linkedin_li_at", COOKIE)
    update = make_update()
    await handlers.cmd_home(update, make_context())
    assert ui.LI_ENTER not in buttons(update.message.markups[0])

    await db.set_setting("cookie_expired_alerted", "1")                   # the cookie died
    update = make_update()
    await handlers.cmd_home(update, make_context())
    assert ui.LI_ENTER in buttons(update.message.markups[0])


async def test_another_button_mid_input_abandons_it(make_update, make_context, insert):
    insert("telegram", 1000, 0)
    update = make_update(callback="sec")
    assert await handlers.li_conv_other_button(update, make_context()) == ConversationHandler.END
    assert update.callback_query.edits[0].startswith("<b>🛡 Безопасность")


async def test_cancel_returns_home(make_update, make_context):
    update = make_update(callback=ui.LI_CANCEL)
    assert await handlers.li_conv_cancel(update, make_context()) == ConversationHandler.END
    assert update.callback_query.answers[0]["text"] == "Отменено"
    assert update.callback_query.edits[0].startswith("<b>📊 Подписчики")


# --- settings ----------------------------------------------------------------

async def test_settime(make_update, make_context, db, sched):
    update = make_update()
    await handlers.cmd_settime(update, make_context("09:30", scheduler=sched))
    assert await db.get_setting("report_time") == "09:30"
    assert str(sched.get_job("scheduled_report").trigger.fields[5]) == "9"   # hour field
    assert update.message.replies[0].startswith("✅ Отчёт теперь в 09:30 UTC")

    for args in (("25:00",), ("8",), ("08:00", "extra")):
        update = make_update()
        await handlers.cmd_settime(update, make_context(*args, scheduler=sched))
        assert "Неверный формат" in update.message.replies[0]

    update = make_update()
    await handlers.cmd_settime(update, make_context(scheduler=sched))       # no time: the picker
    assert "🕗 Время отчёта" in update.message.replies[0]


async def test_hour_picker(make_update, make_context, db, sched):
    query = await press(make_update, make_context, "set:time", scheduler=sched)
    assert buttons(query.markups[0])["set:hour:8"] == "✅ 08:00" and "11:00 по Москве" in query.edits[0]
    query = await press(make_update, make_context, "set:hour:19", scheduler=sched)
    assert await db.get_setting("report_time") == "19:00"
    assert str(sched.get_job("scheduled_report").trigger.fields[5]) == "19"
    assert query.answers[0]["text"] == "Отчёт будет приходить в 19:00 UTC"
    assert "в 19:00 UTC" in query.edits[0]


async def test_setday(make_update, make_context, db, sched):
    update = make_update()
    await handlers.cmd_setday(update, make_context("Mon-Fri", scheduler=sched))
    assert await db.get_setting("report_dow") == "mon-fri"
    assert update.message.replies[0].startswith("✅ Отчёт: по будням")

    update = make_update()
    await handlers.cmd_setday(update, make_context("someday", scheduler=sched))
    assert update.message.replies[0].startswith("❌")


async def test_day_toggles_and_presets(make_update, make_context, db):
    query = await press(make_update, make_context, "set:days")
    assert buttons(query.markups[0])["set:day:sat"] == "✅ Сб" and "по субботам" in query.edits[0]

    await press(make_update, make_context, "set:day:mon")
    assert await db.get_setting("report_dow") == "mon,sat"
    query = await press(make_update, make_context, "set:day:sat")
    assert await db.get_setting("report_dow") == "mon" and "по понедельникам" in query.edits[0]

    query = await press(make_update, make_context, "set:day:mon")           # the last day stays
    assert query.answers[0]["text"] == "Нужен хотя бы один день" and query.edits == []
    assert await db.get_setting("report_dow") == "mon"

    query = await press(make_update, make_context, "set:days:sat,sun")
    assert await db.get_setting("report_dow") == "sat,sun" and buttons(query.markups[0])["set:days:sat,sun"] == "✅ Выходные"
    query = await press(make_update, make_context, "set:days:junk")
    assert query.edits == [] and await db.get_setting("report_dow") == "sat,sun"


async def test_quiet_mode_command_and_toggle(make_update, make_context, db):
    await handlers.cmd_setquiet(make_update(), make_context("on"))
    assert await db.get_setting("quiet_if_no_change") == "1"
    query = await press(make_update, make_context, "set:quiet")
    assert await db.get_setting("quiet_if_no_change") == "0"
    assert "Настройки" in query.edits[0] and query.answers[0]["text"] == "Тихий режим выключен"
    assert buttons(query.markups[0])["set:quiet"] == "⬜ Тихий режим"


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
    assert_telegram_html(update.effective_chat.sent[-1])

    result["value"] = (4530, "cookie")
    await handlers.cmd_setcookie(make_update(), make_context(COOKIE))
    assert (await db.get_latest("linkedin"))["count"] == 4530


async def test_cookieage(make_update, make_context, db):
    update = make_update()
    await handlers.cmd_cookieage(update, make_context())
    assert "cookie не задан" in update.message.replies[0]

    await db.set_setting("linkedin_li_at", COOKIE)
    await db.set_setting("linkedin_li_at_set_at", (utcnow() - timedelta(days=40)).isoformat())
    update = make_update()
    await handlers.cmd_cookieage(update, make_context())
    assert "установлен 40 дн. назад" in update.message.replies[0]


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

    assert update.message.replies[-1].startswith("✅ Восстановлено, добавлено записей: 1.")
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
    assert len(bot.messages) == 1 and "(RuntimeError)" in bot.messages[0] and "Попробуй ещё раз" in bot.messages[0]

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


async def test_a_failing_screen_still_answers_the_press(make_update, make_context, monkeypatch):
    async def broken(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(ui, "settings", broken)
    update = make_update(callback="set")
    with pytest.raises(RuntimeError):
        await handlers.on_callback(update, make_context())
    assert len(update.callback_query.answers) == 1                  # no endless spinner on the button


# --- updates queued during a restart -----------------------------------------

async def test_late_button_answer_does_not_block_the_action(make_update, make_context, insert):
    insert("telegram", 1000, 0)
    update = make_update(callback="home")

    async def too_old(*args, **kwargs):
        raise BadRequest("Query is too old and response timeout expired or query id is invalid")

    update.callback_query.answer = too_old
    await handlers.on_callback(update, make_context())
    assert f"Telegram — 1{NBSP}000" in update.callback_query.edits[0]      # pressed during the restart, still done


async def test_other_answer_errors_still_surface(make_update, make_context):
    update = make_update(callback="home")

    async def broken(*args, **kwargs):
        raise BadRequest("Chat not found")

    update.callback_query.answer = broken
    with pytest.raises(BadRequest, match="Chat not found"):
        await handlers.on_callback(update, make_context())


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
    assert await handlers.drop_stale_messages(make_update(callback="home"), make_context()) is None

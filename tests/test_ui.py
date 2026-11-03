from datetime import UTC, datetime

import pytest
from conftest import buttons

from bot import ui
from bot.monitors import hygiene


@pytest.mark.parametrize(
    ("dow", "days", "pretty"),
    [
        ("*", ui.DOW_ORDER, "каждый день"),
        ("mon-fri", ui.DOW_ORDER[:5], "по будням"),
        ("mon,tue,wed,thu,fri", ui.DOW_ORDER[:5], "по будням"),
        ("sat,sun", ["sat", "sun"], "по выходным"),
        ("sat", ["sat"], "по субботам"),
        ("mon,thu", ["mon", "thu"], "Пн, Чт"),
        ("mon,tue,wed,fri", ["mon", "tue", "wed", "fri"], "Пн–Ср, Пт"),
        ("fri-mon", ["mon", "fri", "sat", "sun"], "Пн, Пт–Вс"),     # a range across the weekend
    ],
)
def test_report_days_in_words(dow, days, pretty):
    assert ui.dow_days(dow) == list(days)
    assert ui.dow_pretty(dow) == pretty


def test_day_sets_are_stored_the_way_the_scheduler_reads_them():
    assert ui.dow_expr(set(ui.DOW_ORDER)) == "*"
    assert ui.dow_expr({"sat", "mon"}) == "mon,sat"


def test_next_report():
    wednesday = datetime(2026, 11, 4, 9, 0, tzinfo=UTC)
    assert ui.next_report("*", 10, 0, wednesday) == "сегодня в 10:00 UTC"
    assert ui.next_report("*", 8, 0, wednesday) == "завтра в 08:00 UTC"
    assert ui.next_report("sat", 8, 0, wednesday) == "сб 07.11 в 08:00 UTC"
    assert ui.next_report("wed", 8, 0, wednesday) == "ср 11.11 в 08:00 UTC"   # today's has passed


async def test_security_screen_shows_accounts_advice_and_events(config, db):
    await hygiene.set_answer(db, "telegram", "2fa", "off")
    await db.add_event("e1", "Google", "new_login", "🚨 Google: новый вход <в> аккаунт\n«Security alert»")
    screen = await ui.security(db, config)
    assert screen.text.startswith("<b>🛡 Безопасность: 0 из 10</b>")
    assert "⚠️ Telegram (аккаунт владельца канала) — 0 из 10" in screen.text
    assert "❓ YouTube (Google-аккаунт канала) — не заполнено" in screen.text
    assert "Что сделать в первую очередь" in screen.text and "…и ещё" in screen.text
    assert "🚨 Google: новый вход &lt;в&gt; аккаунт" in screen.text            # quoted mail is escaped
    assert "«Security alert»" not in screen.text
    assert set(buttons(screen.keyboard)) == {"sec:edit:telegram", "sec:edit:youtube", "sec:edit:linkedin", "home"}


async def test_password_question_lists_the_ages(db):
    screen = await ui.question(db, ui.BY_ID["telegram"], hygiene.PASSWORD_KEY)
    assert "вопрос 5 из 5" in screen.text and hygiene.PASSWORD_QUESTION in screen.text
    assert "sec:pwd:telegram:0" in buttons(screen.keyboard)
    assert buttons(screen.keyboard)["sec:edit:telegram"] == "← Telegram"


async def test_screens_escape_what_they_quote(config, db):
    config = config.__class__(**{**config.__dict__, "telegram_channel_id": "@a<b>&c"})
    screen = await ui.monitors_screen(db, config)
    assert "@a&lt;b&gt;&amp;c" in screen.text


def test_noted_escapes_the_note():
    screen = ui.Screen("<b>x</b>").noted("✅ 1 < 2")
    assert screen.text == "✅ 1 &lt; 2\n\n<b>x</b>"

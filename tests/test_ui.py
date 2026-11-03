from datetime import UTC, datetime
from zoneinfo import ZoneInfo

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
    utc = ZoneInfo("UTC")
    assert ui.next_report("*", 10, 0, utc, wednesday) == "сегодня в 10:00 UTC"
    assert ui.next_report("*", 8, 0, utc, wednesday) == "завтра в 08:00 UTC"
    assert ui.next_report("sat", 8, 0, utc, wednesday) == "сб 07.11 в 08:00 UTC"
    assert ui.next_report("wed", 8, 0, utc, wednesday) == "ср 11.11 в 08:00 UTC"   # today's has passed


def test_next_report_in_the_owners_zone():
    """Friday 21:00 UTC is already Saturday 00:00 in Moscow."""
    moscow = ZoneInfo("Europe/Moscow")
    friday_evening = datetime(2026, 11, 6, 21, 0, tzinfo=UTC)
    assert ui.next_report("sat", 1, 0, moscow, friday_evening) == "сегодня в 01:00"
    assert ui.next_report("fri", 23, 0, moscow, friday_evening) == "пт 13.11 в 23:00"
    assert ui.next_report("sat", 1, 0, moscow, friday_evening.replace(hour=23)) == "сб 14.11 в 01:00"


@pytest.mark.parametrize(
    ("zone", "now", "name"),
    [
        ("UTC", datetime(2026, 1, 15, tzinfo=UTC), "UTC"),
        ("Europe/Moscow", datetime(2026, 1, 15, tzinfo=UTC), "Москва (UTC+3)"),
        ("Europe/Berlin", datetime(2026, 1, 15, tzinfo=UTC), "Берлин (UTC+1)"),
        ("Europe/Berlin", datetime(2026, 7, 15, tzinfo=UTC), "Берлин (UTC+2)"),           # summer time
        ("Europe/London", datetime(2026, 1, 15, tzinfo=UTC), "Лондон (UTC+0)"),
        ("America/New_York", datetime(2026, 1, 15, tzinfo=UTC), "Нью-Йорк (UTC−5)"),
        ("America/New_York", datetime(2026, 7, 15, tzinfo=UTC), "Нью-Йорк (UTC−4)"),
        ("Asia/Kolkata", datetime(2026, 1, 15, tzinfo=UTC), "Asia/Kolkata (UTC+5:30)"),  # not in the picker
    ],
)
def test_zone_names(zone, now, name):
    assert ui.tz_name(ZoneInfo(zone), now) == name


def test_report_time_says_utc_only_while_the_zone_is_utc():
    assert ui.clock(8, 0, ZoneInfo("UTC")) == "08:00 UTC"
    assert ui.clock(11, 30, ZoneInfo("Europe/Moscow")) == "11:30"


@pytest.mark.parametrize(
    ("before", "old", "new", "after"),
    [
        (("sat", 8, 0), "UTC", "Europe/Moscow", ("sat", 11, 0)),
        (("sat", 22, 0), "UTC", "Europe/Moscow", ("sun", 1, 0)),            # past midnight: the next day
        (("sat", 1, 0), "Europe/Moscow", "UTC", ("fri", 22, 0)),            # and back
        (("mon-fri", 22, 0), "UTC", "Europe/Moscow", ("tue,wed,thu,fri,sat", 1, 0)),
        (("sun", 22, 30), "UTC", "Asia/Kolkata", ("mon", 4, 0)),            # the week wraps around
        (("*", 23, 0), "UTC", "Asia/Vladivostok", ("*", 9, 0)),
        (("sat", 8, 0), "Europe/Moscow", "Europe/Moscow", ("sat", 8, 0)),
    ],
)
def test_a_new_zone_keeps_the_report_moment(before, old, new, after):
    january = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    assert ui.shift_schedule(*before, ZoneInfo(old), ZoneInfo(new), january) == after


def test_a_new_zone_keeps_the_moment_as_it_is_today_across_dst():
    berlin, utc = ZoneInfo("Europe/Berlin"), ZoneInfo("UTC")
    assert ui.shift_schedule("sat", 9, 0, berlin, utc, datetime(2026, 1, 15, tzinfo=UTC)) == ("sat", 8, 0)
    assert ui.shift_schedule("sat", 9, 0, berlin, utc, datetime(2026, 7, 15, tzinfo=UTC)) == ("sat", 7, 0)


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

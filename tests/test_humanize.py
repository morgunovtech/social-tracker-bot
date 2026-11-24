"""The one alert shape and the recovery with its duration (bot/humanize.py,
BOT_PRINCIPLES §3): pure functions."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from bot import humanize
from bot.db import utcnow
from bot.monitors import collection
from bot.scheduler import CollectOutcome

MSK = ZoneInfo("Europe/Moscow")


def test_alert_is_headline_meaning_steps_tech_in_that_order():
    text = humanize.alert("🟠 YouTube: не удаётся собрать данные 2 дн. подряд", "collection_failing", "HTTP 403", "")
    head, meaning, steps, tech = text.split("\n\n")
    assert head == "🟠 YouTube: не удаётся собрать данные 2 дн. подряд"
    assert meaning.startswith("В отчёте — последнее собранное число") and " Обычно это " in meaning
    assert steps.startswith("Что делать:\n• ") and steps.count("\n• ") == 2
    assert tech == "Тех.: HTTP 403"                                    # empty parts dropped
    assert humanize.headline(text) == head
    assert "Тех.:" not in humanize.alert("🟠 x", "token_missing")      # no details, no technical line


def test_every_explanation_has_meaning_cause_and_two_or_three_steps():
    for key, e in humanize.EXPLANATIONS.items():
        assert e.meaning.endswith("."), key
        assert e.cause and not e.cause.endswith("."), key             # «Обычно это {cause}.»
        assert 2 <= len(e.steps) <= 3, key


@pytest.mark.parametrize(
    ("minutes", "words"),
    [(0.2, "1 мин"), (40, "40 мин"), (60, "1 ч"), (90, "1 ч 30 мин"), (24 * 60, "1 дн."), (26 * 60 + 5, "1 дн. 2 ч")],
)
def test_durations_are_numbers(minutes, words):
    assert humanize.fmt_duration(minutes) == words


def test_span_names_the_times_and_the_dates_once_it_crosses_midnight():
    since = datetime(2026, 11, 24, 11, 3, tzinfo=UTC)
    assert humanize.span(since, since + timedelta(minutes=40), MSK) == "40 мин (14:03–14:43)"
    assert humanize.span(since, since + timedelta(hours=26), MSK) == "1 дн. 2 ч (24.11 14:03–25.11 16:03)"


def test_lasted_says_so_when_nobody_checked_in_between():
    now = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    every = timedelta(minutes=5)
    assert humanize.lasted(now - timedelta(minutes=40), now - timedelta(minutes=5), now, MSK, every) == (
        "40 мин (14:20–15:00)"
    )
    gap = humanize.lasted(now - timedelta(hours=5), now - timedelta(hours=3), now, MSK, every)
    assert gap.startswith("не меньше 2 ч (10:00–12:00)") and "с 12:00 до 15:00 я не проверял" in gap
    assert humanize.lasted(None, None, now, MSK) == ""


def test_recovery_is_one_message_with_how_long():
    assert humanize.recovery("✅ Почтовый воркер снова отвечает", "40 мин (14:03–14:43)", "Молчал") == (
        "✅ Почтовый воркер снова отвечает. Молчал 40 мин (14:03–14:43). Ничего делать не нужно."
    )
    assert humanize.recovery("✅ x", "") == "✅ x. Ничего делать не нужно."


async def test_an_alerted_collection_streak_ends_with_how_long_it_lasted(db):
    failed = CollectOutcome(report="", has_change=False, errors={"youtube": True})
    assert await collection.alert_lines(db, failed) == []                       # day 1
    await db.set_setting("fail_last_date_youtube", (utcnow().date() - timedelta(days=1)).isoformat())
    (alert,) = await collection.alert_lines(db, failed)                          # day 2: alerted
    assert alert.startswith("🟠 YouTube: не удаётся собрать данные 2 дн. подряд\n\n")
    await db.set_setting("fail_since_youtube", (utcnow() - timedelta(days=2, hours=1)).isoformat())
    working = CollectOutcome(report="", has_change=False, collected={"youtube": (130, "api")})
    (back,) = await collection.alert_lines(db, working, MSK)
    assert back.startswith("✅ YouTube: данные снова собираются. Не собирались 2 дн. 1 ч (")
    assert await collection.alert_lines(db, working, MSK) == []                 # told once


async def test_a_streak_that_was_never_alerted_ends_quietly(db):
    await collection.alert_lines(db, CollectOutcome(report="", has_change=False, errors={"youtube": True}))
    working = CollectOutcome(report="", has_change=False, collected={"youtube": (130, "api")})
    assert await collection.alert_lines(db, working) == []

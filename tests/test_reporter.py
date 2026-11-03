from datetime import timedelta

from bot import reporter
from bot.db import utcnow
from bot.reporter import (
    _crossed_milestone,
    _delta_str,
    _sparkline,
    build_history_all,
    build_history_table,
    build_month_report,
    build_report,
    build_week_report,
)

NBSP = reporter.NBSP


def _line(report: str, label: str) -> str:
    return next(line for line in report.splitlines() if line.startswith(f"{label} —"))


def _block(report: str, label: str) -> str:
    """A platform's lines in the report: from its heading to the next blank line."""
    lines = report.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"{label} —"))
    end = next((i for i in range(start, len(lines)) if not lines[i]), len(lines))
    return "\n".join(lines[start:end])


def test_numbers_read_the_russian_way():
    assert reporter._fmt(1234567) == f"1{NBSP}234{NBSP}567"      # «1,234» would read as a fraction
    assert reporter._signed(-5) == "−5" and reporter._signed(0) == "0"
    assert reporter._pct(6.666) == "+6,7%" and reporter._pct(-1.25) == "−1,2%"


def test_sparkline():
    assert _sparkline([]) == "" and _sparkline([5]) == ""
    assert _sparkline([3, 3, 3]) == "▁▁▁"
    assert _sparkline([0, 7]) == "▁█"
    assert len(_sparkline(list(range(14)))) == 14


def test_crossed_milestone_picks_highest_crossed():
    assert _crossed_milestone(None, 1000) is None
    assert _crossed_milestone(999, 1000) == 1000
    assert _crossed_milestone(1000, 1001) is None          # already past it
    assert _crossed_milestone(240, 1100) == 1000           # 250, 500, 1000 → highest
    assert _crossed_milestone(1100, 990) is None           # drops never cross


def test_delta_str():
    assert _delta_str(10, None) == ""
    assert _delta_str(1010, 10) == f"+1{NBSP}000"
    assert _delta_str(5, 10) == "−5"
    assert _delta_str(5, 5) == "0"


async def test_empty_report(db):
    text, has_change = await build_report(db)
    assert "Данных пока нет" in text and has_change is False


async def test_report_deltas_totals_and_highlights(db, insert):
    insert("telegram", 990, 30)
    insert("telegram", 995, 7)
    insert("telegram", 1000, 1)
    insert("telegram", 1010, 0)
    insert("youtube", 120, 7)
    insert("youtube", 128, 0)

    text, has_change = await build_report(db)

    assert has_change
    tg = _block(text, "Telegram")
    assert tg.startswith(f"Telegram — 1{NBSP}010")
    assert "+10 за день · +15 за неделю · +20 за месяц" in tg
    assert f"🎯 Telegram перешагнул 1{NBSP}000!" in text           # crossed within the week
    assert "🏆 Лидер недели: YouTube, +6,7%" in text
    assert "LinkedIn — пока нет данных" in text
    # Total: only deltas every platform with data can back.
    total = _block(text, "📈 Всего")
    assert f"1{NBSP}138" in total and "за неделю" in total and "за день" not in total


async def test_report_marks_stale_data_of_any_source(db, insert):
    insert("telegram", 1000, 5)                              # collection failing for days
    insert("youtube", 128, 0)
    insert("linkedin", 4800, 21, source="cookie")            # cookie died weeks ago
    text, _ = await build_report(db)
    assert "⚠️ данные от" in _block(text, "Telegram")
    assert "данные от" not in _block(text, "YouTube")
    assert "⚠️ данные от" in _block(text, "LinkedIn")


async def test_report_manual_linkedin_markers(db, insert):
    insert("linkedin", 4800, 2, source="manual")
    text, _ = await build_report(db, linkedin_stale_days=7)
    assert "\nвведено вручную " in _block(text, "LinkedIn")
    text, _ = await build_report(db, linkedin_stale_days=1)
    assert "⚠️ введено вручную" in _block(text, "LinkedIn") and "пора обновить" in text


async def test_report_flags_todays_failure_on_old_data(db, insert):
    insert("telegram", 1000, 1)
    text, _ = await build_report(db, errors={"telegram": True})
    assert "⚠️ сегодня собрать не удалось" in _block(text, "Telegram")


async def test_report_cookie_warnings(db, insert):
    insert("telegram", 1000, 0)
    text, _ = await build_report(db, errors={"linkedin_cookie_expired": True})
    assert "cookie истёк" in text.splitlines()[2]            # problems come first
    text, _ = await build_report(db, errors={"linkedin_cookie_aging": 340})
    assert "340 дн." in text


async def test_report_forecast_and_acceleration(db, insert):
    insert("telegram", 900, 30)
    insert("telegram", 910, 7)                               # ~3/week before
    insert("telegram", 960, 0)                               # +50 this week
    text, _ = await build_report(db)
    assert f"🔮 Telegram: 1{NBSP}000 примерно через 1 нед. (+50 в неделю)" in text
    assert "⚡ Telegram: растёт в" in text and "раза быстрее" in text


async def test_week_report_total_needs_every_baseline(db, insert):
    last_sunday = utcnow().date().weekday() + 1
    insert("telegram", 1000, last_sunday)
    insert("telegram", 1010, 0)
    insert("linkedin", 4520, 0)                              # added this week: no baseline
    text = await build_week_report(db)
    assert f"(+10, было 1{NBSP}000)" in _line(text, "Telegram")
    assert "за прошлую неделю данных нет" in _line(text, "LinkedIn")
    assert "за неделю" not in _line(text, "📈 Всего")         # was "+4 530 за неделю"

    insert("linkedin", 4500, last_sunday)
    text = await build_week_report(db)
    assert "(+30 за неделю)" in _line(text, "📈 Всего")


async def test_month_report_total_needs_every_baseline(db, insert):
    today = utcnow().date()
    prev_month_first = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    back = (today - prev_month_first).days
    insert("telegram", 900, back)
    insert("telegram", 1000, 0)
    insert("youtube", 500, back)
    insert("youtube", 550, 0)
    insert("linkedin", 4520, 0)                              # no start-of-month baseline

    text = await build_month_report(db)
    assert "нет данных на начало месяца" in _line(text, "LinkedIn")
    assert "за месяц" not in text
    assert "🏆 Лучшая платформа: Telegram, +11,1%" in text
    assert "(+100, +11,1%)" in _line(text, "Telegram")

    insert("linkedin", 4400, back)
    text = await build_month_report(db)
    assert "(+270 за месяц)" in text


async def test_month_report_without_data(db):
    assert await build_month_report(db) is None


async def test_history_tables(db, insert):
    insert("telegram", 1000, 1)
    insert("telegram", 1007, 0)
    table = await build_history_table(db, "telegram", 7)
    assert table.startswith("<b>📋 Telegram · 7 дн.</b>") and "+7" in table
    assert table.count("<pre>") == table.count("</pre>") == 1

    insert("youtube", 128, 0)
    combined = await build_history_all(db, 7)
    assert f"1{NBSP}007" in combined and "128" in combined
    assert "TG — Telegram, YT — YouTube\n" in combined                  # no LinkedIn column yet
    assert await build_history_table(db, "linkedin", 7) == (
        "<b>📋 LinkedIn · 7 дн.</b>\n\nЗа последние 7 дн. данных нет."
    )


async def test_longest_history_fits_one_telegram_message(db, insert):
    for day in range(91):
        for platform in reporter.PLATFORM_IDS:
            insert(platform, 10_000_000 + day, day)
    longest = max(
        [len(await build_history_all(db, 90))]
        + [len(await build_history_table(db, p, 90)) for p in reporter.PLATFORM_IDS]
    )
    assert longest < 4096


async def test_report_shows_placeholders_only_for_enabled_platforms(db, insert):
    insert("telegram", 1000, 0)
    text, _ = await build_report(db, platforms=["telegram"])
    assert "LinkedIn" not in text
    insert("youtube", 128, 3)                                # disabled now, but has data
    text, _ = await build_report(db, platforms=["telegram"])
    assert "YouTube — 128" in text

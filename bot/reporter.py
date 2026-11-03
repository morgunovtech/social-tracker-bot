from __future__ import annotations

import math
from datetime import date, datetime, timedelta

from bot.db import Database, parse_utc, utcnow
from bot.platforms import BY_ID, LABELS, PLATFORM_IDS

# Crossed when count moves up through one of these.
MILESTONES = [100, 250, 500, 1000, 2500, 5000, 10000, 25000, 50000, 100000, 250000, 500000, 1000000]

_BLOCKS = "▁▂▃▄▅▆▇█"

# Collected values are refreshed daily; older than this means collection is failing.
AUTO_STALE_DAYS = 2

NBSP = "\u00a0"
MINUS = "\u2212"


def _fmt(n: int) -> str:
    """1234567 → «1 234 567». Russian groups digits with a (no-break) space:
    «4,520» reads as a decimal fraction there."""
    return f"{n:,}".replace(",", NBSP).replace("-", MINUS)


def _signed(diff: int) -> str:
    if diff > 0:
        return f"+{_fmt(diff)}"
    if diff < 0:
        return f"{MINUS}{_fmt(-diff)}"
    return "0"


def _delta_str(current: int, previous: int | None) -> str:
    return "" if previous is None else _signed(current - previous)


def _pct(value: float) -> str:
    """+6.66 → «+6,7%»: the Russian decimal comma and a real minus sign."""
    return f"{value:+.1f}%".replace(".", ",").replace("-", MINUS)


def _deltas(current: int, day: int | None, week: int | None, month: int | None) -> str:
    """«+10 за день · +15 за неделю · +20 за месяц», only the periods with a baseline."""
    parts = [
        f"{delta} за {name}"
        for delta, name in (
            (_delta_str(current, day), "день"),
            (_delta_str(current, week), "неделю"),
            (_delta_str(current, month), "месяц"),
        )
        if delta
    ]
    return " · ".join(parts)


def _sparkline(values: list[int]) -> str:
    """Render a unicode sparkline. Empty if fewer than 2 points."""
    if len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    if lo == hi:
        return _BLOCKS[0] * len(values)
    span = hi - lo
    return "".join(_BLOCKS[int((v - lo) * 7 / span)] for v in values)


def _crossed_milestone(prev: int | None, current: int) -> int | None:
    """Highest milestone strictly between prev (exclusive) and current (inclusive)."""
    if prev is None or current <= prev:
        return None
    crossed = [m for m in MILESTONES if prev < m <= current]
    return max(crossed) if crossed else None


async def _platform_snapshot(
    db: Database, platform: str, today: date
) -> dict:
    """Fetch all comparison points for a platform in one place."""
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    latest = await db.get_latest(platform)
    if latest is None:
        return {"latest": None}

    day_row = await db.get_by_date(platform, yesterday)
    week_row = await db.get_by_date(platform, week_ago)
    month_row = await db.get_by_date(platform, month_ago)

    # Sparkline: last 14 days, take all available points
    history = await db.get_history(platform, 14)
    spark_values = [r["count"] for r in history[-14:]]

    return {
        "latest": latest,
        "day": day_row["count"] if day_row else None,
        "week": week_row["count"] if week_row else None,
        "month": month_row["count"] if month_row else None,
        "spark_values": spark_values,
    }


async def build_report(
    db: Database,
    errors: dict[str, bool | int] | None = None,
    linkedin_stale_days: int = 7,
    platforms: list[str] | None = None,
) -> tuple[str, bool]:
    """Build the textual report and return (text, has_meaningful_change).

    platforms are the enabled ones: only they get a placeholder line while
    they have no data (a disabled platform with old data is still shown).
    """
    # DB timestamps are UTC, so "today" must be the UTC date too.
    today = utcnow().date()
    errors = errors or {}

    lines: list[str] = [f"📊 Подписчики · {today.strftime('%d.%m.%Y')}"]

    # Problems first: they need an action, the numbers don't.
    if errors.get("linkedin_cookie_expired"):
        lines += ["", "⚠️ LinkedIn cookie истёк — обнови через /setcookie"]
    elif errors.get("linkedin_cookie_aging"):
        age = errors["linkedin_cookie_aging"]
        lines += ["", f"⏰ LinkedIn cookie живёт уже {age} дн. — пора обновить: /setcookie"]

    total_current = 0
    total_yesterday: int | None = 0
    total_week_ago: int | None = 0
    total_month_ago: int | None = 0
    has_any_data = False
    has_change = False

    week_growth: dict[str, float] = {}
    milestones_hit: list[tuple[str, int]] = []  # (platform_label, milestone)
    forecasts: list[str] = []
    accel_notes: list[str] = []

    for platform in PLATFORM_IDS:
        label = LABELS[platform]
        snap = await _platform_snapshot(db, platform, today)
        latest = snap["latest"]

        if latest is None:
            if platforms is not None and platform not in platforms:
                continue
            if platform == "linkedin":
                lines += ["", f"{label} — пока нет данных: число вводится вручную"]
            elif errors.get(platform):
                lines += ["", f"{label} — ⚠️ собрать не удалось"]
            continue

        has_any_data = True
        count = latest["count"]
        source = latest["source"]
        collected_at_str = latest["collected_at"]
        total_current += count

        day_count = snap["day"]
        week_count = snap["week"]
        month_count = snap["month"]

        if day_count is not None and count != day_count:
            has_change = True
        if week_count is not None and count != week_count:
            has_change = True

        # Milestone: detected vs week_ago (one-week scope) so weekly reports surface fresh crossings.
        crossed = _crossed_milestone(week_count, count)
        if crossed is not None:
            milestones_hit.append((label, crossed))

        # Week growth percentage for leader detection
        if week_count is not None and week_count > 0:
            week_growth[label] = (count - week_count) / week_count * 100

        # Forecast: at the current weekly rate, when is the next milestone?
        if week_count is not None:
            rate = count - week_count
            next_m = next((m for m in MILESTONES if m > count), None)
            if rate > 0 and next_m is not None:
                weeks_left = math.ceil((next_m - count) / rate)
                if weeks_left <= 26:  # beyond half a year the estimate is noise
                    forecasts.append(
                        f"🔮 {label}: {_fmt(next_m)} примерно через {weeks_left} нед. (+{_fmt(rate)} в неделю)"
                    )
            # Acceleration vs the average weekly rate over the prior ~3 weeks
            if month_count is not None:
                prev_avg = (week_count - month_count) / 3.3  # 23 days ≈ 3.3 weeks
                if prev_avg >= 3:  # too small a base gives meaningless ratios
                    if rate >= 2 * prev_avg:
                        ratio = f"{rate / prev_avg:.1f}".replace(".", ",")
                        accel_notes.append(f"⚡ {label}: растёт в {ratio} раза быстрее, чем обычно за месяц")
                    elif rate <= 0.5 * prev_avg:
                        accel_notes.append(
                            f"🐌 {label}: рост замедлился — {_signed(rate)} в неделю против обычных ~{prev_avg:.0f}"
                        )

        # One block per platform: the number, its changes, then what is off about it.
        head = f"{label} — {_fmt(count)}"
        spark = _sparkline(snap["spark_values"])
        if spark:
            head += f"  {spark}"
        block = ["", head]
        deltas = _deltas(count, day_count, week_count, month_count)
        if deltas:
            block.append(deltas)

        # Age marker: the latest value can be days old when collection keeps failing.
        try:
            collected_dt = parse_utc(collected_at_str)
            age_days = (utcnow() - collected_dt).days
        except (ValueError, TypeError):
            collected_dt = None
            age_days = 0
        date_str = collected_dt.strftime("%d.%m") if collected_dt else "?"

        if source == "manual":
            if age_days >= linkedin_stale_days:
                block.append(f"⚠️ введено вручную {date_str} — пора обновить")
            else:
                block.append(f"введено вручную {date_str}")
        elif age_days >= AUTO_STALE_DAYS:
            block.append(f"⚠️ данные от {date_str} — свежие собрать не удаётся")
        elif errors.get(platform):
            block.append("⚠️ сегодня собрать не удалось")

        lines += block

        if day_count is not None and total_yesterday is not None:
            total_yesterday += day_count
        else:
            total_yesterday = None
        if week_count is not None and total_week_ago is not None:
            total_week_ago += week_count
        else:
            total_week_ago = None
        if month_count is not None and total_month_ago is not None:
            total_month_ago += month_count
        else:
            total_month_ago = None

    if not has_any_data:
        lines += ["", "Данных пока нет — нажми «🔄 Обновить данные» или отправь /now."]
        return "\n".join(lines), False

    # Total: only the periods every platform with data can back.
    lines += ["", f"📈 Всего — {_fmt(total_current)}"]
    total_deltas = _deltas(total_current, total_yesterday, total_week_ago, total_month_ago)
    if total_deltas:
        lines.append(total_deltas)

    highlights: list[str] = [f"🎯 {label} перешагнул {_fmt(milestone)}!" for label, milestone in milestones_hit]
    if week_growth:
        leader_name, leader_pct = max(week_growth.items(), key=lambda kv: kv[1])
        if leader_pct > 0:
            highlights.append(f"🏆 Лидер недели: {leader_name}, {_pct(leader_pct)}")
    highlights.extend(accel_notes)
    highlights.extend(forecasts)
    if highlights:
        lines.append("")
        lines.extend(highlights)

    return "\n".join(lines), has_change


async def build_week_report(db: Database) -> str:
    today = utcnow().date()
    week_start = today - timedelta(days=today.weekday())
    last_week_end = week_start - timedelta(days=1)

    lines = [
        f"📅 Неделя {week_start.strftime('%d.%m')} — {today.strftime('%d.%m.%Y')}",
        "В сравнении с концом прошлой недели",
        "",
    ]

    total_now = 0
    total_prev = 0
    # The total delta is only meaningful when every counted platform has a baseline.
    prev_complete = True
    has_data = False

    for platform in PLATFORM_IDS:
        label = LABELS[platform]

        latest = await db.get_latest(platform)
        if latest is None:
            continue

        has_data = True
        count_now = latest["count"]
        total_now += count_now

        # Walk back from Sunday of last week up to 7 days,
        # taking the most recent available data point inside last week.
        prev_row = None
        for offset in range(7):
            prev_row = await db.get_by_date(platform, last_week_end - timedelta(days=offset))
            if prev_row:
                break

        count_prev = prev_row["count"] if prev_row else None
        if count_prev is not None:
            total_prev += count_prev
            lines.append(f"{label} — {_fmt(count_now)} ({_delta_str(count_now, count_prev)}, было {_fmt(count_prev)})")
        else:
            prev_complete = False
            lines.append(f"{label} — {_fmt(count_now)} (за прошлую неделю данных нет)")

    if not has_data:
        return "📅 Неделя\n\nДанных пока нет — недельное сравнение появится после первых сборов."

    lines.append("")
    total_line = f"📈 Всего — {_fmt(total_now)}"
    if prev_complete:
        total_line += f" ({_delta_str(total_now, total_prev)} за неделю)"
    lines.append(total_line)

    return "\n".join(lines)


_MONTH_NAMES = [
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
]


async def build_month_report(db: Database) -> str | None:
    """Digest for the month that just ended (intended for the 1st of the month).

    Compares the latest counts against the first available data point of the
    previous month. Returns None when there is nothing to report.
    """
    today = utcnow().date()
    prev_month_last = today.replace(day=1) - timedelta(days=1)
    prev_month_first = prev_month_last.replace(day=1)

    lines = [f"🗓 Итоги месяца — {_MONTH_NAMES[prev_month_last.month - 1]} {prev_month_last.year}", ""]

    growth_pct: dict[str, float] = {}
    total_now = 0
    total_base = 0
    # The total delta is only meaningful when every counted platform has a baseline.
    base_complete = True
    has_data = False

    for platform in PLATFORM_IDS:
        label = LABELS[platform]
        latest = await db.get_latest(platform)
        if latest is None:
            continue

        # Baseline: first data point within the first week of the previous month.
        base_row = None
        for offset in range(7):
            base_row = await db.get_by_date(platform, prev_month_first + timedelta(days=offset))
            if base_row:
                break

        has_data = True
        count_now = latest["count"]
        total_now += count_now

        if base_row is None:
            base_complete = False
            lines.append(f"{label} — {_fmt(count_now)} (нет данных на начало месяца)")
            continue

        base = base_row["count"]
        total_base += base
        diff = count_now - base
        pct = diff / base * 100 if base > 0 else 0.0
        if base > 0:
            growth_pct[label] = pct
        lines.append(f"{label} — {_fmt(count_now)} ({_signed(diff)}, {_pct(pct)})")

    if not has_data:
        return None

    if len(growth_pct) >= 2:
        best = max(growth_pct.items(), key=lambda kv: kv[1])
        worst = min(growth_pct.items(), key=lambda kv: kv[1])
        lines.append("")
        lines.append(f"🏆 Лучшая платформа: {best[0]}, {_pct(best[1])}")
        lines.append(f"🐌 Слабее всех: {worst[0]}, {_pct(worst[1])}")

    if base_complete:
        lines.append("")
        lines.append(f"📈 Всего — {_fmt(total_now)} ({_signed(total_now - total_base)} за месяц)")

    return "\n".join(lines)


async def build_history_all(db: Database, days: int) -> str:
    """Combined history table for all platforms, as Telegram HTML."""
    # Collect per-platform rows indexed by date object
    data: dict[date, dict[str, int]] = {}

    for platform in PLATFORM_IDS:
        rows = await db.get_history(platform, days)
        for row in rows:
            try:
                d = datetime.fromisoformat(row["collected_at"]).date()
            except (ValueError, TypeError):
                continue
            data.setdefault(d, {})[platform] = row["count"]

    title = f"<b>📋 Все платформы · {days} дн.</b>"
    if not data:
        return f"{title}\n\nЗа последние {days} дн. данных нет."

    sorted_dates = sorted(data.keys())

    # Only platforms with data in the period get a column.
    columns = [p for p in PLATFORM_IDS if any(p in row for row in data.values())]

    # Narrow columns keep the table unwrapped on a phone; the legend names them.
    legend = ", ".join(f"{BY_ID[p].short} — {LABELS[p]}" for p in columns)
    table = [f"{'Дата':<6}" + "".join(f" {BY_ID[p].short:>9}" for p in columns)]
    for d in sorted_dates:
        row = data[d]
        cells = "".join(f" {_fmt(row[p]) if p in row else '—':>9}" for p in columns)
        table.append(f"{d.strftime('%d.%m'):<6}{cells}")

    return f"{title}\n{legend}\n\n<pre>" + "\n".join(table) + "</pre>"


async def build_history_table(db: Database, platform: str, days: int) -> str:
    """One platform's history with the change per collection, as Telegram HTML."""
    label = LABELS.get(platform, platform)
    rows = await db.get_history(platform, days)

    title = f"<b>📋 {label} · {days} дн.</b>"
    if not rows:
        return f"{title}\n\nЗа последние {days} дн. данных нет."

    table = [f"{'Дата':<6} {'Подписчики':>11} {'Изменение':>10}"]
    prev_count: int | None = None
    for row in rows:
        try:
            date_str = datetime.fromisoformat(row["collected_at"]).strftime("%d.%m")
        except (ValueError, TypeError):
            date_str = str(row["collected_at"])[5:10]

        count = row["count"]
        change = "—" if prev_count is None else _signed(count - prev_count)
        table.append(f"{date_str:<6} {_fmt(count):>11} {change:>10}")
        prev_count = count

    return f"{title}\n\n<pre>" + "\n".join(table) + "</pre>"

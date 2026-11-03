from __future__ import annotations

import math
from datetime import date, datetime, timedelta

from bot.db import Database, parse_utc, utcnow

PLATFORMS = ["telegram", "youtube", "linkedin"]
PLATFORM_LABELS = {
    "telegram": "Telegram",
    "youtube": "YouTube",
    "linkedin": "LinkedIn",
}

# Crossed when count moves up through one of these.
MILESTONES = [100, 250, 500, 1000, 2500, 5000, 10000, 25000, 50000, 100000, 250000, 500000, 1000000]

_BLOCKS = "▁▂▃▄▅▆▇█"

# Collected values are refreshed daily; older than this means collection is failing.
AUTO_STALE_DAYS = 2


def _fmt(n: int) -> str:
    return f"{n:,}"


def _delta_str(current: int, previous: int | None) -> str:
    if previous is None:
        return ""
    diff = current - previous
    if diff > 0:
        return f"▲ +{_fmt(diff)}"
    elif diff < 0:
        return f"▼ {_fmt(diff)}"
    return "→ 0"


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

    lines: list[str] = []
    lines.append(f"📊 Подписчики — {today.strftime('%d.%m.%Y')}")
    lines.append("")

    if errors.get("linkedin_cookie_expired"):
        lines.append("⚠️ LinkedIn cookie истёк — обнови через /setcookie")
        lines.append("")
    elif errors.get("linkedin_cookie_aging"):
        age = errors["linkedin_cookie_aging"]
        lines.append(f"⏰ LinkedIn cookie живёт уже {age} дней — пора обновить (/setcookie)")
        lines.append("")

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

    for platform in PLATFORMS:
        label = PLATFORM_LABELS[platform]
        snap = await _platform_snapshot(db, platform, today)
        latest = snap["latest"]

        if latest is None:
            if platforms is not None and platform not in platforms:
                continue
            if platform == "linkedin":
                lines.append(f"{label}: — (не введено)")
            elif errors.get(platform):
                lines.append(f"{label}: ⚠️ нет данных")
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
                        f"🔮 {label}: {_fmt(next_m)} через ~{weeks_left} нед (+{_fmt(rate)}/нед)"
                    )
            # Acceleration vs the average weekly rate over the prior ~3 weeks
            if month_count is not None:
                prev_avg = (week_count - month_count) / 3.3  # 23 days ≈ 3.3 weeks
                if prev_avg >= 3:  # too small a base gives meaningless ratios
                    if rate >= 2 * prev_avg:
                        accel_notes.append(
                            f"⚡ {label}: рост ×{rate / prev_avg:.1f} к среднему за месяц"
                        )
                    elif rate <= 0.5 * prev_avg:
                        accel_notes.append(
                            f"🐌 {label}: рост замедлился (+{_fmt(rate)}/нед против ~{prev_avg:.0f})"
                        )

        # Build the line
        head = f"{label}: {_fmt(count)}"
        spark = _sparkline(snap["spark_values"])
        if spark:
            head += f"  {spark}"

        deltas: list[str] = []
        for delta_raw, name in (
            (_delta_str(count, day_count), "день"),
            (_delta_str(count, week_count), "неделя"),
            (_delta_str(count, month_count), "месяц"),
        ):
            if delta_raw:
                deltas.append(f"{delta_raw} {name}")

        line = head
        if deltas:
            line += " (" + ", ".join(deltas) + ")"

        # Age marker: the latest value can be days old when collection keeps failing.
        try:
            collected_dt = parse_utc(collected_at_str)
            age_days = (utcnow() - collected_dt).days
        except (ValueError, TypeError):
            collected_dt = None
            age_days = 0
        date_str = collected_dt.strftime("%d.%m") if collected_dt else "?"

        if source == "manual":
            stale = age_days >= linkedin_stale_days
            marker = "⚠️ устарело" if stale else "вручную"
            line += f"  ({marker}, {date_str})"
        elif age_days >= AUTO_STALE_DAYS:
            line += f"  (⚠️ данные от {date_str})"

        if errors.get(platform):
            line += " ⚠️"

        lines.append(line)

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
        lines.append("Нет данных. Используйте /now для первого сбора.")
        return "\n".join(lines), False

    # Highlights block
    highlights: list[str] = []
    for label, milestone in milestones_hit:
        highlights.append(f"🎯 {label} перешагнул {_fmt(milestone)}!")
    if week_growth:
        leader_name, leader_pct = max(week_growth.items(), key=lambda kv: kv[1])
        if leader_pct > 0:
            highlights.append(f"🏆 Лидер недели: {leader_name} +{leader_pct:.1f}%")
    highlights.extend(accel_notes)
    highlights.extend(forecasts)
    if highlights:
        lines.append("")
        lines.extend(highlights)

    # Total
    lines.append("")
    total_parts = [f"📈 Всего: {_fmt(total_current)}"]
    for delta_raw, name in (
        (_delta_str(total_current, total_yesterday), "день"),
        (_delta_str(total_current, total_week_ago), "неделя"),
        (_delta_str(total_current, total_month_ago), "месяц"),
    ):
        if delta_raw:
            total_parts.append(f"{delta_raw} {name}")

    total_line = total_parts[0]
    if len(total_parts) > 1:
        total_line += " (" + ", ".join(total_parts[1:]) + ")"
    lines.append(total_line)

    return "\n".join(lines), has_change


async def build_week_report(db: Database) -> str:
    today = utcnow().date()
    week_start = today - timedelta(days=today.weekday())
    last_week_end = week_start - timedelta(days=1)

    lines = [f"📅 Неделя {week_start.strftime('%d.%m')} — {today.strftime('%d.%m.%Y')}", ""]

    total_now = 0
    total_prev = 0
    # The total delta is only meaningful when every counted platform has a baseline.
    prev_complete = True
    has_data = False

    for platform in PLATFORMS:
        label = PLATFORM_LABELS[platform]

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
        else:
            prev_complete = False

        delta = _delta_str(count_now, count_prev)
        prev_str = f" (было {_fmt(count_prev)})" if count_prev is not None else ""
        line = f"{label}: {_fmt(count_now)}{prev_str}"
        if delta:
            line += f"  {delta}"
        lines.append(line)

    if not has_data:
        return "Нет данных для недельного отчёта."

    lines.append("")
    total_delta = _delta_str(total_now, total_prev if prev_complete else None)
    total_line = f"📈 Всего: {_fmt(total_now)}"
    if total_delta:
        total_line += f"  {total_delta} за неделю"
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

    for platform in PLATFORMS:
        label = PLATFORM_LABELS[platform]
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
            lines.append(f"{label}: {_fmt(count_now)} (нет данных на начало месяца)")
            continue

        base = base_row["count"]
        total_base += base
        diff = count_now - base
        pct = diff / base * 100 if base > 0 else 0.0
        if base > 0:
            growth_pct[label] = pct
        sign = "+" if diff >= 0 else ""
        lines.append(f"{label}: {_fmt(count_now)} ({sign}{_fmt(diff)}, {sign}{pct:.1f}%)")

    if not has_data:
        return None

    if len(growth_pct) >= 2:
        best = max(growth_pct.items(), key=lambda kv: kv[1])
        worst = min(growth_pct.items(), key=lambda kv: kv[1])
        lines.append("")
        lines.append(f"🏆 Лучшая платформа: {best[0]} ({best[1]:+.1f}%)")
        lines.append(f"🐌 Слабее всех: {worst[0]} ({worst[1]:+.1f}%)")

    if base_complete:
        total_diff = total_now - total_base
        sign = "+" if total_diff >= 0 else ""
        lines.append("")
        lines.append(f"📈 Всего: {_fmt(total_now)} ({sign}{_fmt(total_diff)} за месяц)")

    return "\n".join(lines)


async def build_history_all(db: Database, days: int) -> str:
    """Combined history table for all platforms."""
    # Collect per-platform rows indexed by date object
    data: dict[date, dict[str, int]] = {}

    for platform in PLATFORMS:
        rows = await db.get_history(platform, days)
        for row in rows:
            try:
                d = datetime.fromisoformat(row["collected_at"]).date()
            except (ValueError, TypeError):
                continue
            data.setdefault(d, {})[platform] = row["count"]

    if not data:
        return f"Нет данных за последние {days} дней."

    sorted_dates = sorted(data.keys())

    lines = [f"📊 Все платформы — {days} дней", ""]
    lines.append("```")
    lines.append(f"{'Дата':<7} {'TG':>7} {'YT':>7} {'LI':>7}")
    lines.append("-" * 30)

    for d in sorted_dates:
        row = data[d]
        tg = _fmt(row["telegram"]) if "telegram" in row else "—"
        yt = _fmt(row["youtube"]) if "youtube" in row else "—"
        li = _fmt(row["linkedin"]) if "linkedin" in row else "—"
        lines.append(f"{d.strftime('%d.%m'):<7} {tg:>7} {yt:>7} {li:>7}")

    lines.append("```")
    return "\n".join(lines)


async def build_history_table(db: Database, platform: str, days: int) -> str:
    label = PLATFORM_LABELS.get(platform, platform)
    rows = await db.get_history(platform, days)

    if not rows:
        return f"Нет данных по {label} за последние {days} дней."

    lines = [f"📊 {label} — история за {days} дней", ""]
    lines.append("```")
    lines.append(f"{'Дата':<12} {'Подписчики':>12} {'Изменение':>12}")
    lines.append("-" * 38)

    prev_count: int | None = None
    for row in rows:
        try:
            dt = datetime.fromisoformat(row["collected_at"])
            date_str = dt.strftime("%d.%m.%Y")
        except (ValueError, TypeError):
            date_str = str(row["collected_at"])[:10]

        count = row["count"]
        if prev_count is not None:
            diff = count - prev_count
            if diff > 0:
                change = f"+{_fmt(diff)}"
            elif diff < 0:
                change = _fmt(diff)
            else:
                change = "0"
        else:
            change = "—"

        lines.append(f"{date_str:<12} {_fmt(count):>12} {change:>12}")
        prev_count = count

    lines.append("```")
    return "\n".join(lines)

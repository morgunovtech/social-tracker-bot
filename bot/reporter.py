from __future__ import annotations

from datetime import date, datetime, timedelta

from bot.db import Database

PLATFORMS = ["telegram", "youtube", "linkedin"]
PLATFORM_LABELS = {
    "telegram": "Telegram",
    "youtube": "YouTube",
    "linkedin": "LinkedIn",
}


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


async def build_report(
    db: Database,
    errors: dict[str, bool] | None = None,
) -> str:
    today = date.today()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    errors = errors or {}

    lines: list[str] = []
    lines.append(f"📊 Подписчики — {today.strftime('%d.%m.%Y')}")
    lines.append("")

    total_current = 0
    total_yesterday: int | None = 0
    total_week_ago: int | None = 0
    has_any_data = False

    for platform in PLATFORMS:
        label = PLATFORM_LABELS[platform]
        latest = await db.get_latest(platform)

        if latest is None:
            # LinkedIn without data — show placeholder without warning
            if platform == "linkedin":
                lines.append(f"{label}: — (не введено, используйте /linkedin)")
            elif errors.get(platform):
                lines.append(f"{label}: ⚠️ нет данных")
            continue

        has_any_data = True
        count = latest["count"]
        source = latest["source"]
        collected_at_str = latest["collected_at"]
        total_current += count

        day_row = await db.get_by_date(platform, yesterday)
        day_count = day_row["count"] if day_row else None

        week_row = await db.get_by_date(platform, week_ago)
        week_count = week_row["count"] if week_row else None

        parts = [f"{label}: {_fmt(count)}"]

        day_delta = _delta_str(count, day_count)
        if day_delta:
            parts.append(f"{day_delta} за день")

        week_delta = _delta_str(count, week_count)
        if week_delta:
            parts.append(f"{week_delta} за неделю")

        line = parts[0]
        if len(parts) > 1:
            line += " (" + ", ".join(parts[1:]) + ")"

        if platform == "linkedin" and source == "manual":
            try:
                collected_dt = datetime.fromisoformat(collected_at_str)
                line += f" (вручную, {collected_dt.strftime('%d.%m')})"
            except (ValueError, TypeError):
                line += " (вручную)"

        if errors.get(platform) and platform != "linkedin":
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

    if not has_any_data:
        lines.append("Нет данных. Используйте /now для первого сбора.")
        return "\n".join(lines)

    lines.append("")
    total_parts = [f"📈 Всего: {_fmt(total_current)}"]

    total_day_delta = _delta_str(total_current, total_yesterday)
    if total_day_delta:
        total_parts.append(f"{total_day_delta} за день")

    total_week_delta = _delta_str(total_current, total_week_ago)
    if total_week_delta:
        total_parts.append(f"{total_week_delta} за неделю")

    total_line = total_parts[0]
    if len(total_parts) > 1:
        total_line += " (" + ", ".join(total_parts[1:]) + ")"

    lines.append(total_line)

    return "\n".join(lines)


async def build_week_report(db: Database) -> str:
    today = date.today()
    # This week: Mon–today
    week_start = today - timedelta(days=today.weekday())
    # Last week: Mon–Sun
    last_week_start = week_start - timedelta(days=7)
    last_week_end = week_start - timedelta(days=1)

    lines = [f"📅 Неделя {week_start.strftime('%d.%m')} — {today.strftime('%d.%m.%Y')}", ""]

    total_now = 0
    total_prev = 0
    has_data = False

    for platform in PLATFORMS:
        label = PLATFORM_LABELS[platform]

        latest = await db.get_latest(platform)
        if latest is None:
            continue

        has_data = True
        count_now = latest["count"]
        total_now += count_now

        # Best value from last week (last available day)
        prev_row = None
        for d in range(6, -1, -1):
            prev_row = await db.get_by_date(platform, last_week_end - timedelta(days=d - 6))
            if prev_row:
                break

        count_prev = prev_row["count"] if prev_row else None
        if count_prev is not None:
            total_prev += count_prev

        delta = _delta_str(count_now, count_prev)
        prev_str = f" (было {_fmt(count_prev)})" if count_prev else ""
        line = f"{label}: {_fmt(count_now)}{prev_str}"
        if delta:
            line += f"  {delta}"
        lines.append(line)

    if not has_data:
        return "Нет данных для недельного отчёта."

    lines.append("")
    total_delta = _delta_str(total_now, total_prev if total_prev else None)
    total_line = f"📈 Всего: {_fmt(total_now)}"
    if total_delta:
        total_line += f"  {total_delta} за неделю"
    lines.append(total_line)

    return "\n".join(lines)


async def build_history_all(db: Database, days: int) -> str:
    """Combined history table for all platforms."""
    from datetime import datetime as _dt
    since = (date.today() - timedelta(days=days))

    # Collect per-platform rows indexed by date string
    data: dict[str, dict[str, int]] = {}  # date_str -> {platform: count}
    all_dates: set[str] = set()

    for platform in PLATFORMS:
        rows = await db.get_history(platform, days)
        for row in rows:
            try:
                d = _dt.fromisoformat(row["collected_at"]).strftime("%d.%m")
            except (ValueError, TypeError):
                d = str(row["collected_at"])[:5]
            all_dates.add(d)
            data.setdefault(d, {})[platform] = row["count"]

    if not all_dates:
        return f"Нет данных за последние {days} дней."

    sorted_dates = sorted(all_dates, key=lambda s: (s[3:], s[:2]))  # sort by MM, DD

    lines = [f"📊 Все платформы — {days} дней", ""]
    lines.append("```")
    lines.append(f"{'Дата':<7} {'TG':>7} {'YT':>7} {'LI':>7}")
    lines.append("-" * 30)

    for d in sorted_dates:
        tg = _fmt(data[d]["telegram"]) if "telegram" in data[d] else "—"
        yt = _fmt(data[d]["youtube"]) if "youtube" in data[d] else "—"
        li = _fmt(data[d]["linkedin"]) if "linkedin" in data[d] else "—"
        lines.append(f"{d:<7} {tg:>7} {yt:>7} {li:>7}")

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

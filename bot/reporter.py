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
            if errors.get(platform):
                lines.append(f"{label}: ⚠️ нет данных")
            continue

        has_any_data = True
        count = latest["count"]
        source = latest["source"]
        collected_at_str = latest["collected_at"]
        total_current += count

        # Day delta
        day_row = await db.get_by_date(platform, yesterday)
        day_count = day_row["count"] if day_row else None

        # Week delta
        week_row = await db.get_by_date(platform, week_ago)
        week_count = week_row["count"] if week_row else None

        # Build line
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

        # Manual LinkedIn marker
        if platform == "linkedin" and source == "manual":
            try:
                collected_dt = datetime.fromisoformat(collected_at_str)
                line += f" (вручную, {collected_dt.strftime('%d.%m')})"
            except (ValueError, TypeError):
                line += " (вручную)"

        # Error marker
        if errors.get(platform):
            line += " ⚠️"

        lines.append(line)

        # Accumulate totals
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

    # Total line
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

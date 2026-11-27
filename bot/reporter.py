from __future__ import annotations

import math
from datetime import date, datetime, timedelta

from bot.db import Database, parse_utc, utcnow
from bot.i18n import language, t
from bot.platforms import BY_ID, LABELS, PLATFORM_IDS

# Crossed when count moves up through one of these.
MILESTONES = [100, 250, 500, 1000, 2500, 5000, 10000, 25000, 50000, 100000, 250000, 500000, 1000000]

_BLOCKS = "▁▂▃▄▅▆▇█"

# Collected values are refreshed daily; older than this means collection is failing.
AUTO_STALE_DAYS = 2
# A week-ago or month-ago baseline is the row of that day or, when that
# collection failed (LinkedIn answers 999 now and then), the newest row up to
# this many days earlier: one missed day used to leave the report without a
# weekly delta, a leader and a forecast at all. The day-ago delta stays exact.
WEEK_BASELINE_SLACK_DAYS = 3
MONTH_BASELINE_SLACK_DAYS = 7
# Telegram's message limit is 4096 characters; the rest is headroom for HTML tags.
HISTORY_LIMIT = 4000

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


def _decimal(text: str) -> str:
    """The decimal separator of the chat language: «6,7» in Russian, "6.7" in English."""
    return text.replace(".", ",") if language() == "ru" else text


def _pct(value: float) -> str:
    """+6.66 → «+6,7%»: the decimal separator of the language and a real minus sign."""
    return _decimal(f"{value:+.1f}%").replace("-", MINUS)


def _deltas(current: int, day: int | None, week: int | None, month: int | None) -> str:
    """«+10 за день · +15 за неделю · +20 за месяц», only the periods with a baseline."""
    parts = [
        template.format(delta=delta)
        for delta, template in (
            (_delta_str(current, day), t("{delta} за день")),
            (_delta_str(current, week), t("{delta} за неделю")),
            (_delta_str(current, month), t("{delta} за месяц")),
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
    week_row = await db.get_on_or_before(platform, week_ago, WEEK_BASELINE_SLACK_DAYS)
    month_row = await db.get_on_or_before(platform, month_ago, MONTH_BASELINE_SLACK_DAYS)

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
    shown_date: date | None = None,
) -> tuple[str, bool]:
    """Build the textual report and return (text, has_meaningful_change).

    platforms are the enabled ones: only they get a placeholder line while
    they have no data (a disabled platform with old data is still shown).
    shown_date is the date in the title — the owner's local one; the rows are
    looked up by UTC days, which is how they are stored.
    """
    # DB timestamps are UTC, so "today" must be the UTC date too.
    today = utcnow().date()
    errors = errors or {}

    lines: list[str] = [t("📊 Подписчики · {date}").format(date=(shown_date or today).strftime("%d.%m.%Y"))]

    # Problems first: they need an action, the numbers don't.
    if errors.get("linkedin_cookie_expired"):
        lines += ["", t("🟠 LinkedIn cookie истёк — обнови через /setcookie")]
    elif errors.get("linkedin_cookie_aging"):
        age = errors["linkedin_cookie_aging"]
        lines += ["", t("🟠 LinkedIn cookie живёт уже {age} дн. — пора обновить: /setcookie").format(age=age)]
    if errors.get("instagram_token_missing"):
        lines += ["", t("🟠 Instagram подключён, но токена нет — пришли его через /igtoken")]
    elif errors.get("instagram_token_expired"):
        lines += ["", t("🟠 Instagram отклонил токен — пришли новый через /igtoken")]

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
            if platform == "linkedin" and errors.get("linkedin_baseline_needed"):
                needed = errors["linkedin_baseline_needed"]
                lines += [
                    "",
                    t("{label} — по cookie получено {count}: первое значение подтверди вручную — /linkedin {raw}").format(
                        label=label, count=_fmt(needed), raw=needed
                    ),
                ]
            elif platform == "linkedin":
                lines += ["", t("{label} — пока нет данных: число вводится вручную").format(label=label)]
            elif platform == "instagram" and (
                errors.get("instagram_token_missing") or errors.get("instagram_token_expired")
            ):
                lines += ["", t("{label} — пока нет данных: нужен токен, см. /igtoken").format(label=label)]
            elif errors.get(platform):
                lines += ["", t("{label} — ⚠️ собрать не удалось").format(label=label)]
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
                        t("🔮 {label}: {goal} примерно через {weeks} нед. (+{rate} в неделю)").format(
                            label=label, goal=_fmt(next_m), weeks=weeks_left, rate=_fmt(rate)
                        )
                    )
            # Acceleration vs the average weekly rate over the prior ~3 weeks
            if month_count is not None:
                prev_avg = (week_count - month_count) / 3.3  # 23 days ≈ 3.3 weeks
                if prev_avg >= 3:  # too small a base gives meaningless ratios
                    if rate >= 2 * prev_avg:
                        ratio = _decimal(f"{rate / prev_avg:.1f}")
                        accel_notes.append(
                            t("⚡ {label}: растёт в {ratio} раза быстрее, чем обычно за месяц").format(
                                label=label, ratio=ratio
                            )
                        )
                    elif rate <= 0.5 * prev_avg:
                        accel_notes.append(
                            t("🐌 {label}: рост замедлился — {rate} в неделю против обычных ~{avg:.0f}").format(
                                label=label, rate=_signed(rate), avg=prev_avg
                            )
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
                block.append(t("🟠 введено вручную {date} — пора обновить").format(date=date_str))
            else:
                block.append(t("введено вручную {date}").format(date=date_str))
        elif age_days >= AUTO_STALE_DAYS:
            block.append(t("🟠 данные от {date} — свежие собрать не удаётся").format(date=date_str))
        elif errors.get(platform):
            block.append(t("⚠️ сегодня собрать не удалось"))

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
        if platforms is not None and not platforms:
            lines += ["", t("Данных пока нет: сначала подключи сеть — кнопка ниже.")]
        else:
            lines += ["", t("Данных пока нет — нажми «🔄 Обновить данные» или отправь /now.")]
        return "\n".join(lines), False

    # Total: only the periods every platform with data can back.
    lines += ["", t("📈 Всего — {total}").format(total=_fmt(total_current))]
    total_deltas = _deltas(total_current, total_yesterday, total_week_ago, total_month_ago)
    if total_deltas:
        lines.append(total_deltas)

    highlights: list[str] = [
        t("🎯 {label} перешагнул {milestone}!").format(label=label, milestone=_fmt(milestone))
        for label, milestone in milestones_hit
    ]
    if week_growth:
        leader_name, leader_pct = max(week_growth.items(), key=lambda kv: kv[1])
        if leader_pct > 0:
            highlights.append(t("🏆 Лидер недели: {label}, {pct}").format(label=leader_name, pct=_pct(leader_pct)))
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
        t("📅 Неделя {start} — {end}").format(start=week_start.strftime("%d.%m"), end=today.strftime("%d.%m.%Y")),
        t("В сравнении с концом прошлой недели"),
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
            lines.append(
                t("{label} — {count} ({delta}, было {prev})").format(
                    label=label, count=_fmt(count_now), delta=_delta_str(count_now, count_prev), prev=_fmt(count_prev)
                )
            )
        else:
            prev_complete = False
            lines.append(t("{label} — {count} (за прошлую неделю данных нет)").format(label=label, count=_fmt(count_now)))

    if not has_data:
        return t("📅 Неделя\n\nДанных пока нет — недельное сравнение появится после первых сборов.")

    lines.append("")
    total_line = t("📈 Всего — {total}").format(total=_fmt(total_now))
    if prev_complete:
        total_line += t(" ({delta} за неделю)").format(delta=_delta_str(total_now, total_prev))
    lines.append(total_line)

    return "\n".join(lines)


_MONTH_NAMES = [
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
]


async def build_month_report(db: Database, today: date | None = None) -> str | None:
    """Digest for the month that just ended (intended for the 1st of the month).

    Compares the latest counts against the first available data point of the
    previous month. Returns None when there is nothing to report. today is
    the owner's local date: at 00:30 on the 1st in Tashkent it is still the
    previous month in UTC.
    """
    today = today or utcnow().date()
    prev_month_last = today.replace(day=1) - timedelta(days=1)
    prev_month_first = prev_month_last.replace(day=1)

    lines = [
        t("🗓 Итоги месяца — {month} {year}").format(
            month=t(_MONTH_NAMES[prev_month_last.month - 1]), year=prev_month_last.year
        ),
        "",
    ]

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
            lines.append(t("{label} — {count} (нет данных на начало месяца)").format(label=label, count=_fmt(count_now)))
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
        lines.append(t("🏆 Лучшая платформа: {label}, {pct}").format(label=best[0], pct=_pct(best[1])))
        lines.append(t("🐌 Слабее всех: {label}, {pct}").format(label=worst[0], pct=_pct(worst[1])))

    if base_complete:
        lines.append("")
        lines.append(
            t("📈 Всего — {total} ({delta} за месяц)").format(
                total=_fmt(total_now), delta=_signed(total_now - total_base)
            )
        )

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

    title = t("<b>📋 Все платформы · {days} дн.</b>").format(days=days)
    if not data:
        return f"{title}\n\n" + t("За последние {days} дн. данных нет.").format(days=days)

    sorted_dates = sorted(data.keys())

    # Only platforms with data in the period get a column.
    columns = [p for p in PLATFORM_IDS if any(p in row for row in data.values())]

    # Narrow columns keep the table unwrapped on a phone; the legend names them.
    # Each column is as wide as its widest number, not a fixed width: with four
    # networks a 90-day table must still fit one Telegram message.
    legend = ", ".join(f"{BY_ID[p].short} — {LABELS[p]}" for p in columns)
    widths = {
        p: max([len(BY_ID[p].short)] + [len(_fmt(row[p])) for row in data.values() if p in row])
        for p in columns
    }
    table = [f"{t('Дата'):<5}" + "".join(f" {BY_ID[p].short:>{widths[p]}}" for p in columns)]
    for d in sorted_dates:
        row = data[d]
        cells = "".join(f" {_fmt(row[p]) if p in row else '—':>{widths[p]}}" for p in columns)
        table.append(f"{d.strftime('%d.%m'):<5}{cells}")

    def render(rows: list[str], note: str = "") -> str:
        return f"{title}\n{legend}{note}\n\n<pre>" + "\n".join([table[0]] + rows) + "</pre>"

    text = render(table[1:])
    if len(text) > HISTORY_LIMIT:
        # Still too long: the oldest days go, and the note says so. Every row
        # is the same width, so the number that fits is plain arithmetic.
        row_len = len(table[1]) + 1
        note = t(" (поместились последние {n} дн.)")
        overhead = len(render([], note.format(n=999)))
        shown = max(1, (HISTORY_LIMIT - overhead) // row_len)
        text = render(table[-shown:], note.format(n=shown))
    return text


async def build_history_table(db: Database, platform: str, days: int) -> str:
    """One platform's history with the change per collection, as Telegram HTML."""
    label = LABELS.get(platform, platform)
    rows = await db.get_history(platform, days)

    title = t("<b>📋 {label} · {days} дн.</b>").format(label=label, days=days)
    if not rows:
        return f"{title}\n\n" + t("За последние {days} дн. данных нет.").format(days=days)

    table = [f"{t('Дата'):<6} {t('Подписчики'):>11} {t('Изменение'):>10}"]
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

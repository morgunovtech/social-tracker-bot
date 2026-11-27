"""Collection health: failure streaks per platform, the LinkedIn cookie and
the Instagram token (missing, rejected, or expiring within a week).

Each problem is an alert of its own in the one shape (bot/humanize.py), said
once until it is fixed; a failure streak that was alerted ends with one
recovery that says how long it lasted, from the first failed collection.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from bot import humanize
from bot.db import Database, parse_utc, utcnow
from bot.i18n import plural, t
from bot.platforms import PLATFORMS
from bot.platforms import instagram as ig
from bot.reporter import _fmt

if TYPE_CHECKING:
    from bot.scheduler import CollectOutcome

# The daily collect itself raised — the DB, the HTTP session, a bug — rather
# than one network failing: counted once per day like a platform's streak.
RUN_FAIL_STREAK_KEY = "run_fail_streak"
RUN_FAIL_DATE_KEY = "run_fail_last_date"
RUN_FAIL_SINCE_KEY = "run_fail_since"
# A streak is alerted on its second day, then weekly while it lasts.
ALERT_STREAK = 2
_ZONE = ZoneInfo("UTC")


def _alerted(streak: int) -> bool:
    return streak == ALERT_STREAK or (streak > ALERT_STREAK and streak % 7 == 0)


async def _since(db: Database, key: str) -> datetime | None:
    """When a failure series began (stored at its first failure); None when unknown."""
    raw = await db.get_setting(key)
    try:
        return parse_utc(raw) if raw else None
    except ValueError:
        return None


async def run_failed(db: Database) -> list[str]:
    """Alerts for a daily collect that raised as a whole: one on the second
    day in a row, then weekly; nothing on day one (the retry an hour later
    usually makes it)."""
    today_iso = utcnow().date().isoformat()
    if await db.get_setting(RUN_FAIL_DATE_KEY) == today_iso:
        return []
    streak = int(await db.get_setting(RUN_FAIL_STREAK_KEY) or "0") + 1
    await db.set_setting(RUN_FAIL_STREAK_KEY, str(streak))
    await db.set_setting(RUN_FAIL_DATE_KEY, today_iso)
    if streak == 1:
        await db.set_setting(RUN_FAIL_SINCE_KEY, utcnow().isoformat())
    if _alerted(streak):
        head = t("🟠 Ежедневный сбор не выполнился {streak} дн. подряд").format(streak=streak)
        return [humanize.alert(head, "run_failed", t("сбор падает целиком; повтор через час, подробности в логах"))]
    return []


def _recovered(head: str, verb: str, since: datetime | None, tz: ZoneInfo) -> str:
    how_long = humanize.lasted(since, None, utcnow(), tz) if since else ""
    return humanize.recovery(head, how_long, verb)


async def alert_lines(db: Database, outcome: CollectOutcome, tz: ZoneInfo = _ZONE) -> list[str]:
    """The collection's alerts, each a message, with dedup state in settings:

    - cookie expiry: alerted once until the cookie works again;
    - a first LinkedIn number read by cookie: alerted once until the owner confirms it;
    - a missing or dead Instagram token: alerted once until a token works;
    - an Instagram token that expires within a week: alerted once per token;
    - failure streaks: alerted at 2 consecutive days, then weekly while
      broken; an alerted streak ends with a ✅ that says how long it lasted.

    tz — the owner's zone, for the times a recovery names.
    """
    today_iso = utcnow().date().isoformat()
    alerts: list[str] = []
    # The collect itself ran: a streak of whole-run failures (run_failed) ends here.
    run_streak = int(await db.get_setting(RUN_FAIL_STREAK_KEY) or "0")
    if run_streak:
        await db.set_setting(RUN_FAIL_STREAK_KEY, "0")
        if run_streak >= ALERT_STREAK:
            alerts.append(_recovered(
                t("✅ Ежедневный сбор снова выполняется"), "Не выполнялся", await _since(db, RUN_FAIL_SINCE_KEY), tz,
            ))

    needed = outcome.errors.get("linkedin_baseline_needed")
    if needed:
        if await db.get_setting("linkedin_baseline_alerted") != "1":
            await db.set_setting("linkedin_baseline_alerted", "1")
            head = t("🟠 LinkedIn: по cookie получено {count} — первое число подтверди командой /linkedin {raw}, "
                     "дальше буду собирать сам").format(count=_fmt(needed), raw=needed)
            alerts.append(humanize.alert(head, "linkedin_baseline"))
    elif "linkedin" in outcome.collected:
        await db.set_setting("linkedin_baseline_alerted", "0")

    if outcome.errors.get("linkedin_cookie_expired"):
        if await db.get_setting("cookie_expired_alerted") != "1":
            await db.set_setting("cookie_expired_alerted", "1")
            alerts.append(humanize.alert(
                t("🟠 LinkedIn cookie истёк или отклонён — обнови через /setcookie"), "cookie_expired",
                t("LinkedIn отправил на вход вместо профиля"),
            ))
    elif outcome.collected.get("linkedin", (None, None))[1] == "cookie":
        await db.set_setting("cookie_expired_alerted", "0")

    if outcome.errors.get("instagram_token_expired") or outcome.errors.get("instagram_token_missing"):
        if await db.get_setting("instagram_token_alerted") != "1":
            await db.set_setting("instagram_token_alerted", "1")
            if outcome.errors.get("instagram_token_expired"):
                alerts.append(humanize.alert(
                    t("🟠 Instagram отклонил токен: истёк или отозван — пришли новый через /igtoken"), "token_rejected",
                    t("Graph API: ошибка авторизации"),
                ))
            else:
                alerts.append(humanize.alert(
                    t("🟠 Instagram подключён, но токена нет — пришли его через /igtoken"), "token_missing",
                    "INSTAGRAM_USERNAME",
                ))
    elif "instagram" in outcome.collected:
        await db.set_setting("instagram_token_alerted", "0")

    # A token with a date: said once a week ahead, re-armed by a token that works past the window.
    left = outcome.errors.get("instagram_token_expiring")
    if left:
        if await db.get_setting(ig.EXPIRY_ALERTED_KEY) != "1":
            await db.set_setting(ig.EXPIRY_ALERTED_KEY, "1")
            expiry = await ig.get_expiry(db)
            date = expiry.astimezone(tz).strftime("%d.%m.%Y") if isinstance(expiry, datetime) else "?"
            alerts.append(humanize.alert(
                t("🟠 Токен Instagram истекает через {left} {d} — пришли новый через /igtoken").format(
                    left=left, d=plural(left, "дн.", "дн.", "дн.")),
                "token_expiring", t("debug_token: действует до {date}").format(date=date),
            ))
    elif "instagram" in outcome.collected:
        await db.set_setting(ig.EXPIRY_ALERTED_KEY, "0")

    for platform in PLATFORMS:
        streak_key, since_key = f"fail_streak_{platform.id}", f"fail_since_{platform.id}"
        if outcome.errors.get(platform.id):
            # Count at most one failure per day, so same-day retries don't inflate the streak.
            if await db.get_setting(f"fail_last_date_{platform.id}") != today_iso:
                streak = int(await db.get_setting(streak_key) or "0") + 1
                await db.set_setting(streak_key, str(streak))
                await db.set_setting(f"fail_last_date_{platform.id}", today_iso)
                if streak == 1:
                    await db.set_setting(since_key, utcnow().isoformat())
                if _alerted(streak):
                    head = t("🟠 {label}: не удаётся собрать данные {streak} дн. подряд").format(
                        label=platform.label, streak=streak
                    )
                    alerts.append(humanize.alert(
                        head, "collection_failing", t("раз в день и два повтора через час; подробности в логах"),
                    ))
        elif platform.id in outcome.collected:
            streak = int(await db.get_setting(streak_key) or "0")
            if streak:
                await db.set_setting(streak_key, "0")
            if streak >= ALERT_STREAK:
                alerts.append(_recovered(
                    t("✅ {label}: данные снова собираются").format(label=platform.label), "Не собирались",
                    await _since(db, since_key), tz,
                ))

    return alerts


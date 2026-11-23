"""Collection health: failure streaks per platform, the LinkedIn cookie and
the Instagram token."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bot.db import Database, utcnow
from bot.i18n import t
from bot.platforms import PLATFORMS
from bot.reporter import _fmt

if TYPE_CHECKING:
    from bot.scheduler import CollectOutcome

# The daily collect itself raised — the DB, the HTTP session, a bug — rather
# than one network failing: counted once per day like a platform's streak.
RUN_FAIL_STREAK_KEY = "run_fail_streak"
RUN_FAIL_DATE_KEY = "run_fail_last_date"


async def run_failed(db: Database) -> list[str]:
    """Alert lines for a daily collect that raised as a whole: a line on the
    second day in a row, then weekly; nothing on day one (the retry an hour
    later usually makes it)."""
    today_iso = utcnow().date().isoformat()
    if await db.get_setting(RUN_FAIL_DATE_KEY) == today_iso:
        return []
    streak = int(await db.get_setting(RUN_FAIL_STREAK_KEY) or "0") + 1
    await db.set_setting(RUN_FAIL_STREAK_KEY, str(streak))
    await db.set_setting(RUN_FAIL_DATE_KEY, today_iso)
    if streak == 2 or (streak > 2 and streak % 7 == 0):
        return [t("🟠 Ежедневный сбор не выполнился {streak} дн. подряд — подробности в логах бота").format(streak=streak)]
    return []


async def alert_lines(db: Database, outcome: CollectOutcome) -> list[str]:
    """Alert lines with dedup state in settings.

    - cookie expiry: alerted once until the cookie works again;
    - a first LinkedIn number read by cookie: alerted once until the owner confirms it;
    - a missing or dead Instagram token: alerted once until a token works;
    - failure streaks: alerted at 2 consecutive days, then weekly while broken.
    """
    today_iso = utcnow().date().isoformat()
    lines: list[str] = []
    # The collect itself ran: a streak of whole-run failures (run_failed) ends here.
    await db.set_setting(RUN_FAIL_STREAK_KEY, "0")

    needed = outcome.errors.get("linkedin_baseline_needed")
    if needed:
        if await db.get_setting("linkedin_baseline_alerted") != "1":
            await db.set_setting("linkedin_baseline_alerted", "1")
            lines.append(
                t("🟠 LinkedIn: по cookie получено {count} — первое число подтверди командой /linkedin {raw}, "
                  "дальше буду собирать сам").format(count=_fmt(needed), raw=needed)
            )
    elif "linkedin" in outcome.collected:
        await db.set_setting("linkedin_baseline_alerted", "0")

    if outcome.errors.get("linkedin_cookie_expired"):
        if await db.get_setting("cookie_expired_alerted") != "1":
            await db.set_setting("cookie_expired_alerted", "1")
            lines.append(t("🟠 LinkedIn cookie истёк или отклонён — обнови через /setcookie"))
    elif outcome.collected.get("linkedin", (None, None))[1] == "cookie":
        await db.set_setting("cookie_expired_alerted", "0")

    if outcome.errors.get("instagram_token_expired") or outcome.errors.get("instagram_token_missing"):
        if await db.get_setting("instagram_token_alerted") != "1":
            await db.set_setting("instagram_token_alerted", "1")
            if outcome.errors.get("instagram_token_expired"):
                lines.append(t("🟠 Instagram отклонил токен: истёк или отозван — пришли новый через /igtoken"))
            else:
                lines.append(t("⚠️ Instagram подключён, но токена нет — пришли его через /igtoken"))
    elif "instagram" in outcome.collected:
        await db.set_setting("instagram_token_alerted", "0")

    for platform in PLATFORMS:
        if outcome.errors.get(platform.id):
            # Count at most one failure per day, so same-day retries don't inflate the streak.
            if await db.get_setting(f"fail_last_date_{platform.id}") != today_iso:
                streak = int(await db.get_setting(f"fail_streak_{platform.id}") or "0") + 1
                await db.set_setting(f"fail_streak_{platform.id}", str(streak))
                await db.set_setting(f"fail_last_date_{platform.id}", today_iso)
                if streak == 2 or (streak > 2 and streak % 7 == 0):
                    lines.append(
                        t("🟠 {label}: не удаётся собрать данные {streak} дн. подряд").format(
                            label=platform.label, streak=streak
                        )
                    )
        elif platform.id in outcome.collected:
            await db.set_setting(f"fail_streak_{platform.id}", "0")

    return lines

"""Collection health: failure streaks per platform and the LinkedIn cookie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bot.db import Database, utcnow
from bot.platforms import PLATFORMS

if TYPE_CHECKING:
    from bot.scheduler import CollectOutcome


async def alert_lines(db: Database, outcome: CollectOutcome) -> list[str]:
    """Alert lines with dedup state in settings.

    - cookie expiry: alerted once until the cookie works again;
    - failure streaks: alerted at 2 consecutive days, then weekly while broken.
    """
    today_iso = utcnow().date().isoformat()
    lines: list[str] = []

    if outcome.errors.get("linkedin_cookie_expired"):
        if await db.get_setting("cookie_expired_alerted") != "1":
            await db.set_setting("cookie_expired_alerted", "1")
            lines.append("🔴 LinkedIn cookie истёк или отклонён — обнови через /setcookie")
    elif outcome.collected.get("linkedin", (None, None))[1] == "cookie":
        await db.set_setting("cookie_expired_alerted", "0")

    for platform in PLATFORMS:
        if outcome.errors.get(platform.id):
            # Count at most one failure per day, so same-day retries don't inflate the streak.
            if await db.get_setting(f"fail_last_date_{platform.id}") != today_iso:
                streak = int(await db.get_setting(f"fail_streak_{platform.id}") or "0") + 1
                await db.set_setting(f"fail_streak_{platform.id}", str(streak))
                await db.set_setting(f"fail_last_date_{platform.id}", today_iso)
                if streak == 2 or (streak > 2 and streak % 7 == 0):
                    lines.append(f"🔴 {platform.label}: не удаётся собрать данные {streak} дн. подряд")
        elif platform.id in outcome.collected:
            await db.set_setting(f"fail_streak_{platform.id}", "0")

    return lines

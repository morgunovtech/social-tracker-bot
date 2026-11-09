"""What this bot sees, one line per network, for the TofsDevOps main screen.

The owner wants one screen that says «всё в порядке» for the sites and the
social channels alike. When HEALTHCHECK_URL is a TofsDevOps heartbeat address
(…/api/heartbeat/…), the daily mark is a POST that carries these lines, and
the profile check refreshes them every 30 minutes without counting as a mark.
TofsDevOps only shows them: the alerts and the detailed screens stay here.

Format: TofsDevOps docs/DEVELOPMENT.md, «Статус от другого бота».
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta

import aiohttp

from bot import platforms
from bot.config import Config
from bot.db import Database, parse_utc, utcnow
from bot.monitors import followers, profile
from bot.reporter import AUTO_STALE_DAYS, _fmt, _signed

logger = logging.getLogger(__name__)

TITLE = "📣 Соцсети"
# The last collection's problems (a failed platform, LinkedIn cookie age):
# the profile check between two collections must not forget them.
LAST_ERRORS_KEY = "tofs_last_errors"


def is_tofs_url(url: str | None) -> bool:
    return bool(url) and "/api/heartbeat/" in url


async def remember_errors(db: Database, errors: dict) -> None:
    await db.set_setting(LAST_ERRORS_KEY, json.dumps(errors))


async def _last_errors(db: Database) -> dict:
    try:
        data = json.loads(await db.get_setting(LAST_ERRORS_KEY) or "{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


async def _item(db: Database, config: Config, platform, errors: dict) -> dict:
    """One line: is the channel there, is it read, are people coming."""
    name = platform.label
    fails = int(await db.get_setting(f"profile_fail_{platform.id}") or "0")
    if fails >= profile.UNREACHABLE_AFTER:
        return {"name": name, "level": "critical",
                "text": "профиль не читается — удалён, скрыт или у бота отобрали права?"}
    latest = await db.get_latest(platform.id)
    if platform.id == "linkedin" and errors.get("linkedin_cookie_expired"):
        return {"name": name, "level": "warning", "text": "cookie истёк — обнови через /setcookie"}
    if latest is None:
        if errors.get(platform.id):
            return {"name": name, "level": "warning", "text": "собрать не удалось"}
        return {"name": name, "level": "unknown", "text": "пока нет данных"}

    count = latest["count"]
    yesterday = await db.get_by_date(platform.id, utcnow().date() - timedelta(days=1))
    head = _fmt(count) + (f", {_signed(count - yesterday['count'])} за сутки" if yesterday else "")
    try:
        age_days = (utcnow() - parse_utc(latest["collected_at"])).days
    except (ValueError, TypeError):
        age_days = 0
    if latest["source"] == "manual":
        if age_days >= config.linkedin_stale_days:
            return {"name": name, "level": "warning", "text": f"{head} — введено вручную {age_days} дн. назад"}
    elif age_days >= AUTO_STALE_DAYS:
        return {"name": name, "level": "warning", "text": f"{head} — свежие данные собрать не удаётся"}
    if errors.get(platform.id):
        return {"name": name, "level": "warning", "text": f"{head} — сегодня собрать не удалось"}
    if platform.id == "linkedin" and errors.get("linkedin_cookie_aging"):
        return {"name": name, "level": "warning",
                "text": f"{head} — cookie живёт {errors['linkedin_cookie_aging']} дн., пора обновить"}
    # The same bar as this bot's own drop alert: −2 of 1 157 is daily noise.
    if yesterday and followers.is_drop(yesterday["count"], count):
        return {"name": name, "level": "warning", "text": head}
    return {"name": name, "level": "ok", "text": head}


async def build(db: Database, config: Config, errors: dict | None = None, bot_username: str | None = None) -> dict:
    """The status payload. errors: the collection that just ran, or None to
    reuse the last one's."""
    if errors is None:
        errors = await _last_errors(db)
    items = [await _item(db, config, p, errors) for p in platforms.enabled(config)]
    payload: dict = {"title": TITLE, "items": items}
    if bot_username:
        payload["open_url"] = f"https://t.me/{bot_username}"
    return payload


async def send(url: str, payload: dict, mark: bool) -> bool:
    """POST the lines. A status TofsDevOps refuses (400 — a format change on
    either side) must not cost the mark: then the plain GET goes out, so a
    format bug shows up in the logs, not as «the bot is dead»."""
    body = {**payload, "heartbeat": mark}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status < 300:
                    logger.info("Status sent to TofsDevOps (mark=%s)", mark)
                    return True
                reason = (await resp.text())[:200]
                logger.warning("TofsDevOps refused the status: HTTP %s %s", resp.status, reason)
                if resp.status == 403 or not mark:
                    return False
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                return resp.status < 300
    except Exception:
        logger.warning("Status to TofsDevOps failed", exc_info=True)
        return False

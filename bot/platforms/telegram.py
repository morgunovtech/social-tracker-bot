from __future__ import annotations

import json
import logging

from telegram import Bot, User
from telegram.error import BadRequest, Forbidden, TelegramError

from bot.platforms.base import ADMINS, IMAGE, TEXT, Context, Platform, Snapshot

logger = logging.getLogger(__name__)


async def collect_telegram(bot: Bot, channel_id: str) -> int | None:
    try:
        count = await bot.get_chat_member_count(chat_id=channel_id)
        logger.info("Telegram subscribers: %d", count)
        return count
    except Exception:
        logger.exception("Failed to collect Telegram subscribers")
        return None


def _user_name(user: User) -> str:
    return f"{user.full_name} (@{user.username})" if user.username else user.full_name


async def fetch_channel(bot: Bot, channel_id: str) -> dict[str, str] | None:
    """Public channel fields, plus its admin list when Telegram lets the bot read it.

    A public channel's title and follower count are readable by anyone, the
    admin list only by its admins: without that right Telegram answers
    "Member list is inaccessible". The list is then left out and admin_access
    says so — losing the access later (a hijacker demoting the bot) is a
    change the profile monitor reports.
    """
    try:
        chat = await bot.get_chat(chat_id=channel_id)
    except Exception:
        logger.exception("Failed to fetch Telegram channel profile")
        return None
    fields = {
        "title": chat.title or "",
        "username": chat.username or "",
        "description": chat.description or "",
        "photo": chat.photo.big_file_unique_id if chat.photo else "",
    }
    try:
        members = await bot.get_chat_administrators(chat_id=channel_id)
    except (BadRequest, Forbidden) as e:
        # Logged at info: a standing configuration, checked every 30 minutes.
        logger.info("Telegram admin list of %s is not readable (is the bot a channel admin?): %s", channel_id, e)
        fields["admin_access"] = "нет"
        return fields
    except TelegramError:
        # A network hiccup: the list is unknown this time, not changed.
        logger.warning("Telegram admin list fetch failed", exc_info=True)
        return fields
    admins = sorted(
        ({"id": m.user.id, "name": _user_name(m.user), "status": str(m.status)} for m in members),
        key=lambda a: a["id"],
    )
    fields["admin_access"] = "есть"
    fields["admins"] = json.dumps(admins, ensure_ascii=False)
    return fields


class Telegram(Platform):
    id = "telegram"
    label = "Telegram"
    short = "TG"
    account = "аккаунт владельца канала"
    checklist = "telegram"
    profile_fields = {
        "title": ("название канала", TEXT),
        "username": ("@username канала", TEXT),
        "description": ("описание канала", TEXT),
        "photo": ("аватарка канала", IMAGE),
        "admin_access": ("доступ бота к списку админов", TEXT),
        "admins": ("админы канала", ADMINS),
    }

    def enabled(self, config) -> bool:
        return bool(config.telegram_channel_id)

    def target(self, config) -> str:
        return config.telegram_channel_id or ""

    async def collect(self, ctx: Context) -> Snapshot:
        count = await collect_telegram(ctx.bot, ctx.config.telegram_channel_id)
        return Snapshot(count, error=count is None)

    async def fetch_profile(self, ctx: Context) -> dict[str, str] | None:
        return await fetch_channel(ctx.bot, ctx.config.telegram_channel_id)

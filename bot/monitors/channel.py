"""Life of the channel: who joins and leaves, what is posted, how it is received.

TGStat sits in a channel's admins for this. The Bot API gives an admin bot
the same events directly: a chat_member update for every join and leave,
with the invite link it came through; a channel_post for every post; a
message_reaction_count when the reactions on a post change. They are kept
in SQLite and shown on the «📣 Канал» screen and as one line of the
report. Views, forwards and the citation index are not in the Bot API:
those stay with Telegram's own statistics.

Nothing here is alerted — a drop in followers is the followers monitor's
job. The switch in /modules decides whether events are recorded at all: a
join or a leave names a person, and switched off the bot keeps nothing.
"""

from __future__ import annotations

import html
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import ChatMember, ChatMemberUpdated, Message, MessageReactionCountUpdated, Update
from telegram.constants import ChatMemberStatus

from bot import callbacks, monitors
from bot.config import Config
from bot.db import Database, parse_utc, utcnow
from bot.i18n import plural, t
from bot.monitors import defang
from bot.monitors.comments import message_link

logger = logging.getLogger(__name__)

MONITOR_ID = "channel"
# Callback data of the screen.
CALLBACK = callbacks.CHANNEL

# How a subscriber came, as stored in channel_events.via: an invite link's
# name as it is, or one of these.
VIA_LINK = "link"        # a link without a name
VIA_REQUEST = "request"  # approved join request
VIA_FOLDER = "folder"    # a chat folder's invite link
VIA_DIRECT = ""          # search, a forward, a mention: no link involved
VIA_LABELS = {VIA_LINK: "по ссылке без имени", VIA_REQUEST: "по заявке", VIA_FOLDER: "через папку", VIA_DIRECT: "напрямую"}

# A post's kind, by its attachment; a service message is not a post.
POST_KINDS = ("photo", "video", "animation", "document", "audio", "voice", "video_note", "sticker", "poll", "text")
POST_LABELS = {
    "text": "текст", "photo": "фото", "video": "видео", "animation": "GIF", "document": "файл", "audio": "аудио",
    "voice": "голосовое", "video_note": "кружок", "sticker": "стикер", "poll": "опрос",
}

# A custom emoji has no character to show; a paid reaction is a star.
CUSTOM_EMOJI = "🙂"
PAID = "⭐"

PERIODS = (1, 7, 30)         # days: «за 24 часа», «за 7 дней», «за 30 дней»
STATS_DAYS = 30              # sources and top posts
TOP_POSTS = 3
RECENT_EVENTS = 5
REPORT_DAYS = 7


@dataclass(frozen=True)
class MemberEvent:
    kind: str          # join | leave
    user_id: int
    user_name: str
    via: str
    at: datetime


# ── Which chat is the channel ───────────────────────────────────────────────

def is_channel(chat, config: Config) -> bool:
    """Whether a chat is the tracked channel: TELEGRAM_CHANNEL_ID is either
    its numeric id or its @username."""
    target = (config.telegram_channel_id or "").strip()
    if not target or chat is None:
        return False
    if target.lstrip("-").isdigit():
        return getattr(chat, "id", None) == int(target)
    username = getattr(chat, "username", None) or ""
    return bool(username) and username.lower() == target.lstrip("@").lower()


# ── From an update to an event ──────────────────────────────────────────────

def _is_member(member: ChatMember) -> bool:
    if member.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
        return True
    return member.status == ChatMemberStatus.RESTRICTED and bool(getattr(member, "is_member", False))


def _user_name(user) -> str:
    name = user.full_name or str(user.id)
    return f"{name} (@{user.username})" if user.username else name


def member_event(change: ChatMemberUpdated) -> MemberEvent | None:
    """A join or a leave out of a chat_member update; None for a change of
    rights, a bot, or an update that moves nobody in or out."""
    user = change.new_chat_member.user
    if user.is_bot:
        return None
    was, now = _is_member(change.old_chat_member), _is_member(change.new_chat_member)
    if was == now:
        return None
    via = VIA_DIRECT
    if now:
        if change.invite_link is not None:
            via = change.invite_link.name or VIA_LINK
        elif change.via_chat_folder_invite_link:
            via = VIA_FOLDER
        elif change.via_join_request:
            via = VIA_REQUEST
    return MemberEvent("join" if now else "leave", user.id, _user_name(user), via, change.date)


def post_kind(message: Message) -> str | None:
    """What kind of post a channel message is; None for a service message
    (a pinned post, a changed title) which is not a publication."""
    for kind in POST_KINDS:
        if kind == "text":
            if message.text:
                return "text"
        elif getattr(message, kind, None):
            return kind
    return None


def reaction_counts(change: MessageReactionCountUpdated) -> dict[str, int]:
    """{emoji: count}; custom emoji are summed under one key, paid under ⭐."""
    counts: dict[str, int] = {}
    for reaction in change.reactions:
        emoji = getattr(reaction.type, "emoji", None)
        if emoji is None:
            emoji = PAID if reaction.type.type == "paid" else CUSTOM_EMOJI
        counts[emoji] = counts.get(emoji, 0) + reaction.total_count
    return counts


async def record(db: Database, config: Config, update: Update) -> str | None:
    """Keep what an update of the channel says; returns what was recorded
    ('join', 'leave', 'post', 'reactions') or None. A re-delivered update
    (Telegram resends what the bot did not acknowledge) changes nothing."""
    if not await monitors.is_on(db, config, MONITOR_ID):
        return None
    change = getattr(update, "chat_member", None)
    post = getattr(update, "channel_post", None)
    reactions = getattr(update, "message_reaction_count", None)
    try:
        if change is not None and is_channel(change.chat, config):
            event = member_event(change)
            if event is None:
                return None
            stored = await db.add_channel_event(
                change.chat.id, event.kind, event.user_id, event.user_name, event.via, event.at
            )
            return event.kind if stored else None
        if post is not None and is_channel(post.chat, config):
            kind = post_kind(post)
            if kind is None:
                return None
            stored = await db.add_channel_post(post.chat.id, post.message_id, kind, post.date)
            return "post" if stored else None
        if reactions is not None and is_channel(reactions.chat, config):
            counts = reaction_counts(reactions)
            await db.set_post_reactions(
                reactions.chat.id, reactions.message_id, sum(counts.values()), json.dumps(counts, ensure_ascii=False),
                reactions.date,
            )
            return "reactions"
    except Exception:
        logger.exception("Channel event not recorded")
    return None


# ── What the owner reads ────────────────────────────────────────────────────

def esc(value: object) -> str:
    """Names and link titles are other people's text: HTML-escaped, like
    bot.ui.esc, and a domain in them is defanged so it is not a link."""
    return html.escape(defang(str(value)), quote=False)


def _signed(joins: int, leaves: int) -> str:
    return f"+{joins} · −{leaves}"


def _posts(n: int) -> str:
    return f"{n} {plural(n, 'пост', 'поста', 'постов')}"


def _reactions(n: int) -> str:
    return f"{n} {plural(n, 'реакция', 'реакции', 'реакций')}"


def _joins(n: int) -> str:
    return f"+{n} {plural(n, 'подписка', 'подписки', 'подписок')}"


def _leaves(n: int) -> str:
    return f"−{n} {plural(n, 'отписка', 'отписки', 'отписок')}"


def via_label(via: str) -> str:
    """The source of a join as the owner reads it: a link's name in quotes, or the kind."""
    if via in VIA_LABELS:
        return t(VIA_LABELS[via])
    return t("по ссылке «{name}»").format(name=via)


def reactions_label(raw: str) -> str:
    """'{"👍": 23, "❤": 5}' → '👍 23 · ❤ 5'."""
    try:
        counts = json.loads(raw) if raw else {}
    except ValueError:
        return ""
    return " · ".join(f"{emoji} {n}" for emoji, n in sorted(counts.items(), key=lambda kv: -kv[1]))


def post_link(config: Config, chat_id: int, message_id: int) -> str:
    target = (config.telegram_channel_id or "").strip()
    username = target.lstrip("@") if target.startswith("@") else ""
    return message_link(chat_id, message_id, username)


async def has_data(db: Database) -> bool:
    return await db.channel_has_data()


async def report_line(db: Database, config: Config) -> str | None:
    """«📣 Канал за 7 дн.: +12 подписок · −3 отписки · 4 поста · 37 реакций»,
    or None while there is nothing to tell."""
    if not await monitors.is_on(db, config, MONITOR_ID) or not await has_data(db):
        return None
    counts = await db.channel_counts(utcnow() - timedelta(days=REPORT_DAYS))
    parts = [_joins(counts["joins"]), _leaves(counts["leaves"]), _posts(counts["posts"])]
    if counts["reactions"]:
        parts.append(_reactions(counts["reactions"]))
    return t("📣 Канал за {days} дн.: {parts}").format(days=REPORT_DAYS, parts=" · ".join(parts))


async def overview(db: Database, config: Config, tz: ZoneInfo) -> list[str]:
    """The lines of the «📣 Канал» screen below its title, Telegram HTML."""
    now = utcnow()
    lines: list[str] = []
    if not await has_data(db):
        lines.append(
            t("Пока пусто. Подписки, отписки, посты и реакции приходят, когда бот — админ канала; "
              "первые цифры появятся с первым событием.")
        )
        return lines
    for days in PERIODS:
        counts = await db.channel_counts(now - timedelta(days=days))
        head = t("За 24 часа") if days == 1 else t("За {days} дней").format(days=days)
        parts = [_signed(counts["joins"], counts["leaves"]), _posts(counts["posts"])]
        if counts["reactions"]:
            parts.append(_reactions(counts["reactions"]))
        lines.append(f"<b>{head}</b>: {' · '.join(parts)}")
    lines.append(t("Подписки · отписки · посты · реакции на посты за период"))

    since = now - timedelta(days=STATS_DAYS)
    sources = await db.channel_sources(since)
    if sources:
        lines += ["", t("<b>Откуда приходят</b> · {days} дней").format(days=STATS_DAYS)]
        lines += [f"• {esc(via_label(via))} — {n}" for via, n in sources]
    top = await db.channel_top_posts(since, TOP_POSTS)
    if top:
        lines += ["", t("<b>Больше всего реакций</b> · {days} дней").format(days=STATS_DAYS)]
        for post in top:
            when = parse_utc(post["posted_at"]).astimezone(tz).strftime("%d.%m") if post["posted_at"] else ""
            label = reactions_label(post["reactions_json"]) or str(post["reactions"])
            link = post_link(config, post["chat_id"], post["message_id"])
            lines.append(f"• {esc(label)} — <a href=\"{link}\">{when or t('пост')}</a>")
    recent = await db.channel_recent_events(RECENT_EVENTS)
    if recent:
        lines += ["", t("<b>Последние</b>")]
        for event in recent:
            at = parse_utc(event["occurred_at"]).astimezone(tz).strftime("%d.%m %H:%M")
            sign = "+" if event["kind"] == "join" else "−"
            line = f"• {at} {sign} {esc(event['user_name'])}"
            if event["kind"] == "join" and event["via"] != VIA_DIRECT:
                line += f" — {esc(via_label(event['via']))}"
            lines.append(line)
    return lines

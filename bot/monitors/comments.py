"""Comments of the channel: content the whole group gets blocked for.

A channel's discussion group is where drug shops, porn bots and «double
your crypto» accounts land, and a single such comment left standing is a
reason for Telegram to block the group — the channel's owner finds out from
a subscriber, hours later. The bot is already an admin of the channel; made
an admin of the discussion group too, it sees every comment, asks the
classifier (bot/classifier.py) what it is, and sends the owner a card for
anything that is not plainly fine: what was written, by whom, why it was
flagged, and three buttons — delete, delete and ban, «all fine».

The bot only reports. Nothing is deleted or banned without a tap: the
owner's taps are the labels (confirmed / false alarm) that the accuracy
table in /comments is built from, and that table is what any automatic
action would later be calibrated on. A category the group is blocked for
at high confidence rings (🔴); the rest is quiet (🟠) and waits for the
digest at night. Spam is reported quietly too — Defensy handles it.

Failures are «could not check», never «fine»: when the API is down the
owner hears once, and once more when it is back.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import anthropic
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.error import BadRequest, Forbidden, TelegramError

from bot import callbacks, classifier, humanize, monitors, notifier
from bot.classifier import REFUSED, Sample, Verdict
from bot.config import Config
from bot.db import Database, parse_utc, utc_stamp, utcnow
from bot.i18n import t
from bot.monitors import CRITICAL, WARNING, clean, defang
from bot.notifier import Priority

logger = logging.getLogger(__name__)

MONITOR_ID = "comments"
# Callback data of the card buttons: cm:<action>:<review id>.
CALLBACK = callbacks.COMMENTS
# A 🔴 card (rings through quiet hours) needs a blocked-for category at least
# this sure; anything flagged below is a 🟠 card.
CRITICAL_CONFIDENCE = 70
# The discussion group is looked up through the channel; how long the answer is kept.
GROUP_TTL = timedelta(hours=6)
GROUP_RETRY = timedelta(minutes=30)      # when the lookup failed or there is no group
ADMINS_TTL = timedelta(minutes=30)
EXCERPT_LEN = 300
STORED_TEXT_LEN = 1000
# Consecutive classifier failures before the owner hears about it.
API_FAIL_AFTER = 3
API_FAIL_KEY = "comments_api_fails"
API_FAIL_SINCE_KEY = "comments_api_fail_since"
# Comments classified at once. Every message in the group is reviewed as a
# task of its own, so a spam wave of two hundred messages used to be two
# hundred parallel API calls with pictures; now three at a time, the rest wait.
CONCURRENCY = 3
# The day the owner was told the daily limit (config.comments_daily_limit) is reached.
LIMIT_NOTIFIED_KEY = "comments_limit_notified"

# Category → what the card and the table call it (Russian key, t() at render).
LABELS = {
    "drugs": "наркотики",
    "sexual": "порнография",
    "csam": "сексуализация детей",
    "extremism": "экстремизм или терроризм",
    "fraud": "мошенничество",
    "spam": "спам или реклама",
    REFUSED: "модель отказалась оценивать",
}
MEDIA_LABELS = {
    "photo": "📷 фото", "video": "🎬 видео", "animation": "🎬 GIF", "sticker": "🩵 стикер",
    "document": "📎 файл",
}
# What the owner did, as the card shows it afterwards.
ACTIONS = {
    "deleted": "🗑 Удалено",
    "banned": "🔨 Удалено, автор забанен",
    "unbanned": "↩️ Бан снят, сообщение удалено",
}


@dataclass
class Watch:
    """The bot's view of the discussion group, kept in bot_data between updates."""

    client: anthropic.AsyncAnthropic | None = None
    group_id: int | None = None
    group_title: str = ""
    group_username: str = ""
    channel_id: int | None = None   # the channel the group belongs to: its own voice is not reviewed
    group_checked_at: datetime | None = None
    admins: set[int] = field(default_factory=set)
    admins_at: datetime | None = None
    semaphore: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(CONCURRENCY))


@dataclass(frozen=True)
class Comment:
    """A comment as the review needs it, extracted from the Telegram message."""

    chat_id: int
    message_id: int
    user_id: int | None               # None for a comment written under a channel's name
    user_name: str
    text: str
    media: str
    forwarded: bool
    image_file_id: str | None
    edited_at: datetime | None = None   # Telegram's edit_date: when this version of the text was written
    sender_chat_id: int | None = None   # the channel that wrote it, when a channel did


# ── The group and its admins ────────────────────────────────────────────────

async def group_id(bot: Bot, config: Config, watch: Watch) -> int | None:
    """The discussion group: COMMENTS_CHAT_ID, or the channel's linked group.
    Looked up at most once per GROUP_TTL; None when there is none."""
    now = utcnow()
    if watch.group_checked_at is not None:
        ttl = GROUP_TTL if watch.group_id is not None else GROUP_RETRY
        if now - watch.group_checked_at < ttl:
            return watch.group_id
    watch.group_checked_at = now
    try:
        if config.comments_chat_id is not None:
            found: int | None = config.comments_chat_id
        else:
            channel = await bot.get_chat(chat_id=config.telegram_channel_id)
            found = channel.linked_chat_id
        if found is not None:
            group = await bot.get_chat(chat_id=found)
            watch.group_title = group.title or ""
            watch.group_username = group.username or ""
            watch.channel_id = getattr(group, "linked_chat_id", None)
    except TelegramError:
        logger.warning("Discussion group lookup failed", exc_info=True)
        return watch.group_id
    if found != watch.group_id:
        logger.info("Discussion group: %s", found)
        watch.admins, watch.admins_at = set(), None
    watch.group_id = found
    return found


async def admin_ids(bot: Bot, watch: Watch) -> set[int]:
    """Admins of the group, refreshed every ADMINS_TTL: their comments are never reviewed."""
    now = utcnow()
    if watch.admins_at is not None and now - watch.admins_at < ADMINS_TTL:
        return watch.admins
    try:
        members = await bot.get_chat_administrators(chat_id=watch.group_id)
    except TelegramError:
        logger.warning("Group admin list fetch failed", exc_info=True)
        return watch.admins
    watch.admins = {m.user.id for m in members}
    watch.admins_at = now
    return watch.admins


# ── From a Telegram message to a sample ─────────────────────────────────────

def _author(message: Message) -> str:
    user = message.from_user
    name = user.full_name or str(user.id)
    return f"{name} (@{user.username})" if user.username else name


def _chat_name(chat) -> str:
    name = chat.title or str(chat.id)
    return f"📣 {name} (@{chat.username})" if chat.username else f"📣 {name}"


def extract(message: Message, channel_id: int | None = None) -> Comment | None:
    """The parts of a group message the review needs; None for a message that
    is not a comment to review: the channel's own posts and its owner speaking
    as the channel (channel_id — the group's linked channel), anonymous admins,
    other bots, service messages, voice notes and the like. A comment written
    under another channel's name — the usual face of a spam network — is a
    comment with that channel as its author (banned with ban_chat_sender_chat)."""
    if message.is_automatic_forward:
        return None
    sender = message.sender_chat
    if sender is not None:
        if sender.id == message.chat.id or (channel_id is not None and sender.id == channel_id):
            return None
        user_id, sender_chat_id, name = None, sender.id, _chat_name(sender)
    else:
        user = message.from_user
        if user is None or user.is_bot:
            return None
        user_id, sender_chat_id, name = user.id, None, _author(message)
    text = message.text or message.caption or ""
    media, file_id = "", None
    if message.photo:
        media = "photo"
        # The largest size the API accepts; sizes come smallest first.
        fitting = [p for p in message.photo if (p.file_size or 0) <= classifier.IMAGE_MAX_BYTES]
        file_id = (fitting[-1] if fitting else message.photo[0]).file_id
    else:
        for kind in ("video", "animation", "sticker", "document"):
            attachment = getattr(message, kind, None)
            if attachment is not None:
                media = kind
                thumbnail = getattr(attachment, "thumbnail", None)
                file_id = thumbnail.file_id if thumbnail is not None else None
                break
    if not text and not media:
        return None
    return Comment(
        chat_id=message.chat.id,
        message_id=message.message_id,
        user_id=user_id,
        user_name=name,
        text=text,
        media=media,
        forwarded=message.forward_origin is not None,
        image_file_id=file_id,
        edited_at=getattr(message, "edit_date", None),
        sender_chat_id=sender_chat_id,
    )


async def fetch_image(bot: Bot, file_id: str) -> bytes | None:
    try:
        file = await bot.get_file(file_id)
        if file.file_size and file.file_size > classifier.IMAGE_MAX_BYTES:
            return None
        return bytes(await file.download_as_bytearray())
    except TelegramError:
        logger.warning("Comment attachment download failed", exc_info=True)
        return None


def message_link(chat_id: int, message_id: int, username: str = "") -> str:
    if username:
        return f"https://t.me/{username}/{message_id}"
    # A supergroup id is -100<internal id>; t.me/c/ links use the internal id.
    internal = str(chat_id)
    internal = internal[4:] if internal.startswith("-100") else internal.lstrip("-")
    return f"https://t.me/c/{internal}/{message_id}"


# ── The card ────────────────────────────────────────────────────────────────

def _excerpt(text: str) -> str:
    text = " ".join(text.split())
    if len(text) > EXCERPT_LEN:
        text = text[: EXCERPT_LEN - 1] + "…"
    return defang(text)


def _buttons(review: dict) -> InlineKeyboardMarkup | None:
    rid = review["id"]
    if review["label"] == "false_positive":
        return None
    if review["action"] == "":
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(t("🗑 Удалить"), callback_data=f"{CALLBACK}:del:{rid}"),
                InlineKeyboardButton(t("🔨 Удалить и забанить"), callback_data=f"{CALLBACK}:ban:{rid}"),
            ],
            [InlineKeyboardButton(t("✅ Всё в порядке"), callback_data=f"{CALLBACK}:ok:{rid}")],
        ])
    if review["action"] == "banned":
        return InlineKeyboardMarkup([[InlineKeyboardButton(t("↩️ Разбанить"), callback_data=f"{CALLBACK}:unban:{rid}")]])
    # deleted or unbanned: the author can still be banned
    return InlineKeyboardMarkup([[InlineKeyboardButton(t("🔨 Забанить автора"), callback_data=f"{CALLBACK}:ban:{rid}")]])


def card(review: dict, channel_title: str = "", first_message: bool = False) -> tuple[str, InlineKeyboardMarkup | None]:
    """The owner's card for a flagged comment, plain text: headline, who and
    where, the text, why, what it means, the link; then its buttons."""
    category, confidence = review["category"], review["confidence"]
    dangerous = category in classifier.DANGEROUS
    icon = CRITICAL if dangerous and confidence >= CRITICAL_CONFIDENCE else WARNING
    label = t(LABELS.get(category, category))
    if category == REFUSED:
        head = t("{icon} Комментарии: {label}").format(icon=icon, label=label)
    else:
        head = t("{icon} Комментарии: {label} — уверенность {confidence}%").format(
            icon=icon, label=label, confidence=confidence
        )
    who = [clean(channel_title), defang(review["user_name"])]   # a display name can be a link too
    if first_message:
        who.append(t("первое сообщение в группе"))
    if review.get("edited_at"):
        who.append(t("✏️ отредактирован после публикации"))
    if review["media"]:
        who.append(t(MEDIA_LABELS.get(review["media"], review["media"])))
    lines = [head, " · ".join(part for part in who if part)]
    if review["text"]:
        lines.append(f"«{_excerpt(review['text'])}»")
    if review["reason"]:
        lines.append(t("Почему: {reason}").format(reason=defang(review["reason"])))
    if category == REFUSED:
        lines.append(t("Модель не стала оценивать это сообщение — обычно так бывает с самым тяжёлым контентом. Посмотри сам."))
    elif dangerous:
        lines.append(t("За такой контент Telegram блокирует всю группу. Я только сообщаю — удалить или забанить можно кнопкой."))
    else:
        lines.append(t("Группе это не грозит, но и не нужно. Удалить или забанить можно кнопкой."))
    if review["action"]:
        lines.append(t(ACTIONS[review["action"]]))
    if review["label"] == "false_positive":
        lines.append(t("✅ Отмечено: ложная тревога — учту в статистике"))
    if review["link"]:
        lines.append(review["link"])
    return "\n".join(lines), _buttons(review)


# ── The review ──────────────────────────────────────────────────────────────

async def _api_failed(bot: Bot, config: Config, db: Database, error: Exception) -> None:
    fails = int(await db.get_setting(API_FAIL_KEY) or "0") + 1
    await db.set_setting(API_FAIL_KEY, str(fails))
    if fails == 1:
        await db.set_setting(API_FAIL_SINCE_KEY, utcnow().isoformat())
    if fails == API_FAIL_AFTER:
        await notifier.send(
            bot, config, db,
            humanize.alert(
                t("🟠 Комментарии: проверка не работает {n} раза подряд").format(n=fails), "comments_down",
                type(error).__name__, config.comments_model,
            ),
            Priority.NORMAL, actions=(callbacks.COMMENTS,), monitor=MONITOR_ID,
        )


async def _api_recovered(bot: Bot, config: Config, db: Database) -> None:
    """The check works again: after an alerted failure, one message with how
    long it did not, from the first failed check of the series."""
    fails = int(await db.get_setting(API_FAIL_KEY) or "0")
    if fails:
        await db.set_setting(API_FAIL_KEY, "0")
    if fails >= API_FAIL_AFTER:
        raw = await db.get_setting(API_FAIL_SINCE_KEY)
        try:
            since = parse_utc(raw) if raw else None
        except ValueError:
            since = None
        how_long = humanize.lasted(since, None, utcnow(), await notifier.owner_tz(db, config))
        await notifier.send(
            bot, config, db, humanize.recovery(t("✅ Комментарии: проверка снова работает"), how_long, "Не работала"),
            Priority.NORMAL,
        )


async def over_daily_limit(bot: Bot, config: Config, db: Database) -> bool:
    """COMMENTS_DAILY_LIMIT classifications per UTC day, so a spam wave cannot
    run up an unbounded API bill; the owner hears once a day when it is reached
    and the rest of the day's comments go unchecked — said in as many words."""
    limit = config.comments_daily_limit
    if not limit:
        return False
    day = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    if await db.count_reviews_since(day) < limit:
        return False
    today = day.date().isoformat()
    if await db.get_setting(LIMIT_NOTIFIED_KEY) != today:
        await db.set_setting(LIMIT_NOTIFIED_KEY, today)
        await notifier.send(
            bot, config, db,
            humanize.alert(
                t("🟠 Комментарии: дневной лимит проверок ({limit}) исчерпан").format(limit=limit), "comments_limit",
                f"COMMENTS_DAILY_LIMIT={limit}",
            ),
            Priority.NORMAL, actions=(callbacks.COMMENTS,), monitor=MONITOR_ID,
        )
    return True


def _client(config: Config, watch: Watch) -> anthropic.AsyncAnthropic:
    if watch.client is None:
        watch.client = classifier.make_client(config.anthropic_api_key)
    return watch.client


async def review(
    bot: Bot, config: Config, db: Database, watch: Watch, message: Message, edited: bool = False,
) -> int | None:
    """Look at one group message; returns the review id when a card was sent.

    Skips what is not a comment (see extract), a group other than the channel's
    own, and the group's admins. Every classified comment is recorded; only a
    flagged one becomes a card. edited — Telegram's edited_message: a comment
    that was fine when posted and is a drug shop after an edit is looked at
    again; one the owner already deleted or banned is not."""
    if not await monitors.is_on(db, config, MONITOR_ID):
        return None
    group = await group_id(bot, config, watch)
    if group is None or message.chat.id != group:
        return None
    comment = extract(message, watch.channel_id)
    if comment is None:
        return None
    if comment.user_id is not None and (
        comment.user_id == config.admin_chat_id or comment.user_id in await admin_ids(bot, watch)
    ):
        return None
    before = await db.get_review_by_message(comment.chat_id, comment.message_id)
    if before is not None:
        if not edited or before["action"] in ("deleted", "banned"):
            return None   # Telegram re-delivered the update, or the comment is gone
        if comment.edited_at is not None and before["edited_at"] == utc_stamp(comment.edited_at):
            return None   # this very edit was looked at already: Telegram re-delivered it
    if await over_daily_limit(bot, config, db):
        return None

    # The author's stored rows include this comment itself once it has one:
    # an edit of their first comment is still their first message.
    first_message = await db.count_author_reviews(
        comment.chat_id, comment.user_id, comment.sender_chat_id
    ) == (0 if before is None else 1)
    async with watch.semaphore:
        image = await fetch_image(bot, comment.image_file_id) if comment.image_file_id else None
        sample = Sample(
            text=comment.text, channel_title=watch.group_title, first_message=first_message,
            forwarded=comment.forwarded, media=comment.media, image=image,
        )
        try:
            verdict = await classifier.classify(_client(config, watch), config.comments_model, sample, config.lang)
        except (anthropic.APIError, ValueError, KeyError, TypeError) as e:
            logger.warning("Comment classification failed: %s", e)
            await _api_failed(bot, config, db, e)
            return None
    await _api_recovered(bot, config, db)
    return await record_and_report(bot, config, db, watch, comment, verdict, first_message, before, edited)


async def record_and_report(
    bot: Bot, config: Config, db: Database, watch: Watch, comment: Comment, verdict: Verdict, first_message: bool,
    before: dict | None = None, edited: bool = False,
) -> int | None:
    """Store the verdict and send the card of a flagged comment. before — the
    stored review of an edited comment: a flagged edit replaces it and gets a
    card of its own; an edit the model calls fine leaves a flagged card as it
    was (the owner still decides on what was posted). edited — the comment
    was edited, whether or not it was looked at when it was posted.

    The card is held in the queue when Telegram does not take it (a flood
    limit in a spam wave): the update is not sent again, so a lost card would
    be lost for good."""
    # Only a card needs the text and the name; a comment the model called fine
    # keeps its author's id alone (for «first message in the group»).
    stored_text = " ".join(comment.text.split())[:STORED_TEXT_LEN] if verdict.flagged else ""
    stored_name = comment.user_name if verdict.flagged else ""
    if before is not None:
        review_id = before["id"]
        if not verdict.flagged:
            await db.touch_review(review_id, comment.edited_at)
            return None
        await db.rereview(review_id, stored_name, stored_text, comment.media, verdict.category, verdict.confidence,
                          verdict.reason, comment.edited_at)
    else:
        link = message_link(comment.chat_id, comment.message_id, watch.group_username)
        review_id = await db.add_review(
            comment.chat_id, comment.message_id, comment.user_id, stored_name, stored_text, comment.media,
            link, verdict.category, verdict.confidence, verdict.reason, sender_chat_id=comment.sender_chat_id,
        )
        if review_id is not None and edited:
            # Posted before the bot looked: the card still says it was edited.
            await db.touch_review(review_id, comment.edited_at)
        if review_id is None or not verdict.flagged:
            return None
    text, markup = card(await db.get_review(review_id), watch.group_title, first_message)
    await notifier.send(bot, config, db, text, notifier.priority_for(text), reply_markup=markup, no_preview=True,
                        hold_on_error=True)
    return review_id


# ── The buttons ─────────────────────────────────────────────────────────────

def _rights_note(error: TelegramError) -> str:
    reason = str(error).lower()
    if "not enough rights" in reason or "have no rights" in reason or isinstance(error, Forbidden):
        return t("Нет прав: сделай бота админом группы с правом удалять сообщения и блокировать участников.")
    if "message to delete not found" in reason or "message can't be deleted" in reason:
        return t("Сообщение уже удалено.")
    if "user is an administrator" in reason or "can't remove chat owner" in reason:
        return t("Автор — админ группы, его нельзя забанить.")
    if "participant_id_invalid" in reason or "user not found" in reason:
        return t("Telegram не нашёл этого пользователя.")
    return t("Telegram ответил ошибкой: {error}").format(error=type(error).__name__)


async def _delete(bot: Bot, review: dict) -> str | None:
    """Delete the comment; None when it is gone (now or already), else the reason."""
    try:
        await bot.delete_message(chat_id=review["chat_id"], message_id=review["message_id"])
    except BadRequest as e:
        if "message to delete not found" in str(e).lower() or "message can't be deleted" in str(e).lower():
            return None
        return _rights_note(e)
    except TelegramError as e:
        return _rights_note(e)
    return None


async def act(bot: Bot, db: Database, review_id: int, action: str) -> tuple[dict | None, str]:
    """A button press: del | ban | ok | unban. Returns the review as it is now
    and a short note for the toast; the review is None when the id is unknown."""
    review = await db.get_review(review_id)
    if review is None:
        return None, t("Эта карточка устарела")
    if action == "ok":
        await db.update_review(review_id, label="false_positive")
        note = t("Отмечено как ложная тревога")
    elif action == "del":
        problem = await _delete(bot, review)
        if problem:
            return review, problem
        await db.update_review(review_id, action="deleted", label="confirmed")
        note = t("Удалено")
    elif action == "ban":
        try:
            if review.get("sender_chat_id"):
                # Written under a channel's name: the channel is banned from the group; the comment goes below.
                await bot.ban_chat_sender_chat(chat_id=review["chat_id"], sender_chat_id=review["sender_chat_id"])
            elif review["user_id"] is None:
                return review, t("Автор неизвестен")
            else:
                # revoke_messages drops everything the author wrote in the group, this comment included.
                await bot.ban_chat_member(chat_id=review["chat_id"], user_id=review["user_id"], revoke_messages=True)
        except TelegramError as e:
            return review, _rights_note(e)
        await _delete(bot, review)
        await db.update_review(review_id, action="banned", label="confirmed")
        note = t("Удалено, автор забанен")
    elif action == "unban":
        try:
            if review.get("sender_chat_id"):
                await bot.unban_chat_sender_chat(chat_id=review["chat_id"], sender_chat_id=review["sender_chat_id"])
            else:
                await bot.unban_chat_member(chat_id=review["chat_id"], user_id=review["user_id"], only_if_banned=True)
        except TelegramError as e:
            return review, _rights_note(e)
        await db.update_review(review_id, action="unbanned")
        note = t("Бан снят")
    else:
        return review, t("Эта карточка устарела")
    return await db.get_review(review_id), note

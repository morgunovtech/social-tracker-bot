"""The comment monitor: what is reviewed, what becomes a card, what the
buttons do — with a fake classifier and a fake Telegram."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import re
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import anthropic
import pytest
from conftest import ADMIN_ID, buttons
from telegram.error import BadRequest, Forbidden
from telegram.ext import ApplicationHandlerStop

from bot import classifier, handlers, monitors, ui
from bot.classifier import Sample, Verdict
from bot.config import Config
from bot.monitors import comments

CHANNEL = "@test_channel"
GROUP = -1001234567890
OTHER_GROUP = -1009999999999
ADMIN_OF_GROUP = 300
CHANNEL_ID = -1001000000001                       # the channel the group is linked to
SPAM_CHANNEL = SimpleNamespace(id=-1007777777777, title="Крипто-сигналы", username="cryptosignals", type="channel")


@pytest.fixture
def config(tmp_path) -> Config:
    return dataclasses.replace(Config.from_env(), db_path=str(tmp_path / "followers.db"), anthropic_api_key="sk-test")


@pytest.fixture
def group_bot(bot):
    bot.chats[CHANNEL] = SimpleNamespace(linked_chat_id=GROUP)
    bot.chats[GROUP] = SimpleNamespace(title="Обсуждение", username=None, linked_chat_id=CHANNEL_ID)
    bot.admins = [SimpleNamespace(user=SimpleNamespace(id=ADMIN_OF_GROUP))]
    return bot


@pytest.fixture
def verdicts(monkeypatch):
    """The classifier answers from this queue; .samples keeps what it was asked."""
    queue: list = []
    samples: list[Sample] = []

    async def fake_classify(client, model, sample, lang="ru"):
        samples.append(sample)
        answer = queue.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(classifier, "classify", fake_classify)
    monkeypatch.setattr(classifier, "make_client", lambda key: object())
    queue_ns = SimpleNamespace(queue=queue, samples=samples)
    return queue_ns


def message(
    text: str = "", user_id: int = 5, chat_id: int = GROUP, message_id: int = 7, *, photo: list | None = None,
    video=None, is_bot: bool = False, sender_chat=None, automatic: bool = False, forwarded: bool = False,
    username: str | None = "ivan", caption: str = "", edit_date=None,
):
    return SimpleNamespace(
        message_id=message_id,
        edit_date=edit_date,
        chat=SimpleNamespace(id=chat_id, type="supergroup"),
        from_user=SimpleNamespace(id=user_id, is_bot=is_bot, full_name="Иван", username=username),
        sender_chat=sender_chat,
        is_automatic_forward=automatic,
        text=text,
        caption=caption,
        photo=photo or [],
        video=video,
        animation=None,
        sticker=None,
        document=None,
        forward_origin=object() if forwarded else None,
    )


def dangerous(confidence: int = 92) -> Verdict:
    return Verdict("drugs", confidence, "предложение купить с контактом")


# --- the classifier call ---------------------------------------------------

def test_sample_content_carries_facts_text_and_a_known_image():
    jpeg = b"\xff\xd8\xff" + b"\0" * 10
    content = classifier.build_content(
        Sample("  купить   здесь ", "Канал", first_message=True, forwarded=True, media="photo", image=jpeg)
    )
    assert content[0]["type"] == "image" and content[0]["source"]["media_type"] == "image/jpeg"
    body = content[1]["text"]
    assert "Channel: Канал" in body and "first message" in body and "forwarded" in body
    assert "Attachment: photo" in body and body.endswith("Comment text:\nкупить здесь")

    no_text = classifier.build_content(Sample("", "", False, False, media="video", image=None))
    assert no_text[0]["type"] == "text" and "(no preview available)" in no_text[0]["text"]
    assert no_text[0]["text"].endswith("(no text)")

    unknown = classifier.build_content(Sample("x", "", False, False, media="document", image=b"%PDF-1.4"))
    assert [c["type"] for c in unknown] == ["text"]                    # not an image the API takes

    huge = classifier.build_content(Sample("x", "", False, False, media="photo", image=b"\xff\xd8\xff" + b"\0" * classifier.IMAGE_MAX_BYTES))
    assert [c["type"] for c in huge] == ["text"]

    long_text = classifier.build_content(Sample("а" * 5000, "", False, False))
    assert len(long_text[0]["text"]) < classifier.TEXT_MAX_CHARS + 200


def _response(payload: dict | None, stop_reason: str = "end_turn", explanation: str | None = None):
    content = [SimpleNamespace(type="text", text=json.dumps(payload))] if payload is not None else []
    details = SimpleNamespace(explanation=explanation) if explanation is not None else None
    return SimpleNamespace(stop_reason=stop_reason, content=content, stop_details=details)


def test_verdict_parsing():
    verdict = classifier.parse_verdict(_response({"category": "fraud", "confidence": 140, "reason": " раздача  крипты "}))
    assert verdict == Verdict("fraud", 100, "раздача крипты") and verdict.flagged and verdict.dangerous
    ok = classifier.parse_verdict(_response({"category": "ok", "confidence": 95, "reason": "спор о политике"}))
    assert not ok.flagged and not ok.dangerous
    refused = classifier.parse_verdict(_response(None, "refusal", "declined"))
    assert refused.category == classifier.REFUSED and refused.reason == "declined" and refused.flagged
    with pytest.raises(ValueError):
        classifier.parse_verdict(_response({"category": "weird", "confidence": 1, "reason": ""}))
    # Thinking counts toward max_tokens: a reply that ends there has no text, and is not «fine».
    with pytest.raises(ValueError, match="max_tokens"):
        classifier.parse_verdict(_response(None, "max_tokens"))
    with pytest.raises(ValueError, match="no text"):
        classifier.parse_verdict(_response(None, "end_turn"))
    assert classifier.MAX_TOKENS >= 4096                        # room for the thinking, not only the JSON
    assert set(classifier.SCHEMA["properties"]["category"]["enum"]) == set(classifier.CATEGORIES)
    # The API refuses minimum/maximum on an integer (HTTP 400): the range is clamped here instead.
    assert not {"minimum", "maximum"} & set(classifier.SCHEMA["properties"]["confidence"])


def test_the_sdk_accepts_what_classify_sends():
    """The call is not made offline; the parameters must at least exist."""
    import inspect

    from anthropic.resources.beta.messages import AsyncMessages

    params = inspect.signature(AsyncMessages.create).parameters
    assert {"model", "max_tokens", "system", "messages", "output_config", "betas", "fallbacks"} <= set(params)


# --- what counts as a comment -------------------------------------------------

def test_extract_skips_what_is_not_a_person_commenting():
    assert comments.extract(message("hi", is_bot=True)) is None
    assert comments.extract(message("hi", sender_chat=SimpleNamespace(id=GROUP), is_bot=True)) is None   # an anonymous admin
    owner = message("hi", sender_chat=SimpleNamespace(id=CHANNEL_ID), is_bot=True)
    assert comments.extract(owner, CHANNEL_ID) is None                                     # the owner, as the channel
    as_channel = comments.extract(message("buy", sender_chat=SPAM_CHANNEL, is_bot=True), CHANNEL_ID)
    assert as_channel.user_id is None and as_channel.sender_chat_id == SPAM_CHANNEL.id   # another channel: reviewed
    assert as_channel.user_name == "📣 Крипто-сигналы (@cryptosignals)"
    assert comments.extract(message("post", automatic=True)) is None
    assert comments.extract(message("")) is None                                           # a poll, a contact, a voice note
    comment = comments.extract(message("Привет", forwarded=True))
    assert comment.user_name == "Иван (@ivan)" and comment.forwarded and comment.media == "" and comment.image_file_id is None
    assert comments.extract(message("x", username=None)).user_name == "Иван"


def test_extract_picks_the_largest_photo_the_api_takes_and_a_video_thumbnail():
    photo = [
        SimpleNamespace(file_id="s", file_size=10_000),
        SimpleNamespace(file_id="m", file_size=500_000),
        SimpleNamespace(file_id="l", file_size=classifier.IMAGE_MAX_BYTES + 1),
    ]
    comment = comments.extract(message("", photo=photo, caption="подпись"))
    assert comment.media == "photo" and comment.image_file_id == "m" and comment.text == "подпись"
    video = SimpleNamespace(thumbnail=SimpleNamespace(file_id="thumb"))
    assert comments.extract(message("", video=video)).image_file_id == "thumb"
    assert comments.extract(message("", video=SimpleNamespace(thumbnail=None))).media == "video"


def test_message_link():
    assert comments.message_link(-1001234567890, 7) == "https://t.me/c/1234567890/7"
    assert comments.message_link(-1001234567890, 7, "chat") == "https://t.me/chat/7"


async def test_group_is_the_channels_linked_group_and_is_cached(group_bot, config):
    watch = comments.Watch()
    assert await comments.group_id(group_bot, config, watch) == GROUP and watch.group_title == "Обсуждение"
    group_bot.chats.clear()
    assert await comments.group_id(group_bot, config, watch) == GROUP                   # from the cache

    pinned = dataclasses.replace(config, comments_chat_id=OTHER_GROUP)
    group_bot.chats[OTHER_GROUP] = SimpleNamespace(title="Своя группа", username="own")
    assert await comments.group_id(group_bot, pinned, comments.Watch()) == OTHER_GROUP

    no_group = comments.Watch()
    group_bot.chats[CHANNEL] = SimpleNamespace(linked_chat_id=None)
    assert await comments.group_id(group_bot, config, no_group) is None


# --- the review -------------------------------------------------------------

async def test_a_dangerous_comment_becomes_a_ringing_card(group_bot, config, db, verdicts):
    verdicts.queue.append(dangerous())
    watch = comments.Watch()
    review_id = await comments.review(group_bot, config, db, watch, message("Есть мефф, пиши в лс t.me/shop"))
    assert review_id == 1
    (text,) = group_bot.messages
    assert text.startswith("🔴 Комментарии: наркотики — уверенность 92%")
    assert "Обсуждение · Иван (@ivan) · первое сообщение в группе" in text
    assert "«Есть мефф, пиши в лс t[.]me/shop»" in text                                   # defanged
    assert "Почему: предложение купить с контактом" in text
    assert "блокирует всю группу" in text and text.endswith("https://t.me/c/1234567890/7")
    assert group_bot.silent == [False]                                                   # rings
    assert buttons(group_bot.markups[0]) == {"cm:del:1": "🗑 Удалить", "cm:ban:1": "🔨 Удалить и забанить", "cm:ok:1": "✅ Всё в порядке"}
    assert verdicts.samples[0].first_message and verdicts.samples[0].channel_title == "Обсуждение"
    stored = await db.get_review(1)
    assert stored["text"] == "Есть мефф, пиши в лс t.me/shop" and stored["category"] == "drugs" and stored["action"] == ""


async def test_an_ok_comment_is_recorded_without_text_and_without_a_card(group_bot, config, db, verdicts):
    verdicts.queue.append(Verdict("ok", 97, "обычный комментарий"))
    assert await comments.review(group_bot, config, db, comments.Watch(), message("Спасибо за пост")) is None
    assert (await db.get_review(1))["user_name"] == ""        # only a card needs the author's name
    assert group_bot.messages == []
    stored = await db.get_review_by_message(GROUP, 7)
    assert stored["category"] == "ok" and stored["text"] == ""
    assert (await db.review_stats())["checked"] == 1


async def test_spam_and_low_confidence_are_quiet_cards(group_bot, config, db, verdicts):
    verdicts.queue += [Verdict("spam", 88, "реклама канала"), dangerous(55)]
    await comments.review(group_bot, config, db, comments.Watch(), message("Подпишись на мой канал", message_id=1))
    await comments.review(group_bot, config, db, comments.Watch(), message("что-то мутное", message_id=2))
    assert [m[:1] for m in group_bot.messages] == ["🟠", "🟠"] and group_bot.silent == [True, True]
    assert "Группе это не грозит" in group_bot.messages[0]


async def test_the_daily_limit_stops_the_checks_and_is_said_once(group_bot, config, db, verdicts):
    limited = dataclasses.replace(config, comments_daily_limit=2)
    verdicts.queue += [Verdict("ok", 90, ""), Verdict("ok", 90, "")]
    watch = comments.Watch()
    for i in range(4):
        await comments.review(group_bot, limited, db, watch, message("x", message_id=i))
    assert len(verdicts.samples) == 2                                   # the third and fourth were not asked
    assert len(group_bot.messages) == 1 and group_bot.messages[0].startswith("🟠 Комментарии: дневной лимит проверок (2)")
    assert "COMMENTS_DAILY_LIMIT" in group_bot.messages[0]
    unlimited = dataclasses.replace(config, comments_daily_limit=0)
    verdicts.queue.append(Verdict("ok", 90, ""))
    await comments.review(group_bot, unlimited, db, watch, message("x", message_id=9))
    assert len(verdicts.samples) == 3


async def test_classifications_run_a_few_at_a_time(group_bot, config, db, monkeypatch):
    running, peak = [0], [0]

    async def slow_classify(client, model, sample, lang="ru"):
        running[0] += 1
        peak[0] = max(peak[0], running[0])
        await asyncio.sleep(0.01)
        running[0] -= 1
        return Verdict("ok", 90, "")

    monkeypatch.setattr(classifier, "classify", slow_classify)
    monkeypatch.setattr(classifier, "make_client", lambda key: object())
    watch = comments.Watch()
    await asyncio.gather(*(comments.review(group_bot, config, db, watch, message("x", message_id=i)) for i in range(8)))
    assert peak[0] == comments.CONCURRENCY and (await db.review_stats())["checked"] == 8


def test_a_display_name_that_is_a_link_is_defanged():
    review = {"id": 1, "category": "spam", "confidence": 60, "user_name": "buy at evil.com (@x)", "media": "",
              "text": "", "reason": "", "action": "", "label": "", "link": ""}
    text, _ = comments.card(review, "Channel")
    assert "evil[.]com" in text and "evil.com" not in text


async def test_a_photo_is_downloaded_and_sent_along(group_bot, config, db, verdicts):
    group_bot.files["m"] = b"\xff\xd8\xff-jpeg"
    verdicts.queue.append(Verdict("sexual", 90, "порнография на фото"))
    photo = [SimpleNamespace(file_id="m", file_size=100)]
    await comments.review(group_bot, config, db, comments.Watch(), message("", photo=photo))
    assert verdicts.samples[0].image == b"\xff\xd8\xff-jpeg" and verdicts.samples[0].media == "photo"
    assert "📷 фото" in group_bot.messages[0]


async def test_who_is_not_reviewed(group_bot, config, db, verdicts):
    watch = comments.Watch()
    assert await comments.review(group_bot, config, db, watch, message("x", user_id=ADMIN_OF_GROUP)) is None
    assert await comments.review(group_bot, config, db, watch, message("x", user_id=ADMIN_ID)) is None   # the owner
    assert await comments.review(group_bot, config, db, watch, message("x", chat_id=OTHER_GROUP)) is None
    await monitors.toggle(db, "comments")
    assert await comments.review(group_bot, config, db, watch, message("x")) is None
    await monitors.toggle(db, "comments")
    assert verdicts.samples == [] and group_bot.messages == []
    assert not await monitors.is_on(db, dataclasses.replace(config, anthropic_api_key=None), "comments")


async def test_a_comment_written_as_a_channel_is_reviewed_and_the_channel_banned(group_bot, config, db, verdicts):
    verdicts.queue += [dangerous(), dangerous()]
    watch = comments.Watch()
    # The owner's own channel speaking in its group and an anonymous admin are not reviewed.
    own = message("x", sender_chat=SimpleNamespace(id=CHANNEL_ID), is_bot=True)
    assert await comments.review(group_bot, config, db, watch, own) is None
    anonymous = message("x", sender_chat=SimpleNamespace(id=GROUP), is_bot=True)
    assert await comments.review(group_bot, config, db, watch, anonymous) is None
    assert verdicts.samples == [] and watch.channel_id == CHANNEL_ID

    rid = await comments.review(group_bot, config, db, watch, message("удвою крипту", sender_chat=SPAM_CHANNEL, is_bot=True))
    assert rid == 1 and verdicts.samples[0].first_message is True
    (text,) = group_bot.messages
    assert "📣 Крипто-сигналы (@cryptosignals)" in text and "первое сообщение в группе" in text

    review, note = await comments.act(group_bot, db, rid, "ban")
    assert note == "Удалено, автор забанен" and group_bot.banned_chats == [(GROUP, SPAM_CHANNEL.id)]
    assert group_bot.banned == [] and group_bot.deleted == [(GROUP, 7)] and review["action"] == "banned"
    review, note = await comments.act(group_bot, db, rid, "unban")
    assert note == "Бан снят" and group_bot.unbanned_chats == [(GROUP, SPAM_CHANNEL.id)] and group_bot.unbanned == []

    # The channel's next comment is not a first one.
    again = message("ещё раз", message_id=8, sender_chat=SPAM_CHANNEL, is_bot=True)
    assert await comments.review(group_bot, config, db, watch, again) == 2
    assert verdicts.samples[1].first_message is False


async def test_a_redelivered_update_is_not_reviewed_twice(group_bot, config, db, verdicts):
    verdicts.queue.append(dangerous())
    watch = comments.Watch()
    assert await comments.review(group_bot, config, db, watch, message("x")) == 1
    assert await comments.review(group_bot, config, db, watch, message("x")) is None
    assert len(verdicts.samples) == 1 and len(group_bot.messages) == 1


async def test_the_second_message_of_an_author_is_not_a_first(group_bot, config, db, verdicts):
    verdicts.queue += [Verdict("ok", 90, ""), dangerous()]
    watch = comments.Watch()
    await comments.review(group_bot, config, db, watch, message("раз", message_id=1))
    await comments.review(group_bot, config, db, watch, message("два", message_id=2))
    assert not verdicts.samples[1].first_message and "первое сообщение" not in group_bot.messages[0]


async def test_api_failures_are_reported_once_and_the_recovery_once(group_bot, config, db, verdicts):
    error = anthropic.APIConnectionError(request=SimpleNamespace())
    verdicts.queue += [error, error, error, error, Verdict("ok", 90, "")]
    watch = comments.Watch()
    for i in range(5):
        await comments.review(group_bot, config, db, watch, message("x", message_id=i))
    assert len(group_bot.messages) == 2
    alert, back = group_bot.messages
    assert alert.startswith("🟠 Комментарии: проверка не работает 3 раза подряд\n\n")
    assert "Что делать:" in alert and alert.endswith("Тех.: APIConnectionError · claude-opus-5-5")
    # The recovery says how long the check was down, from its first failure.
    assert re.fullmatch(r"✅ Комментарии: проверка снова работает\. Не работала 1 мин \(\d\d:\d\d–\d\d:\d\d\)\. "
                        r"Ничего делать не нужно\.", back), back
    assert (await db.review_stats())["checked"] == 1                                   # a failure is not a verdict


async def test_a_refusal_is_a_card_of_its_own(group_bot, config, db, verdicts):
    verdicts.queue.append(Verdict(classifier.REFUSED, 0, ""))
    await comments.review(group_bot, config, db, comments.Watch(), message("…"))
    (text,) = group_bot.messages
    assert text.startswith("🟠 Комментарии: модель отказалась оценивать\n") and "Посмотри сам" in text
    assert "уверенность" not in text and group_bot.silent == [True]


# --- the buttons ----------------------------------------------------------

async def flagged(group_bot, config, db, verdicts) -> int:
    verdicts.queue.append(dangerous())
    return await comments.review(group_bot, config, db, comments.Watch(), message("x"))


async def test_delete_ban_unban_and_false_alarm(group_bot, config, db, verdicts):
    rid = await flagged(group_bot, config, db, verdicts)

    review, note = await comments.act(group_bot, db, rid, "del")
    assert note == "Удалено" and group_bot.deleted == [(GROUP, 7)]
    assert review["action"] == "deleted" and review["label"] == "confirmed"
    text, markup = comments.card(review, "Обсуждение")
    assert "🗑 Удалено" in text and buttons(markup) == {f"cm:ban:{rid}": "🔨 Забанить автора"}

    review, note = await comments.act(group_bot, db, rid, "ban")
    assert note == "Удалено, автор забанен" and group_bot.banned == [(GROUP, 5)]
    text, markup = comments.card(review, "Обсуждение")
    assert "автор забанен" in text and buttons(markup) == {f"cm:unban:{rid}": "↩️ Разбанить"}

    review, note = await comments.act(group_bot, db, rid, "unban")
    assert note == "Бан снят" and group_bot.unbanned == [(GROUP, 5)]
    assert review["action"] == "unbanned" and review["label"] == "confirmed"
    text, markup = comments.card(review, "Обсуждение")
    assert "Бан снят" in text and f"cm:ban:{rid}" in buttons(markup)

    review, note = await comments.act(group_bot, db, rid, "ok")
    assert note == "Отмечено как ложная тревога" and review["label"] == "false_positive"
    text, markup = comments.card(review, "Обсуждение")
    assert "ложная тревога" in text and markup is None

    assert await comments.act(group_bot, db, 999, "del") == (None, "Эта карточка устарела")
    assert (await comments.act(group_bot, db, rid, "fly"))[1] == "Эта карточка устарела"


async def test_a_missing_right_is_explained_and_changes_nothing(group_bot, config, db, verdicts):
    rid = await flagged(group_bot, config, db, verdicts)
    group_bot.fail_with = BadRequest("Not enough rights to delete a message")
    review, note = await comments.act(group_bot, db, rid, "del")
    assert note.startswith("Нет прав") and review["action"] == "" and review["label"] == ""
    group_bot.fail_with = Forbidden("bot was kicked")
    assert (await comments.act(group_bot, db, rid, "ban"))[1].startswith("Нет прав")
    group_bot.fail_with = BadRequest("Can't remove chat owner")
    assert (await comments.act(group_bot, db, rid, "ban"))[1] == "Автор — админ группы, его нельзя забанить."
    group_bot.fail_with = BadRequest("Message to delete not found")
    review, note = await comments.act(group_bot, db, rid, "del")
    assert note == "Удалено" and review["action"] == "deleted"                      # already gone counts as done


async def test_stats_screen_counts_marks(group_bot, config, db, verdicts):
    verdicts.queue += [dangerous(), Verdict("fraud", 80, ""), Verdict("spam", 70, ""), Verdict("ok", 95, "")]
    watch = comments.Watch()
    for i in range(4):
        await comments.review(group_bot, config, db, watch, message("x", message_id=i))
    await comments.act(group_bot, db, 1, "ban")
    await comments.act(group_bot, db, 2, "ok")
    screen = await ui.comments_screen(db, config)
    assert "Режим: только сообщаю" in screen.text and "группа обсуждения канала @test_channel" in screen.text
    assert "Проверено комментариев: 4" in screen.text
    assert "🔴 наркотики — 1 · 1 · 0" in screen.text and "🔴 мошенничество — 1 · 0 · 1" in screen.text
    assert "🟠 спам или реклама — 1 · 0 · 0" in screen.text
    assert "Точность по твоим отметкам: 50% (1 из 2)" in screen.text
    assert buttons(screen.keyboard) == {"mod:comments:cm": "✅ Комментарии", "sec": "← Безопасность"}

    unconfigured = await ui.comments_screen(db, dataclasses.replace(config, anthropic_api_key=None))
    assert "Не подключено — нужно: ANTHROPIC_API_KEY" in unconfigured.text


# --- the handlers -----------------------------------------------------------

def group_update(msg=None, chat_type: str = "supergroup"):
    return SimpleNamespace(
        effective_chat=SimpleNamespace(type=chat_type),
        message=msg,
        effective_user=SimpleNamespace(id=5),
        callback_query=None,
    )


async def test_group_traffic_never_reaches_the_owner_handlers(group_bot, config, db, verdicts, make_context):
    context = make_context()
    verdicts.queue.append(dangerous())
    with pytest.raises(ApplicationHandlerStop):
        await handlers.on_group_update(group_update(message("x")), context)
    await asyncio.gather(*context.application.tasks)
    assert len(group_bot.messages) == 1 and group_bot.messages[0].startswith("🔴 Комментарии")

    with pytest.raises(ApplicationHandlerStop):                                # a channel post: stopped, not reviewed
        await handlers.on_group_update(group_update(None, "channel"), context)
    with pytest.raises(ApplicationHandlerStop):                                # a group without a message (a member joined)
        await handlers.on_group_update(group_update(None), context)
    assert len(context.application.tasks) == 1

    # A private chat passes through to the owner-only handlers untouched.
    assert await handlers.on_group_update(SimpleNamespace(effective_chat=SimpleNamespace(type="private")), context) is None


async def test_card_buttons_edit_the_card_in_place(group_bot, config, db, verdicts, make_context, make_update):
    rid = await flagged(group_bot, config, db, verdicts)
    update = make_update(callback=f"cm:ban:{rid}")
    await handlers.on_callback(update, make_context())
    assert group_bot.banned == [(GROUP, 5)]
    assert update.callback_query.answers[0]["text"] == "Удалено, автор забанен"
    (edited,) = update.callback_query.edits
    assert edited.startswith("🔴 Комментарии: наркотики") and "🔨 Удалено, автор забанен" in edited
    assert buttons(update.callback_query.markups[0]) == {f"cm:unban:{rid}": "↩️ Разбанить"}

    stale = make_update(callback="cm:del:777")
    await handlers.on_callback(stale, make_context())
    assert stale.callback_query.answers[0]["text"] == "Эта карточка устарела" and stale.callback_query.edits == []

    screen = make_update(callback="cm")
    await handlers.on_callback(screen, make_context())
    assert screen.callback_query.edits[0].startswith("<b>💬 Комментарии канала</b>")


async def test_comments_command_and_security_button(make_update, make_context):
    update = make_update(text="/comments")
    await handlers.cmd_comments(update, make_context())
    assert update.message.replies[0].startswith("<b>💬 Комментарии канала</b>")
    security = make_update(callback="sec")
    await handlers.on_callback(security, make_context())
    assert buttons(security.callback_query.markups[0])["cm"] == "💬 Комментарии канала"


# --- an edited comment, a card Telegram did not take ------------------------

async def test_a_comment_edited_into_a_drug_shop_is_reviewed_again(group_bot, config, db, verdicts):
    verdicts.queue += [Verdict("ok", 97, "обычный комментарий"), dangerous()]
    watch = comments.Watch()
    assert await comments.review(group_bot, config, db, watch, message("Спасибо за пост")) is None
    # The same message, edited an hour later.
    assert await comments.review(group_bot, config, db, watch, message("Есть мефф, пиши в лс"), edited=True) == 1
    (text,) = group_bot.messages
    assert text.startswith("🔴 Комментарии: наркотики") and "✏️ отредактирован после публикации" in text
    stored = await db.get_review(1)
    assert stored["category"] == "drugs" and stored["text"] == "Есть мефф, пиши в лс" and stored["edited_at"]
    assert (await db.review_stats())["checked"] == 1                     # one message, one row


async def test_an_edit_of_a_deleted_comment_is_not_reviewed_and_a_fine_edit_keeps_the_card(
    group_bot, config, db, verdicts,
):
    verdicts.queue += [dangerous(), Verdict("ok", 95, "уже нормально")]
    watch = comments.Watch()
    await comments.review(group_bot, config, db, watch, message("мефф"))
    # Edited into something harmless: the card about what was posted stays as it was.
    assert await comments.review(group_bot, config, db, watch, message("привет"), edited=True) is None
    assert (await db.get_review(1))["category"] == "drugs" and len(group_bot.messages) == 1
    await db.update_review(1, action="deleted", label="confirmed")
    assert await comments.review(group_bot, config, db, watch, message("мефф снова"), edited=True) is None
    assert len(verdicts.samples) == 2                                    # the last edit was not sent to the model


async def test_the_same_edit_delivered_again_is_not_a_second_card(group_bot, config, db, verdicts):
    verdicts.queue += [Verdict("ok", 97, "обычный комментарий"), dangerous(), dangerous()]
    watch = comments.Watch()
    at = datetime(2026, 11, 24, 10, 0, tzinfo=UTC)
    await comments.review(group_bot, config, db, watch, message("Спасибо за пост"))
    edit = message("Есть мефф, пиши в лс", edit_date=at)
    assert await comments.review(group_bot, config, db, watch, edit, edited=True) == 1
    # The bot restarted before it confirmed the update: Telegram sends the same edit again.
    assert await comments.review(group_bot, config, db, watch, edit, edited=True) is None
    assert len(group_bot.messages) == 1 and len(verdicts.samples) == 2       # one card, one call to the model
    assert (await db.get_review(1))["edited_at"] == "2026-11-24 10:00:00"
    # A later edit is a new look.
    later = message("Есть мефф, пиши в лс, недорого", edit_date=at + timedelta(minutes=5))
    assert await comments.review(group_bot, config, db, watch, later, edited=True) == 1
    assert len(group_bot.messages) == 2 and (await db.get_review(1))["edited_at"] == "2026-11-24 10:05:00"


async def test_an_edited_first_comment_is_still_the_authors_first(group_bot, config, db, verdicts):
    verdicts.queue += [Verdict("ok", 97, "обычный комментарий"), dangerous(), dangerous()]
    watch = comments.Watch()
    await comments.review(group_bot, config, db, watch, message("Спасибо за пост"))
    at = datetime(2026, 11, 24, 10, 0, tzinfo=UTC)
    await comments.review(group_bot, config, db, watch, message("мефф", edit_date=at), edited=True)
    assert verdicts.samples[1].first_message is True                        # the model is told so…
    assert "первое сообщение в группе" in group_bot.messages[0]            # …and so is the owner
    # The author's second comment is not a first, edited or not.
    await comments.review(group_bot, config, db, watch, message("мефф", message_id=8, edit_date=at), edited=True)
    assert verdicts.samples[2].first_message is False
    assert "первое сообщение в группе" not in group_bot.messages[1]


async def test_a_card_telegram_did_not_take_waits_in_the_queue(group_bot, config, db, verdicts):
    from telegram.error import RetryAfter

    from bot import notifier

    verdicts.queue.append(dangerous())

    async def flood(*args, **kwargs):
        raise RetryAfter(30)

    sent = group_bot.send_message
    group_bot.send_message = flood                                       # a spam wave hit the flood limit
    assert await comments.review(group_bot, config, db, comments.Watch(), message("мефф")) == 1
    assert group_bot.messages == []
    group_bot.send_message = sent
    assert await notifier.flush_queue(group_bot, config, db) == 1        # the next minute
    (text,) = group_bot.messages
    assert text.startswith("🕒 ") and "🔴 Комментарии: наркотики" in text
    assert buttons(group_bot.markups[0]) == {"cm:del:1": "🗑 Удалить", "cm:ban:1": "🔨 Удалить и забанить", "cm:ok:1": "✅ Всё в порядке"}


async def test_edits_reach_the_review_and_never_the_owner_handlers(group_bot, config, db, verdicts, make_context):
    from telegram import Update

    assert Update.EDITED_MESSAGE in handlers.ALLOWED_UPDATES
    context = make_context()
    verdicts.queue.append(dangerous())
    edit = SimpleNamespace(effective_chat=SimpleNamespace(type="supergroup"), message=None,
                           edited_message=message("мефф"))
    with pytest.raises(ApplicationHandlerStop):
        await handlers.on_group_update(edit, context)
    await asyncio.gather(*context.application.tasks)
    assert "✏️ отредактирован после публикации" in group_bot.messages[0]
    # The owner fixing a typo in an old /settime: not a new command.
    private_edit = SimpleNamespace(effective_chat=SimpleNamespace(type="private"), message=None,
                                   edited_message=SimpleNamespace(text="/settime 09:00"))
    with pytest.raises(ApplicationHandlerStop):
        await handlers.on_group_update(private_edit, context)

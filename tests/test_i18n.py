"""BOT_LANG=en: every screen, report and alert renders without a Cyrillic
letter. Russian is the source and the lookup key (bot/i18n.py), so a key that
drifted from its English entry falls back to Russian and shows up here."""

import dataclasses
import re
from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from conftest import COOKIE, FakeBot

from bot import handlers, humanize, i18n, monitors, notifier, reporter, scheduler, tofs_status, ui, watchdog
from bot.config import Config
from bot.db import utcnow
from bot.i18n import plural, t
from bot.monitors import channel, collection, comments, followers, hygiene, mail, profile
from bot.platforms import BY_ID, PLATFORMS
from bot.scheduler import CollectOutcome, _send_backup

CYRILLIC = re.compile("[А-Яа-яЁё]")


@pytest.fixture(autouse=True)
def english():
    i18n.set_language("en")
    yield
    i18n.set_language("ru")


@pytest.fixture
def config(tmp_path) -> Config:
    return dataclasses.replace(Config.from_env(), db_path=str(tmp_path / "followers.db"), instagram_username="semyon")


def english_only(text: str | None) -> None:
    assert text is not None
    hit = CYRILLIC.search(text)
    assert hit is None, f"Russian leaked at …{text[max(0, hit.start() - 40):hit.start() + 60]}…"


def screen_english(screen: ui.Screen) -> None:
    english_only(screen.text)
    if screen.keyboard is not None:
        for row in screen.keyboard.inline_keyboard:
            for button in row:
                english_only(button.text)


def test_layer():
    assert t("Сохранено") == "Saved"
    assert t("нет такого ключа — остаётся русским") == "нет такого ключа — остаётся русским"
    assert plural(1, "подписчик", "подписчика", "подписчиков") == "follower"
    assert plural(5, "подписчик", "подписчика", "подписчиков") == "followers"
    i18n.set_language("ru")
    assert t("Сохранено") == "Сохранено"
    assert plural(22, "подписчик", "подписчика", "подписчиков") == "подписчика"
    with pytest.raises(ValueError):
        i18n.set_language("de")


def test_numbers_use_the_english_decimal_point():
    assert reporter._pct(6.66) == "+6.7%"
    i18n.set_language("ru")
    assert reporter._pct(6.66) == "+6,7%"


def test_config_lang(monkeypatch):
    monkeypatch.setenv("BOT_LANG", "EN")
    assert Config.from_env().lang == "en"
    monkeypatch.setenv("BOT_LANG", "fr")
    with pytest.raises(RuntimeError):
        Config.from_env()


def test_keyboard_and_its_notes():
    english_only(ui.welcome(claimed=True))
    english_only(t(handlers.NOT_UNDERSTOOD))
    english_only(t(handlers.STALE_BUTTON))
    for row in ui.persistent_keyboard().keyboard:
        for button in row:
            english_only(button.text)


class _Channel(type(BY_ID["telegram"])):
    """The Telegram connector with the profile it returns queued (None — a failed fetch)."""

    def __init__(self, values):
        self.values = values

    def enabled(self, config):
        return True

    async def fetch_profile(self, ctx):
        return self.values.pop(0)


async def _log_while_russian(db, config, monkeypatch) -> None:
    """Fill the security log the way a chat that was Russian until today has it:
    rows today's monitors write, and a row 1.5.0 stored as finished Russian
    text — the one 🛡 Security showed in Russian on an English chat."""
    i18n.set_language("ru")
    try:
        before = {"title": "Channel", "description": "about", "admin_access": "нет"}
        channel = _Channel([before, {**before, "description": "", "admin_access": "есть"}])
        monkeypatch.setattr(profile.platforms, "enabled", lambda config: [channel])
        bot = FakeBot()
        for _ in range(2):
            await profile.check(bot, config, db, None)

        async def fetch(session, config):
            return [
                {"id": "1", "from": "no-reply@accounts.google.com", "subject": "", "text": "New sign-in on Windows"},
                {"id": "2", "from": "security@mail.instagram.com", "subject": "123456 is your Instagram code"},
            ], ""

        async def ack(session, config, ids):
            pass

        monkeypatch.setattr(mail, "_fetch", fetch)
        monkeypatch.setattr(mail, "_ack", ack)
        assert await mail.check(bot, config, db, None) == 2
        await db.add_event("profile:telegram:old", "Telegram", "profile",
                           "🟠 Telegram: доступ бота к списку админов — «нет» → «есть»")
    finally:
        i18n.set_language("en")
    assert len(await db.recent_events()) == 5        # all of them on the screen


async def test_every_screen(config, db, insert, monkeypatch):
    insert("telegram", 1000, 1)
    insert("telegram", 1020)
    insert("youtube", 126)
    insert("linkedin", 4981, 10, source="manual")
    await db.set_setting("linkedin_li_at", COOKIE)
    await db.set_setting("linkedin_li_at_set_at", (utcnow() - timedelta(days=340)).isoformat())
    await db.set_setting("profile_fail_youtube", "3")
    await hygiene.set_answer(db, "telegram", "2fa", "off")
    await _log_while_russian(db, config, monkeypatch)

    screens = [
        await ui.home(db, config),
        ui.loading(),
        await ui.dynamics(db),
        await ui.table(db, config),
        await ui.table(db, config, "telegram", 30),
        await ui.security(db, config),
        await ui.settings(db, config),
        await ui.report_days(db, config),
        await ui.report_time(db, config),
        await ui.timezone(db, config),
        await ui.monitors_screen(db, config),
        await ui.linkedin(db, config),
        await ui.instagram(db, config),
        await ui.linkedin_prompt(db),
        ui.linkedin_retry(),
        ui.linkedin_confirm(4500, 9000),
        ui.about_screen(),
        ui.icons_screen(),
        ui.mute_picker(),
        await ui.watchdog_screen(db, config),
        ui.watchdog_off_confirm(),
        ui.input_prompt("watchdog"),
        ui.input_retry(t("✅ Сторож на связи")),
        await ui.when_to_write(db, config),
        await ui.comments_screen(db, config),
        await ui.comments_screen(db, dataclasses.replace(config, anthropic_api_key="k")),
        await ui.channel_screen(db, config),   # empty
        await ui.connections(db, config),
        await ui.connections(db, dataclasses.replace(config, telegram_channel_id=None, youtube_api_key=None)),
    ]
    # The channel screen with events, sources and a reacted post; the report line it feeds.
    now = utcnow()
    await db.add_channel_event(-100, "join", 1, "Ivan", "From IG", now)   # a link's name is the owner's text
    await db.add_channel_event(-100, "join", 2, "Anna", channel.VIA_REQUEST, now)
    await db.add_channel_event(-100, "leave", 3, "Pete", "", now)
    await db.add_channel_post(-100, 10, "photo", now)
    await db.set_post_reactions(-100, 10, 4, '{"👍": 3, "❤": 1}', now)
    screens.append(await ui.channel_screen(db, config))
    english_only(await channel.report_line(db, config))
    for via in (*channel.VIA_LABELS, "From IG"):
        english_only(channel.via_label(via))
    await monitors.toggle(db, channel.MONITOR_ID)
    screens.append(await ui.channel_screen(db, config))
    await monitors.toggle(db, channel.MONITOR_ID)
    for platform in PLATFORMS:
        screens.append(await ui.checklist(db, platform))
        for key in ui.question_keys(platform):
            screens.append(await ui.question(db, platform, key))
    for screen in screens:
        screen_english(screen)
        screen_english(screen.noted(t("Сохранено")))  # the caller translates a note before noted()

    tz = ZoneInfo("Europe/Moscow")
    english_only(ui.next_report("sat", 9, 0, tz))
    english_only(ui.dow_pretty("mon-fri"))
    english_only(ui.dow_pretty("*"))
    english_only(ui.tz_name(tz))
    # The Instagram token and the manual LinkedIn number change the home screen and the settings.
    await db.set_setting("instagram_token", "x" * 60)
    await db.set_setting("instagram_token_set_at", utcnow().isoformat())
    await db.set_setting("cookie_expired_alerted", "1")
    screen_english(await ui.home(db, config))
    screen_english(await ui.linkedin(db, config))
    screen_english(await ui.instagram(db, config))
    # Quiet hours and a mute: the when screen, the home chip, the mute note.
    await notifier.set_quiet_hours(db, "0-23")
    await notifier.set_mute(db, timedelta(hours=1))
    screen_english(await ui.when_to_write(db, config))
    screen_english(await ui.settings(db, config))
    screen_english(await ui.home(db, config))
    english_only(await notifier.silence_status(db, config))
    english_only(ui.mute_note("08:00"))
    english_only(notifier.what_rings_through())
    await notifier.set_mute(db, None)
    english_only(await notifier.silence_status(db, config))
    # ⏱ Сторож: set in the chat, then a ping that did not land; the offer and every reason.
    await watchdog.save(db, "https://hc-ping.com/1b2c3d4e-5f60-7182")
    screen_english(await ui.watchdog_screen(db, config))
    for code in ("not_found", "rejected:403", "timeout", "connect", "error", "tofs"):
        english_only(watchdog.reason(code))
        await watchdog.record(db, code)
        screen_english(await ui.connections(db, config))
    english_only(t(scheduler.WATCHDOG_OFFER))


async def test_reports_and_tables(config, db, insert):
    for day in range(40, -1, -1):
        insert("telegram", 990 + day * 2, day)
        insert("youtube", 100 + day // 3, day)
        insert("instagram", 150 + day, day)
    insert("linkedin", 4981, 9, source="manual")
    errors = {
        "youtube": True,
        "linkedin_cookie_expired": True,
        "instagram_token_missing": True,
    }
    text, _ = await reporter.build_report(db, errors=errors, platforms=config.enabled_platforms)
    english_only(text)
    text, _ = await reporter.build_report(db, errors={"linkedin_cookie_aging": 340, "instagram_token_expired": True})
    english_only(text)
    english_only((await reporter.build_report(db, platforms=["tiktok"]))[0])
    english_only(await reporter.build_week_report(db))
    english_only(await reporter.build_month_report(db))
    english_only(await reporter.build_history_all(db, 7))
    english_only(await reporter.build_history_all(db, 0))
    english_only(await reporter.build_history_table(db, "telegram", 7))
    english_only(await reporter.build_history_table(db, "linkedin", 1))
    english_only(await hygiene.report_line(db, config))
    for errs in ({}, errors, {"instagram_token_expired": True}, {"linkedin_cookie_aging": 340}):
        payload = await tofs_status.build(db, config, errs)
        english_only(payload["title"])
        for item in payload["items"]:
            english_only(item["text"])
    await db.set_setting("profile_fail_telegram", "3")
    for item in (await tofs_status.build(db, config, {}))["items"]:
        english_only(item["text"])


async def test_alerts(config, db):
    outcome = CollectOutcome(
        report="", has_change=True,
        drops={"telegram": (1000, 900)}, spikes={"youtube": (100, 600)}, milestones=[("instagram", 1000)],
        errors={"linkedin_cookie_expired": True, "youtube": True},
    )
    for line in followers.alert_lines(outcome):
        english_only(line)
    await db.set_setting("fail_streak_youtube", "1")
    for line in await collection.alert_lines(db, outcome):
        english_only(line)
    missing = CollectOutcome(report="", has_change=False, errors={"instagram_token_missing": True})
    for line in await collection.alert_lines(db, missing):
        english_only(line)

    old = {
        "title": "Channel", "username": "chan", "description": "about", "avatar": "a", "videos": "40", "media": "56",
        "name": "Sam", "biography": "bio", "handle": "@chan",
        "admins": '[{"id": "1", "name": "Owner", "status": "creator"}, {"id": "2", "name": "Mod", "status": "administrator"}]',
        "admin_access": "нет",
    }
    new = {
        **old, "title": "Giveaway", "username": "scam", "description": "win https://evil.example", "avatar": "b",
        "videos": "10", "media": "10", "name": "X", "biography": "https://evil.example", "handle": "@scam",
        "admins": '[{"id": "3", "name": "Thief", "status": "creator"}]', "admin_access": "есть",
    }
    for platform in PLATFORMS:
        for line in profile.diff(platform, old, new):
            english_only(line)
    for fails, reachable in ((2, False), (3, True)):
        for line in profile._reachability(BY_ID["telegram"], fails, reachable)[0]:
            english_only(line)
    english_only(humanize.render(profile._quote("")))
    for platform in PLATFORMS:
        changes = profile.diff(platform, old, new)
        if changes:
            english_only(profile.change_alert(changes))
    now = utcnow()
    english_only(profile._reachability(
        BY_ID["telegram"], profile.UNREACHABLE_AFTER, True, now - timedelta(hours=26), now - timedelta(hours=20), now,
        ZoneInfo("Europe/Moscow"),
    )[0][0])
    for key in humanize.EXPLANATIONS:
        english_only(humanize.alert("x", key, "y"))
    for minutes in (1, 59, 61, 120, 60 * 24 * 3 + 61):
        english_only(humanize.fmt_duration(minutes))
    # Recoveries with how long it lasted; the run's and a platform's streak ending.
    await db.set_setting("run_fail_streak", "2")
    await db.set_setting("run_fail_since", (now - timedelta(days=2)).isoformat())
    await db.set_setting("fail_streak_telegram", "3")
    await db.set_setting("fail_since_telegram", (now - timedelta(days=3)).isoformat())
    back = CollectOutcome(report="", has_change=False, collected={"telegram": (1000, "api")})
    for line in await collection.alert_lines(db, back, ZoneInfo("Europe/Moscow")):
        english_only(line)
    await db.set_setting("run_fail_last_date", "")
    await db.set_setting("run_fail_streak", "1")
    for line in await collection.run_failed(db):
        english_only(line)
    # The mail worker silent and back; the comment check down, back and over its limit.
    bot = FakeBot()
    for _ in range(mail.UNREACHABLE_AFTER):
        await mail._track_reachability(bot, config, db, "HTTP 500")
    await mail._track_reachability(bot, config, db, None)
    for _ in range(comments.API_FAIL_AFTER):
        await comments._api_failed(bot, config, db, ValueError("x"))
    await comments._api_recovered(bot, config, db)
    limited = dataclasses.replace(config, comments_daily_limit=1)
    await db.add_review(-1001, 1, 5, "", "", "", "", "ok", 0, "")
    assert await comments.over_daily_limit(bot, limited, db)
    assert len(bot.messages) == 5
    for text in bot.messages:
        english_only(text)

    today = utcnow().date()
    for platform in PLATFORMS:
        for line in hygiene.recommendations(platform, {}, today):
            english_only(line)
        for item in hygiene.items(platform):
            english_only(t(item.label))
            english_only(t(item.question))
            english_only(t(item.advice))
            for choice in item.choices:
                english_only(t(choice.button))
    english_only(await hygiene.nudge(db, config))

    mails = [
        ("security@mail.instagram.com", "123456 is your Instagram code", ""),
        ("no-reply@accounts.google.com", "Security alert", "New sign-in on Windows"),
        ("security-noreply@linkedin.com", "Your password was changed", "You changed your password"),
        ("forwarding-noreply@google.com", "Gmail Forwarding Confirmation", "Confirmation code: 123456789"),
        ("someone@example.com", "Hello", "nothing alarming"),
    ]
    for i, (sender, subject, text) in enumerate(mails):
        title, kind, body, link = mail.describe(mail.Mail(id=str(i), sender=sender, subject=subject, text=text))
        english_only(title)
        english_only(body)
    for kind in mail.KINDS:
        english_only(t(kind.title))
        english_only(t(kind.advice))


async def test_digest(config, db, make_update, make_context, bot):
    await notifier.set_mute(db, timedelta(hours=1))
    await notifier.send(bot, config, db, "x")
    await notifier.send(bot, config, db, humanize.alert("🟠 y", "follower_drop", "z"), monitor="followers")
    await notifier.set_mute(db, None)
    assert await notifier.flush_queue(bot, config, db) == 2
    english_only(bot.messages[0])                                  # the headlines and the «ℹ️ N» hint
    for row in bot.markups[0].inline_keyboard:
        for button in row:
            english_only(button.text)
    # «ℹ️ N»: the item whole, with its own row; a button whose text is gone says so.
    data = next(b.callback_data for row in bot.markups[0].inline_keyboard for b in row if b.text == "ℹ️ 1")
    for callback in (data, "dg:999"):
        update = make_update(callback=callback)
        await handlers.on_callback(update, make_context())
        for answer in update.callback_query.answers:
            english_only(answer["text"] or "")
    english_only(bot.messages[-1])
    for row in bot.markups[-1].inline_keyboard:
        for button in row:
            english_only(button.text)


async def test_backup_caption(config, db):
    bot = FakeBot()
    await db.upsert("telegram", 1000)
    await _send_backup(bot, config, db)
    english_only(bot.documents[0]["caption"])


async def test_comment_cards(db):
    with_key = dataclasses.replace(Config.from_env(), anthropic_api_key="k")
    await db.add_review(-1001, 7, 5, "Ivan (@ivan)", "buy here", "photo", "https://t.me/c/1/7", "drugs", 92, "an offer with a contact")
    await db.update_review(1, action="banned", label="confirmed")
    screen = await ui.comments_screen(db, with_key)
    screen_english(screen)
    for state in ({"action": "", "label": ""}, {"action": "deleted", "label": "confirmed"},
                  {"action": "banned", "label": "confirmed"}, {"action": "", "label": "false_positive"}):
        review = {**await db.get_review(1), **state}
        text, markup = comments.card(review, "Channel", first_message=True)
        english_only(text)
        if markup is not None:
            for row in markup.inline_keyboard:
                for button in row:
                    english_only(button.text)
    text, _ = comments.card({**await db.get_review(1), "category": "refused", "confidence": 0, "action": "", "label": ""})
    english_only(text)

import dataclasses
import json
from datetime import timedelta

import pytest

from bot import monitors
from bot.db import utcnow
from bot.monitors import hygiene, profile
from bot.platforms import BY_ID
from bot.platforms.base import Platform

TELEGRAM = BY_ID["telegram"]
YOUTUBE = BY_ID["youtube"]


def _admins(*members):
    return json.dumps([{"id": i, "name": n, "status": s} for i, n, s in members])


CHANNEL = {
    "title": "Мой канал",
    "username": "my_channel",
    "description": "Про код. Связь: https://morgunov.tech",
    "photo": "p1",
    "admins": _admins((1, "Owner (@owner)", "creator"), (99, "Bot", "administrator")),
}


# --- module switches ---------------------------------------------------------

async def test_monitors_are_on_by_default_and_toggle(config, db):
    assert await monitors.is_on(db, config, "followers")
    assert await monitors.toggle(db, "followers") is False
    assert not await monitors.is_on(db, config, "followers")
    assert await monitors.toggle(db, "followers") is True


async def test_monitor_needing_configuration_is_off_without_it(config, db):
    assert not await monitors.is_on(db, config, "mail")              # conftest sets no mail worker
    configured = dataclasses.replace(config, security_mail_url="https://w", security_mail_token="t")
    assert await monitors.is_on(db, configured, "mail")
    no_profiles = dataclasses.replace(config, telegram_channel_id=None, youtube_api_key=None)
    assert not await monitors.is_on(db, no_profiles, "profile")      # LinkedIn has no watched fields


# --- profile diff ------------------------------------------------------------

def test_unchanged_profile_is_silent():
    assert profile.diff(TELEGRAM, CHANNEL, dict(CHANNEL)) == []


def test_text_change_and_a_new_link_is_critical():
    renamed = {**CHANNEL, "title": "Tesla Live", "description": "Розыгрыш BTC: https://scam.example/x"}
    lines = profile.diff(TELEGRAM, CHANNEL, renamed)
    assert lines[0] == "🟠 Telegram: название канала — «Мой канал» → «Tesla Live»"
    assert lines[1].startswith("🚨 Telegram: описание канала") and "hxxps://scam[.]example/x" in lines[1]
    assert "https://" not in "".join(lines)                # quoted links are not clickable


def test_link_list_is_capped():
    links = " ".join(f"https://spam{i}.example" for i in range(40))
    (line,) = profile.diff(TELEGRAM, CHANNEL, {**CHANNEL, "description": links})
    listed = line.split("новые ссылки:")[1]
    assert listed.count("hxxps://") == profile.MAX_LINKS and listed.endswith("и ещё 35")


def test_defang():
    assert monitors.defang("см. evil.example/x и https://a.b/c, т.е. v1.2") == (
        "см. evil[.]example/x и hxxps://a[.]b/c, т.е. v1.2"
    )


def test_long_text_is_cut():
    long_text = {**CHANNEL, "description": "слово " * 100}
    (line,) = profile.diff(TELEGRAM, CHANNEL, long_text)
    assert line.endswith("…»") and len(line) < 2 * profile.SNIPPET_LEN + 80


def test_avatar_and_admin_changes():
    changed = {
        **CHANNEL,
        "photo": "p2",
        "admins": _admins((2, "Stranger (@x)", "creator"), (99, "Bot", "administrator")),
    }
    lines = profile.diff(TELEGRAM, CHANNEL, changed)
    assert "🟠 Telegram: новая аватарка канала" in lines
    assert "🚨 Telegram: новый админ — Stranger (@x)" in lines
    assert "🟠 Telegram: админ удалён — Owner (@owner)" in lines
    assert "🚨 Telegram: сменился владелец — Owner (@owner) → Stranger (@x)" in lines


def test_admin_rename_is_not_a_change():
    renamed = {**CHANNEL, "admins": _admins((1, "New Name", "creator"), (99, "Bot", "administrator"))}
    assert profile.diff(TELEGRAM, CHANNEL, renamed) == []


@pytest.mark.parametrize(("was", "now", "alerted"), [(40, 0, True), (40, 37, False), (40, 36, True), (5, 3, False)])
def test_video_drop(was, now, alerted):
    old = {"videos": str(was)}
    lines = profile.diff(YOUTUBE, old, {"videos": str(now)})
    assert bool(lines) is alerted


def test_field_missing_on_one_side_is_ignored():
    assert profile.diff(TELEGRAM, {"title": "a"}, {"title": "a", "photo": "p"}) == []


# --- profile check -----------------------------------------------------------

class FakeTelegram(Platform):
    id = "telegram"
    label = "Telegram"
    profile_fields = BY_ID["telegram"].profile_fields

    def __init__(self, values):
        self.values = values

    def enabled(self, config):
        return True

    async def fetch_profile(self, ctx):
        return self.values.pop(0)


@pytest.fixture
def watch(monkeypatch):
    """Profile fetches return the queued values in order (None = failed fetch)."""
    values: list = []
    monkeypatch.setattr(profile.platforms, "enabled", lambda config: [FakeTelegram(values)])
    return values


async def test_first_look_is_baseline_then_changes_are_alerted_once(bot, config, db, watch):
    watch += [CHANNEL, {**CHANNEL, "title": "Hacked"}, {**CHANNEL, "title": "Hacked"}]
    assert await profile.check(bot, config, db, None) == 0
    assert await profile.check(bot, config, db, None) == 1
    line = "🟠 Telegram: название канала — «Мой канал» → «Hacked»"
    assert bot.messages[0].startswith(f"🛡 Профиль\n\n{line}") and profile.ADVICE in bot.messages[0]
    assert await profile.check(bot, config, db, None) == 0
    (event,) = await db.recent_events()
    assert event["kind"] == "profile" and event["detail"] == line


async def test_failed_send_keeps_the_old_baseline_and_retries(bot, config, db, watch):
    watch += [CHANNEL, {**CHANNEL, "title": "Hacked"}, {**CHANNEL, "title": "Hacked"}]
    await profile.check(bot, config, db, None)
    send = bot.send_message

    async def broken(*args, **kwargs):
        raise RuntimeError("Telegram is down")

    bot.send_message = broken
    assert await profile.check(bot, config, db, None) == 0
    assert await db.recent_events() == []
    bot.send_message = send
    assert await profile.check(bot, config, db, None) == 1  # the same change, alerted now
    assert "«Hacked»" in bot.messages[0]


async def test_field_missing_from_a_fetch_keeps_its_baseline(bot, config, db, watch):
    without_title = {k: v for k, v in CHANNEL.items() if k != "title"}
    watch += [CHANNEL, without_title, {**CHANNEL, "title": "Hacked"}]
    await profile.check(bot, config, db, None)
    assert await profile.check(bot, config, db, None) == 0
    assert await profile.check(bot, config, db, None) == 1      # still compared with «Мой канал»


async def test_unreachable_profile_alerted_once_and_recovery(bot, config, db, watch):
    watch += [CHANNEL] + [None] * (profile.UNREACHABLE_AFTER + 1) + [CHANNEL]
    await profile.check(bot, config, db, None)
    sent = [await profile.check(bot, config, db, None) for _ in range(profile.UNREACHABLE_AFTER + 1)]
    assert sent == [0] * (profile.UNREACHABLE_AFTER - 1) + [1, 0]
    assert "🔴 Telegram: профиль не читается" in bot.messages[0]
    assert await profile.check(bot, config, db, None) == 1
    assert "✅ Telegram: профиль снова доступен" in bot.messages[1]


# --- hygiene -----------------------------------------------------------------

def test_every_checklist_adds_up_to_ten():
    for checklist in hygiene.CHECKLISTS.values():
        assert sum(item.best for item in checklist) + hygiene.PASSWORD_POINTS == hygiene.MAX_SCORE


def test_score_and_recommendations():
    today = utcnow().date()
    best = {"2fa": "app", "backup": "yes", "recovery": "yes", "unique": "yes", "pwd": today.isoformat()}
    assert hygiene.score(YOUTUBE, best, today) == 10
    assert hygiene.recommendations(YOUTUBE, best, today) == []

    weak = {**best, "2fa": "sms", "pwd": (today - timedelta(days=400)).isoformat()}
    assert hygiene.score(YOUTUBE, weak, today) == 7
    recs = hygiene.recommendations(YOUTUBE, weak, today)
    assert "SMS" in recs[0] and "400 дн." in recs[1]          # the 2FA advice outweighs the password age

    assert hygiene.score(YOUTUBE, {}, today) == 0
    assert hygiene.recommendations(YOUTUBE, {}, today) == ["YouTube: отметь пункты чек-листа — это пара минут"]


async def test_overall_averages_enabled_platforms(config, db):
    today = utcnow().date().isoformat()
    for key, value in {"2fa": "on", "backup": "yes", "sessions": "yes", "unique": "yes", "pwd": today}.items():
        await hygiene.set_answer(db, "telegram", key, value)
    total, recs = await hygiene.overall(db, config)
    assert total == round(10 / 3)                             # YouTube and LinkedIn are still empty
    assert len(recs) == 2


async def test_overall_puts_the_most_valuable_advice_first(config, db):
    today = utcnow().date().isoformat()
    telegram = {"2fa": "on", "backup": "yes", "sessions": "yes", "unique": "no", "pwd": today}
    youtube = {"2fa": "app", "backup": "yes", "recovery": "yes", "unique": "yes", "pwd": today}
    for platform, marks in (("telegram", telegram), ("youtube", youtube), ("linkedin", {"2fa": "off"})):
        for key, value in marks.items():
            await hygiene.set_answer(db, platform, key, value)
    _, recs = await hygiene.overall(db, config)
    assert recs[0].startswith("LinkedIn: включи 2FA")               # 4 points beat Telegram, listed earlier
    assert recs[-1].startswith("LinkedIn: отметь, когда пароль менялся")


async def test_nudge_first_invites_then_waits_a_month(config, db, monkeypatch):
    first = await hygiene.nudge(db, config)
    assert first and "Пройди короткий чек-лист" in first and first.endswith("/security")
    assert await hygiene.nudge(db, config) is None

    await hygiene.set_answer(db, "telegram", "2fa", "off")
    month_later = utcnow() + timedelta(days=hygiene.NUDGE_EVERY_DAYS)
    monkeypatch.setattr(hygiene, "utcnow", lambda: month_later)
    second = await hygiene.nudge(db, config)
    assert second.count("•") == hygiene.NUDGE_TOP and "облачный пароль" in second


async def test_mail_password_change_is_not_a_review(db):
    await hygiene.mark_password_changed(db, "youtube", utcnow().date())
    assert await db.get_setting("hygiene_youtube_pwd") == utcnow().date().isoformat()
    assert await db.get_setting("hygiene_reviewed_at") is None

"""The security log reads in the chat language of the day it is shown
(bot/security_log.py): new rows keep the line before translation, old rows of
finished Russian text are recognised and rendered the same way."""

import re

import pytest

from bot import humanize, i18n, security_log, ui
from bot.monitors import mail, profile
from bot.platforms import BY_ID

CYRILLIC = re.compile("[А-Яа-яЁё]")

# What 🛡 Безопасность showed with BOT_LANG=en on 2026-11-24: a row the profile
# monitor stored as Russian text the day before, while the chat was Russian.
PRODUCTION = "🟠 Telegram: доступ бота к списку админов — «нет» → «есть»"

# The first lines older versions stored, each → what it reads as today in Russian.
# The quoted values are Latin here: someone's text is shown as it was written.
LEGACY = {
    PRODUCTION: PRODUCTION,
    "🟠 Telegram: название канала — «My channel» → «Hacked»": "🟠 Telegram: название канала — «My channel» → «Hacked»",
    "🟠 Instagram: описание профиля — «bio» → «(пусто)»": "🟠 Instagram: описание профиля — «bio» → «(пусто)»",
    "🔴 Telegram: похоже на взлом — описание канала: «About code» → «win hxxps://evil[.]example»":
        "🔴 Telegram: похоже на взлом — описание канала: «About code» → «win hxxps://evil[.]example»",
    "🚨 YouTube: описание канала — «(пусто)» → «free hxxps://scam[.]example»":
        "🔴 YouTube: похоже на взлом — описание канала: «(пусто)» → «free hxxps://scam[.]example»",
    "🟠 YouTube: новая аватарка канала": "🟠 YouTube: новая аватарка канала",
    "🔴 Telegram: похоже на взлом — новый админ Thief (@thief)": "🔴 Telegram: похоже на взлом — новый админ Thief (@thief)",
    "🚨 Telegram: новый админ — Thief (@thief)": "🔴 Telegram: похоже на взлом — новый админ Thief (@thief)",
    "🟠 Telegram: админ удалён — Mod": "🟠 Telegram: админ удалён — Mod",
    "🔴 Telegram: похоже на взлом — сменился владелец: Owner → Thief":
        "🔴 Telegram: похоже на взлом — сменился владелец: Owner → Thief",
    "🚨 Telegram: сменился владелец — Owner → Thief": "🔴 Telegram: похоже на взлом — сменился владелец: Owner → Thief",
    "🔴 YouTube: похоже на взлом — видео на канале: было 40, стало 10 (−30)":
        "🔴 YouTube: похоже на взлом — видео на канале: было 40, стало 10 (−30)",
    "🚨 Instagram: публикаций — было 56, стало 10 (−46)": "🔴 Instagram: похоже на взлом — публикаций: было 56, стало 10 (−46)",
    "🔴 Google: похоже на взлом — новый вход в аккаунт": "🔴 Google: похоже на взлом — новый вход в аккаунт",
    "🚨 LinkedIn: пароль изменён\n«Your password was changed»\nЕсли это не ты — восстанавливай доступ немедленно.":
        "🔴 LinkedIn: похоже на взлом — пароль изменён",
    "🟠 Instagram: пришёл код входа": "🟠 Instagram: пришёл код входа",
    "🟠 evil[.]example: оповещение безопасности": "🟠 evil[.]example: оповещение безопасности",
}


@pytest.fixture
def english():
    i18n.set_language("en")
    yield
    i18n.set_language("ru")


def test_the_production_row_reads_in_english(english):
    assert security_log.line(PRODUCTION) == '🟠 Telegram: bot\'s access to the admin list — "no" → "yes"'


@pytest.mark.parametrize("stored", LEGACY)
def test_an_old_row_reads_as_a_new_one(stored):
    assert security_log.line(stored) == LEGACY[stored]


@pytest.mark.parametrize("stored", LEGACY)
def test_an_old_row_reads_in_english(english, stored):
    shown = security_log.line(stored)
    assert CYRILLIC.search(shown) is None, shown


def test_someone_elses_text_is_never_translated(english):
    # A channel renamed to «нет» stays «нет»: only the bot's own words are keys.
    assert security_log.line("🟠 Telegram: название канала — «нет» → «есть»") == (
        '🟠 Telegram: channel name — "нет" → "есть"'
    )
    assert "Вор" in security_log.line("🚨 Telegram: новый админ — Вор")


def test_a_row_it_does_not_know_is_shown_as_it_is(english):
    assert security_log.line("New login from a new device") == "New login from a new device"
    assert security_log.line("что-то третье\nвторая строка") == "что-то третье"
    assert security_log.line("") == "" and security_log.line(None) == ""
    assert security_log.line("{not json") == "{not json"


def test_new_rows_are_phrases_that_follow_the_language():
    old = {"title": "Канал", "admin_access": "нет", "description": ""}
    new = {"title": "Канал", "admin_access": "есть", "description": "https://evil.example"}
    found = profile.changes(BY_ID["telegram"], old, new)
    stored = [humanize.dump(line) for line, _ in found]
    google = mail.Mail(id="1", sender="no-reply@accounts.google.com", subject="", text="New sign-in on Windows")
    stored.append(humanize.dump(mail.headline(google)))
    russian = [security_log.line(row) for row in stored]
    assert russian == [
        "🔴 Telegram: похоже на взлом — описание канала: «(пусто)» → «hxxps://evil[.]example»",
        PRODUCTION,
        "🔴 Google: похоже на взлом — новый вход в аккаунт",
    ]
    i18n.set_language("en")
    try:
        assert [security_log.line(row) for row in stored] == [
            '🔴 Telegram: looks like a hijack — channel description: "(empty)" → "hxxps://evil[.]example"',
            '🟠 Telegram: bot\'s access to the admin list — "no" → "yes"',
            "🔴 Google: looks like a hijack — new sign-in to the account",
        ]
    finally:
        i18n.set_language("ru")


async def test_the_security_screen_in_english_with_the_production_row(english, config, db):
    await db.add_event("profile:telegram:2026-11-23T09:00:00+00:00:0", "Telegram", "profile", PRODUCTION)
    screen = await ui.security(db, config)
    assert '🟠 Telegram: bot\'s access to the admin list — "no" → "yes"' in screen.text
    assert CYRILLIC.search(screen.text) is None, screen.text

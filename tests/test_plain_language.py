"""The screens a newcomer sees speak plain language: no variable names, no
.env, no developer words. Every screen of a fresh install is drawn in
Russian and in English, twice — with nothing connected, and with every
network connected from the chat (🔌 Подключения → «➕ …») the way a bot
deployed by the Railway button gets them. Labels of someone else's interface
in quotes («Add Check», «Grace Time») are fine: a guide cannot do without them.

The same idea as tests/test_i18n.py: draw everything, fail on the first hit."""

import dataclasses
import re

import pytest

from bot import connections, i18n, ui
from bot.platforms import BY_ID

FORBIDDEN = {
    "a variable name": re.compile(r"\b[A-Z][A-Z0-9]*_[A-Z0-9_]+\b"),
    ".env": re.compile(r"\.env\b"),
    "IANA": re.compile(r"IANA"),
    "DevTools": re.compile(r"DevTools", re.IGNORECASE),
    "user-agent": re.compile(r"user-agent", re.IGNORECASE),
    "heartbeat": re.compile(r"heartbeat", re.IGNORECASE),
    "пинг": re.compile(r"пинг", re.IGNORECASE),
    "ping": re.compile(r"(?<!hc-)\bping\b", re.IGNORECASE),     # hc-ping.com is an address, not a word
    "Python": re.compile(r"Python"),
}

NO_NETWORKS = {"telegram_channel_id": None, "youtube_channel_id": None, "youtube_api_key": None,
               "instagram_username": None, "linkedin_profile_url": None}


def plain(where: str, text: str) -> None:
    for name, pattern in FORBIDDEN.items():
        hit = pattern.search(text)
        assert hit is None, f"{where}: {name} at …{text[max(0, hit.start() - 50):hit.end() + 50]}…"


def plain_screen(where: str, screen: ui.Screen) -> None:
    plain(where, screen.text)
    for row in (screen.keyboard.inline_keyboard if screen.keyboard else ()):
        for button in row:
            plain(f"{where} · button", button.text)


async def _screens(db, config) -> dict[str, ui.Screen]:
    return {
        "home": await ui.home(db, config),
        "connections": await ui.connections(db, config),
        "watchdog": await ui.watchdog_screen(db, config),
        "reputation": await ui.reputation_screen(db, config),
        "settings": await ui.settings(db, config),
        "monitors": await ui.monitors_screen(db, config),
        "linkedin": await ui.linkedin(db, config),
        "instagram": await ui.instagram(db, config),
        "security": await ui.security(db, config),
        "when to write": await ui.when_to_write(db, config),
        "comments": await ui.comments_screen(db, config),
        "about": ui.about_screen(),
        "icons": ui.icons_screen(),
        "watchdog off": ui.watchdog_off_confirm(),
        "security emails": await ui.mail_screen(db, config),
        "mailbox off": ui.mail_off_confirm("box"),
        "worker off": ui.mail_off_confirm("wk"),
        **{f"prompt {kind}": ui.input_prompt(kind) for kind in ui.INPUT_PROMPTS},
    }


@pytest.fixture(params=["ru", "en"])
def lang(request):
    i18n.set_language(request.param)
    yield request.param
    i18n.set_language("ru")


@pytest.fixture
def fresh(config, lang):
    """A bot just deployed by the button: a token and nothing else."""
    return dataclasses.replace(config, lang=lang, app_commit="abc1234", **NO_NETWORKS)


async def test_a_fresh_install_speaks_plainly(db, fresh, lang):
    plain(f"{lang} welcome", ui.welcome(claimed=True, fresh=True))
    for name, screen in (await _screens(db, fresh)).items():
        plain_screen(f"{lang} fresh · {name}", screen)


async def test_networks_connected_from_the_chat_speak_plainly(db, fresh, lang):
    await connections.save(
        fresh, db,
        telegram_channel_id="@my_channel",
        youtube_channel_id="UC" + "x" * 22, youtube_api_key="k" * 39,
        instagram_username="my.account",
        linkedin_profile_url="https://www.linkedin.com/in/me/",
    )
    assert all(platform.enabled(fresh) for platform in BY_ID.values())
    plain(f"{lang} welcome", ui.welcome(claimed=False))
    for name, screen in (await _screens(db, fresh)).items():
        plain_screen(f"{lang} from the chat · {name}", screen)


def test_the_patterns_catch_what_they_are_for():
    for text in ("HEALTHCHECK_URL", "сильнее .env", "из базы IANA", "DevTools", "по user-agent", "адрес heartbeat",
                 "пробным пингом", "a test ping", "Python 3.15"):
        with pytest.raises(AssertionError):
            plain("self-test", text)
    plain("self-test", "ссылка вида https://hc-ping.com/… и «Grace Time»")

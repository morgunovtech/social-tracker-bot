"""The chat language.

Russian is the source language: every user-facing string in the code is
written in Russian and doubles as the lookup key; English lives in
bot/locales/en/. t() returns the text in the configured language
(BOT_LANG, «ru» by default), and a string without an English entry falls
back to Russian — a test renders every screen and alert in English and
fails on the first Cyrillic letter, so a key that drifts is caught.

Strings that are built at import time (platform labels, monitor names,
checklist items, weekday names) stay Russian in their constants and are
translated where they are shown: t() is called at render time, after
set_language() ran at startup.

Usage: t("Сохранено"); t("Профиль: {url}").format(url=…); for counts,
plural(n, "подписчик", "подписчика", "подписчиков") — the English forms
are looked up by the Russian singular.
"""

from __future__ import annotations

LANGUAGES = ("ru", "en")
_lang = "ru"
_strings: dict[str, str] = {}
_plurals: dict[str, tuple[str, str]] = {}


def set_language(lang: str) -> None:
    global _lang, _strings, _plurals
    if lang not in LANGUAGES:
        raise ValueError(f"Unknown language: {lang}")
    _lang = lang
    if lang == "en":
        from bot.locales.en import PLURALS, STRINGS

        _strings, _plurals = STRINGS, PLURALS
    else:
        _strings, _plurals = {}, {}


def language() -> str:
    return _lang


def t(text: str) -> str:
    """The text in the chat language; Russian when there is no translation."""
    if _lang == "ru":
        return text
    return _strings.get(text, text)


def plural(n: int, one: str, few: str, many: str) -> str:
    """The noun form for n: Russian one/few/many, or English singular/plural
    looked up by the Russian singular."""
    if _lang != "ru":
        forms = _plurals.get(one)
        if forms:
            return forms[0] if n == 1 else forms[1]
        return one if n == 1 else many
    if n % 10 == 1 and n % 100 != 11:
        return one
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return few
    return many

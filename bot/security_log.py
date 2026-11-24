"""The security log (the security_events table) as 🛡 Безопасность reads it.

The profile monitor and the security emails write one row per change or
mail; the screen lists the newest under «Последние события». A row keeps its
line before translation — the Russian template and its values
(humanize.Phrase) — so it reads in the chat language of the day it is shown.

Rows written by 1.5.0 and earlier hold the finished line in the language of
the day they were written. line() recognises the Russian lines those
versions wrote and shows them the way a new row is shown (an old 🚨 line as
today's 🔴 with «похоже на взлом»); a row it does not recognise is shown as
it is.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from bot import humanize
from bot.humanize import Phrase, phrase
from bot.monitors import CRITICAL, HIJACK, WARNING, level_icon
from bot.monitors.mail import KINDS
from bot.platforms import PLATFORMS
from bot.platforms.base import STATE


def line(detail: str | None) -> str:
    """The first line of a logged event in the chat language."""
    stored = humanize.load(detail)
    if stored is not None:
        return humanize.headline(humanize.render(stored))
    first = humanize.headline(detail or "")
    old = legacy(first)
    return humanize.render(old) if old is not None else first


# ── Rows of finished Russian text (≤ 1.5.0) ─────────────────────────────────
#
# Every first line the profile monitor and the mail monitor wrote, in each
# version: 1.0–1.4 marked a hijack sign with 🚨 and no words, 1.5.0 with 🔴
# and «похоже на взлом». Frozen: these are what old rows hold, not what the
# bot writes today.

_FIELDS = {label: kind for platform in PLATFORMS for label, kind in platform.profile_fields.values()}
_TITLES = {kind.title: kind for kind in KINDS}
_PLATFORM = "(?P<platform>{})".format("|".join(re.escape(p.label) for p in PLATFORMS))
_FIELD = "(?P<field>{})".format("|".join(re.escape(label) for label in sorted(_FIELDS, key=len, reverse=True)))
_TITLE = "(?P<title>{})".format("|".join(re.escape(title) for title in _TITLES))
_OLD_HIJACK = "похоже на взлом"
# The bot's own words a quoted value may be: an empty field, the bot's access.
_OWN_VALUES = ("(пусто)",)
_STATE_VALUES = ("есть", "нет")


def _value(field: str, value: str) -> Phrase | str:
    """A quoted value: translated when it is the bot's own word, as it is when
    it is someone's text (a title, a description)."""
    if value in _OWN_VALUES or (_FIELDS.get(field) == STATE and value in _STATE_VALUES):
        return phrase(value)
    return value


def _text_change(m: re.Match, hijack: bool) -> Phrase:
    params = {"platform": m["platform"], "field": phrase(m["field"]),
              "before": _value(m["field"], m["before"]), "after": _value(m["field"], m["after"])}
    if hijack:
        return phrase("{icon} {platform}: {hijack} — {field}: «{before}» → «{after}»", icon=CRITICAL,
                      hijack=phrase(HIJACK), **params)
    return phrase("{icon} {platform}: {field} — «{before}» → «{after}»", icon=WARNING, **params)


def _new_admin(m: re.Match) -> Phrase:
    return phrase("🔴 {label}: {hijack} — новый админ {name}", label=m["platform"], hijack=phrase(HIJACK),
                  name=m["name"])


def _owner(m: re.Match) -> Phrase:
    return phrase("🔴 {label}: {hijack} — сменился владелец: {before} → {after}", label=m["platform"],
                  hijack=phrase(HIJACK), before=m["before"], after=m["after"])


def _count(m: re.Match) -> Phrase:
    return phrase("🔴 {platform}: {hijack} — {field}: было {was}, стало {now} (−{drop})", platform=m["platform"],
                  hijack=phrase(HIJACK), field=phrase(m["field"]), was=m["was"], now=m["now"], drop=m["drop"])


def _mail(m: re.Match) -> Phrase:
    kind = _TITLES[m["title"]]
    if kind.level == "critical":
        return phrase("{icon} {network}: {hijack} — {title}", icon=level_icon(kind.level), network=m["network"],
                      hijack=phrase(HIJACK), title=phrase(kind.title))
    return phrase("{icon} {network}: {title}", icon=level_icon(kind.level), network=m["network"],
                  title=phrase(kind.title))


_QUOTED = "«(?P<before>.*)» → «(?P<after>.*)»"
_COUNTED = r"было (?P<was>\d+), стало (?P<now>\d+) \(−(?P<drop>\d+)\)"
_LEGACY: tuple[tuple[re.Pattern, Callable[[re.Match], Phrase]], ...] = tuple(
    (re.compile(pattern, re.S), render) for pattern, render in (
        # the profile monitor
        (f"^🔴 {_PLATFORM}: {_OLD_HIJACK} — {_FIELD}: {_QUOTED}$", lambda m: _text_change(m, hijack=True)),
        (f"^🚨 {_PLATFORM}: {_FIELD} — {_QUOTED}$", lambda m: _text_change(m, hijack=True)),
        (f"^🟠 {_PLATFORM}: {_FIELD} — {_QUOTED}$", lambda m: _text_change(m, hijack=False)),
        (f"^🟠 {_PLATFORM}: новая {_FIELD}$",
         lambda m: phrase("🟠 {platform}: новая {field}", platform=m["platform"], field=phrase(m["field"]))),
        (f"^🔴 {_PLATFORM}: {_OLD_HIJACK} — новый админ (?P<name>.+)$", _new_admin),
        (f"^🚨 {_PLATFORM}: новый админ — (?P<name>.+)$", _new_admin),
        (f"^🟠 {_PLATFORM}: админ удалён — (?P<name>.+)$",
         lambda m: phrase("🟠 {label}: админ удалён — {name}", label=m["platform"], name=m["name"])),
        (f"^🔴 {_PLATFORM}: {_OLD_HIJACK} — сменился владелец: (?P<before>.+) → (?P<after>.+)$", _owner),
        (f"^🚨 {_PLATFORM}: сменился владелец — (?P<before>.+) → (?P<after>.+)$", _owner),
        (f"^🔴 {_PLATFORM}: {_OLD_HIJACK} — {_FIELD}: {_COUNTED}$", _count),
        (f"^🚨 {_PLATFORM}: {_FIELD} — {_COUNTED}$", _count),
        # the security emails
        (f"^🔴 (?P<network>.+?): {_OLD_HIJACK} — {_TITLE}$", _mail),
        (f"^(?:🚨|🟠) (?P<network>.+?): {_TITLE}$", _mail),
    )
)


def legacy(text: str) -> Phrase | None:
    """The phrase behind a first line an older version stored as Russian
    text; None when it is not one of theirs."""
    for pattern, render in _LEGACY:
        m = pattern.match(text)
        if m:
            return render(m)
    return None

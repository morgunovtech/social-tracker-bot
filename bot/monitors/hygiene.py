"""Security hygiene: a checklist per connected account, a score out of 10 and
rare reminders.

No network exposes 2FA state or password age to third-party apps, so the
answers are the user's own marks (and password changes seen in security
emails). The bot never asks for a password.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from bot import platforms
from bot.config import Config
from bot.db import Database, parse_utc, utcnow
from bot.platforms.base import Platform

# Past this age the password line turns into a recommendation. Not a forced
# rotation (NIST advises changing on compromise, not on a timer): a nudge
# to check the password is unique and still the user's own.
PASSWORD_MAX_AGE_DAYS = 365
# The checklist is worth re-checking after this long.
REVIEW_EVERY_DAYS = 90
# At most one reminder per this many days.
NUDGE_EVERY_DAYS = 30
# How many recommendations a reminder lists.
NUDGE_TOP = 3
PASSWORD_POINTS = 1


@dataclass(frozen=True)
class Choice:
    value: str
    button: str
    points: int


@dataclass(frozen=True)
class Item:
    key: str
    label: str
    choices: tuple[Choice, ...]
    advice: str  # shown while the answer is not the best choice

    @property
    def best(self) -> int:
        return max(c.points for c in self.choices)


def _yes_no(points: int) -> tuple[Choice, ...]:
    return Choice("yes", "да", points), Choice("no", "нет", 0)


GENERIC = (
    Item(
        "2fa",
        "Двухфакторная защита",
        (Choice("app", "приложение/ключ", 4), Choice("sms", "SMS", 2), Choice("off", "нет", 0)),
        "включи 2FA через приложение-аутентификатор или ключ доступа: SMS перехватывают перевыпуском SIM",
    ),
    Item(
        "backup",
        "Резервные коды 2FA сохранены",
        _yes_no(2),
        "сохрани резервные коды 2FA в менеджере паролей: без них потеря телефона = потеря аккаунта",
    ),
    Item(
        "recovery",
        "Почта и телефон для восстановления актуальны",
        _yes_no(2),
        "проверь почту и телефон для восстановления: через них аккаунт возвращают после взлома",
    ),
    Item(
        "unique",
        "Пароль уникальный, из менеджера паролей",
        _yes_no(1),
        "поставь уникальный пароль из менеджера паролей: повторённый пароль утекает вместе с чужим сайтом",
    ),
)

TELEGRAM = (
    Item(
        "2fa",
        "Облачный пароль (2FA)",
        (Choice("on", "включён", 4), Choice("off", "нет", 0)),
        "включи облачный пароль (Настройки → Конфиденциальность): без него для входа хватает одного кода",
    ),
    Item(
        "backup",
        "Почта для восстановления облачного пароля",
        _yes_no(2),
        "укажи почту для восстановления облачного пароля",
    ),
    Item(
        "sessions",
        "Чужих сеансов нет (Настройки → Устройства)",
        _yes_no(2),
        "открой Настройки → Устройства и заверши незнакомые сеансы",
    ),
    Item(
        "unique",
        "Облачный пароль уникальный",
        _yes_no(1),
        "сделай облачный пароль уникальным, из менеджера паролей",
    ),
)

CHECKLISTS: dict[str, tuple[Item, ...]] = {"generic": GENERIC, "telegram": TELEGRAM}
MAX_SCORE = 10  # every checklist's best answers + PASSWORD_POINTS (checked in tests)

# "When did you last change the password?" buttons: label -> days ago.
PASSWORD_AGES = {"сегодня": 0, "месяц назад": 30, "полгода назад": 180, "год+ / не помню": PASSWORD_MAX_AGE_DAYS + 1}


def items(platform: Platform) -> tuple[Item, ...]:
    return CHECKLISTS[platform.checklist]


def _key(platform_id: str, item: str) -> str:
    return f"hygiene_{platform_id}_{item}"


async def answers(db: Database, platform: Platform) -> dict[str, str]:
    """Stored answers by item key, plus "pwd" — the ISO date of the last password change."""
    result: dict[str, str] = {}
    for key in [i.key for i in items(platform)] + ["pwd"]:
        value = await db.get_setting(_key(platform.id, key))
        if value is not None:
            result[key] = value
    return result


async def set_answer(db: Database, platform_id: str, item: str, value: str) -> None:
    await db.set_setting(_key(platform_id, item), value)
    await db.set_setting("hygiene_reviewed_at", utcnow().date().isoformat())


async def mark_password_changed(db: Database, platform_id: str, when: date) -> None:
    """Seen in a security email: updates the date, but is no review of the checklist."""
    await db.set_setting(_key(platform_id, "pwd"), when.isoformat())


def password_age(ans: dict[str, str], today: date) -> int | None:
    try:
        return (today - date.fromisoformat(ans["pwd"])).days
    except (KeyError, ValueError):
        return None


def score(platform: Platform, ans: dict[str, str], today: date) -> int:
    total = 0
    for item in items(platform):
        total += next((c.points for c in item.choices if c.value == ans.get(item.key)), 0)
    age = password_age(ans, today)
    if age is not None and age <= PASSWORD_MAX_AGE_DAYS:
        total += PASSWORD_POINTS
    return total


def recommendations(platform: Platform, ans: dict[str, str], today: date) -> list[str]:
    """What would raise the score, most valuable first."""
    if not ans:
        return [f"{platform.label}: пройди чек-лист — /security"]
    todo = [
        (item.best, f"{platform.label}: {item.advice}")
        for item in items(platform)
        if next((c.points for c in item.choices if c.value == ans.get(item.key)), 0) < item.best
    ]
    age = password_age(ans, today)
    if age is None:
        todo.append((PASSWORD_POINTS, f"{platform.label}: отметь, когда последний раз менял пароль"))
    elif age > PASSWORD_MAX_AGE_DAYS:
        todo.append((
            PASSWORD_POINTS,
            f"{platform.label}: пароль не менялся {age} дн. — смени, если он не уникальный или где-то светился",
        ))
    return [text for _, text in sorted(todo, key=lambda t: -t[0])]


async def overall(db: Database, config: Config) -> tuple[int, list[str]] | None:
    """(score out of 10 averaged over the enabled platforms, recommendations); None without platforms."""
    enabled = platforms.enabled(config)
    if not enabled:
        return None
    today = utcnow().date()
    scores: list[int] = []
    recs: list[str] = []
    for platform in enabled:
        ans = await answers(db, platform)
        scores.append(score(platform, ans, today))
        recs += recommendations(platform, ans, today)
    return round(sum(scores) / len(scores)), recs


def _item_line(item: Item, value: str | None) -> str:
    choice = next((c for c in item.choices if c.value == value), None)
    if choice is None:
        return f"  ❓ {item.label}: не отмечено"
    icon = "✅" if choice.points == item.best else "⚠️"
    return f"  {icon} {item.label}: {choice.button}"


def _password_line(ans: dict[str, str], today: date) -> str:
    age = password_age(ans, today)
    if age is None:
        return "  ❓ Смена пароля: не отмечена"
    if age > PASSWORD_MAX_AGE_DAYS:
        return f"  ⚠️ Пароль не менялся {age} дн."
    return "  ✅ Пароль сменён сегодня" if age == 0 else f"  ✅ Пароль сменён {age} дн. назад"


async def render(db: Database, config: Config) -> str:
    """The /security screen: score, checklist per account, what to do, recent events."""
    result = await overall(db, config)
    if result is None:
        return "🛡 Безопасность\n\nНет подключённых платформ — настрой хотя бы одну в .env."
    total, recs = result
    today = utcnow().date()
    lines = [f"🛡 Безопасность — {total}/{MAX_SCORE}", ""]
    for platform in platforms.enabled(config):
        ans = await answers(db, platform)
        if not ans:
            lines.append(f"{platform.label} ({platform.account}) — не заполнено")
            continue
        lines.append(f"{platform.label} ({platform.account}) — {score(platform, ans, today)}/{MAX_SCORE}")
        lines += [_item_line(item, ans.get(item.key)) for item in items(platform)]
        lines.append(_password_line(ans, today))
    if recs:
        lines += ["", "Что сделать:"] + [f"• {r}" for r in recs]
    events = await db.recent_events(5)
    if events:
        lines += ["", "Последние события:"]
        for e in events:
            day = parse_utc(e["occurred_at"]).strftime("%d.%m")
            lines.append(f"• {day} {e['detail'].splitlines()[0]}")
    lines += ["", "Пароли бот не спрашивает и не хранит: здесь только твои отметки."]
    return "\n".join(lines)


async def report_line(db: Database, config: Config) -> str | None:
    result = await overall(db, config)
    if result is None:
        return None
    return f"🛡 Безопасность: {result[0]}/{MAX_SCORE} — /security"


async def nudge(db: Database, config: Config) -> str | None:
    """A reminder at most every NUDGE_EVERY_DAYS, only when there is something to do."""
    result = await overall(db, config)
    if result is None:
        return None
    today = utcnow().date()
    last = await db.get_setting("hygiene_nudged_at")
    if last and today - date.fromisoformat(last) < timedelta(days=NUDGE_EVERY_DAYS):
        return None
    total, recs = result
    reviewed = await db.get_setting("hygiene_reviewed_at")
    review_age = (today - date.fromisoformat(reviewed)).days if reviewed else None
    review_due = review_age is not None and review_age >= REVIEW_EVERY_DAYS
    if not recs and not review_due:
        return None

    await db.set_setting("hygiene_nudged_at", today.isoformat())
    lines = [f"🛡 Безопасность: {total}/{MAX_SCORE}", ""]
    if reviewed is None:
        lines.append(
            "Пройди короткий чек-лист по своим аккаунтам: 2FA, резервные коды, пароли. "
            "Пароль вводить не нужно — только отметки. /security"
        )
    else:
        lines += [f"• {r}" for r in recs[:NUDGE_TOP]]
        if review_due:
            lines.append(f"Отметки не пересматривались {review_age} дн. — проверь, всё ли ещё так: /security")
    return "\n".join(lines)

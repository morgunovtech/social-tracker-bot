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
from bot.db import Database, utcnow
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
    label: str  # short: fits a button together with the answer
    question: str  # asked one at a time, with the choices as buttons
    choices: tuple[Choice, ...]
    advice: str  # why it matters; listed while the answer is not the best choice

    @property
    def best(self) -> int:
        return max(c.points for c in self.choices)


def _yes_no(points: int) -> tuple[Choice, ...]:
    return Choice("yes", "да", points), Choice("no", "нет", 0)


GENERIC = (
    Item(
        "2fa",
        "2FA",
        "Как включена двухфакторная защита?",
        (Choice("app", "приложение/ключ", 4), Choice("sms", "SMS", 2), Choice("off", "нет", 0)),
        "включи 2FA через приложение-аутентификатор или ключ доступа — SMS перехватывают перевыпуском SIM",
    ),
    Item(
        "backup",
        "Резервные коды",
        "Резервные коды 2FA сохранены?",
        _yes_no(2),
        "сохрани резервные коды 2FA в менеджере паролей — без них потеря телефона = потеря аккаунта",
    ),
    Item(
        "recovery",
        "Почта и телефон актуальны",
        "Почта и телефон для восстановления актуальны?",
        _yes_no(2),
        "проверь почту и телефон для восстановления — через них аккаунт возвращают после взлома",
    ),
    Item(
        "unique",
        "Уникальный пароль",
        "Пароль уникальный и хранится в менеджере паролей?",
        _yes_no(1),
        "поставь уникальный пароль из менеджера паролей — повторённый пароль утекает вместе с чужим сайтом",
    ),
)

TELEGRAM = (
    Item(
        "2fa",
        "Облачный пароль",
        "Облачный пароль включён? Настройки → Конфиденциальность → Облачный пароль",
        (Choice("on", "включён", 4), Choice("off", "нет", 0)),
        "включи облачный пароль (Настройки → Конфиденциальность) — без него для входа хватает одного кода",
    ),
    Item(
        "backup",
        "Почта восстановления",
        "К облачному паролю привязана почта для восстановления?",
        _yes_no(2),
        "укажи почту для восстановления облачного пароля — без неё забытый пароль не вернуть",
    ),
    Item(
        "sessions",
        "Только свои сеансы",
        "Все сеансы в Настройки → Устройства — твои?",
        _yes_no(2),
        "открой Настройки → Устройства и заверши незнакомые сеансы — через них читают чаты и управляют каналом",
    ),
    Item(
        "unique",
        "Уникальный пароль",
        "Облачный пароль уникальный, больше нигде не используется?",
        _yes_no(1),
        "сделай облачный пароль уникальным, из менеджера паролей",
    ),
)

CHECKLISTS: dict[str, tuple[Item, ...]] = {"generic": GENERIC, "telegram": TELEGRAM}
MAX_SCORE = 10  # every checklist's best answers + PASSWORD_POINTS (checked in tests)

# The last checklist step: when the password was changed. Stored as a date
# under the "pwd" key; the buttons set it to about that many days ago.
PASSWORD_KEY = "pwd"
PASSWORD_LABEL = "Смена пароля"
PASSWORD_QUESTION = "Когда пароль менялся последний раз?"
PASSWORD_ADVICE = "уникальный пароль не нужно менять по расписанию, но если он старше года или мог утечь — смени"
PASSWORD_AGES = {
    "сегодня": 0,
    "около месяца назад": 30,
    "около полугода назад": 180,
    "больше года / не помню": PASSWORD_MAX_AGE_DAYS + 1,
}


def items(platform: Platform) -> tuple[Item, ...]:
    return CHECKLISTS[platform.checklist]


def _key(platform_id: str, item: str) -> str:
    return f"hygiene_{platform_id}_{item}"


async def answers(db: Database, platform: Platform) -> dict[str, str]:
    """Stored answers by item key, plus "pwd" — the ISO date of the last password change."""
    result: dict[str, str] = {}
    for key in [i.key for i in items(platform)] + [PASSWORD_KEY]:
        value = await db.get_setting(_key(platform.id, key))
        if value is not None:
            result[key] = value
    return result


async def set_answer(db: Database, platform_id: str, item: str, value: str) -> None:
    await db.set_setting(_key(platform_id, item), value)
    await db.set_setting("hygiene_reviewed_at", utcnow().date().isoformat())


async def mark_password_changed(db: Database, platform_id: str, when: date) -> None:
    """Seen in a security email: updates the date, but is no review of the checklist."""
    await db.set_setting(_key(platform_id, PASSWORD_KEY), when.isoformat())


def password_age(ans: dict[str, str], today: date) -> int | None:
    try:
        return (today - date.fromisoformat(ans[PASSWORD_KEY])).days
    except (KeyError, ValueError):
        return None


def chosen(item: Item, ans: dict[str, str]) -> Choice | None:
    return next((c for c in item.choices if c.value == ans.get(item.key)), None)


def item_status(item: Item, ans: dict[str, str]) -> tuple[str, str]:
    """(icon, answer) of one item: ✅ best answer, ⚠️ could be better, ❓ not marked."""
    choice = chosen(item, ans)
    if choice is None:
        return "❓", "не отмечено"
    return ("✅" if choice.points == item.best else "⚠️"), choice.button


def password_status(ans: dict[str, str], today: date) -> tuple[str, str]:
    age = password_age(ans, today)
    if age is None:
        return "❓", "не отмечено"
    when = "сегодня" if age == 0 else f"{age} дн. назад"
    return ("⚠️" if age > PASSWORD_MAX_AGE_DAYS else "✅"), when


def score(platform: Platform, ans: dict[str, str], today: date) -> int:
    total = sum(c.points for item in items(platform) if (c := chosen(item, ans)))
    age = password_age(ans, today)
    if age is not None and age <= PASSWORD_MAX_AGE_DAYS:
        total += PASSWORD_POINTS
    return total


def _todo(platform: Platform, ans: dict[str, str], today: date) -> list[tuple[int, str]]:
    """(points it would add, what to do) for everything short of the best answer."""
    if not ans:
        return [(MAX_SCORE, f"{platform.label}: отметь пункты чек-листа — это пара минут")]
    todo = [
        (item.best, f"{platform.label}: {item.advice}")
        for item in items(platform)
        if (c := chosen(item, ans)) is None or c.points < item.best
    ]
    age = password_age(ans, today)
    if age is None:
        todo.append((PASSWORD_POINTS, f"{platform.label}: отметь, когда пароль менялся последний раз"))
    elif age > PASSWORD_MAX_AGE_DAYS:
        todo.append((
            PASSWORD_POINTS,
            f"{platform.label}: пароль не менялся {age} дн. — смени, если он не уникальный или где-то светился",
        ))
    return todo


def recommendations(platform: Platform, ans: dict[str, str], today: date) -> list[str]:
    """What would raise the score, most valuable first."""
    return [text for _, text in sorted(_todo(platform, ans, today), key=lambda t: -t[0])]


async def overall(db: Database, config: Config) -> tuple[int, list[str]] | None:
    """(score out of 10 averaged over the enabled platforms, recommendations
    across all of them, most valuable first); None without platforms."""
    enabled = platforms.enabled(config)
    if not enabled:
        return None
    today = utcnow().date()
    scores: list[int] = []
    todo: list[tuple[int, str]] = []
    for platform in enabled:
        ans = await answers(db, platform)
        scores.append(score(platform, ans, today))
        todo += _todo(platform, ans, today)
    return round(sum(scores) / len(scores)), [text for _, text in sorted(todo, key=lambda t: -t[0])]


async def report_line(db: Database, config: Config) -> str | None:
    result = await overall(db, config)
    if result is None:
        return None
    return f"🛡 Безопасность: {result[0]} из {MAX_SCORE} — /security"


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
    lines = [f"🛡 Безопасность: {total} из {MAX_SCORE}", ""]
    if reviewed is None:
        lines.append(
            "Пройди короткий чек-лист по своим аккаунтам: 2FA, резервные коды, пароли. "
            "Пароль вводить не нужно — только отметки."
        )
    else:
        lines += [f"• {r}" for r in recs[:NUDGE_TOP]]
        if review_due:
            lines.append(f"Отметки не пересматривались {review_age} дн. — проверь, всё ли ещё так.")
    lines += ["", "Открыть чек-лист: /security"]
    return "\n".join(lines)

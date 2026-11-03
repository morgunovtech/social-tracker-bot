"""The bot's menu: every screen as text and buttons, without Telegram I/O.

Navigation is a tree rooted at the home screen. Every other screen has a
«← <parent>» button, and a command opens the same screen as its button.
Texts are Telegram HTML, so every dynamic value goes through esc().

Callback data is "<screen>[:<args>]". Menus sent by older versions stay in
the chat, so the handlers send an id they no longer know to the home screen.
"""

from __future__ import annotations

import html
import platform as py_platform
from dataclasses import dataclass
from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from bot import monitors, platforms
from bot.config import DOW_ORDER, Config
from bot.db import Database, parse_utc, utcnow
from bot.monitors import hygiene
from bot.platforms import BY_ID, PLATFORMS
from bot.platforms.base import Platform
from bot.platforms.linkedin import COOKIE_AGING_DAYS, get_active_cookie, get_cookie_age_days
from bot.reporter import _fmt, build_history_all, build_history_table, build_week_report
from bot.scheduler import build_stats, get_report_schedule, is_quiet_mode

# Callback data of the screens and actions.
HOME = "home"
NOW = "now"
DYNAMICS = "dyn"
CHART = "chart"
TABLE = "tbl"
SECURITY = "sec"
SETTINGS = "set"
MONITORS = "mod"
LINKEDIN = "li"
LI_ENTER = "li:enter"
LI_CANCEL = "li:cancel"
HELP = "help"

# The persistent reply-keyboard button: tapping it sends this text back.
MENU_BUTTON_TEXT = "🏠 Меню"
# Reply keyboards of earlier versions stay on the user's screen until replaced.
LEGACY_MENU_BUTTON_TEXTS = ("📊 Меню",)

TABLE_PERIODS = (7, 14, 30, 90)

# One meaning per icon across the bot: on / chosen, off, unavailable.
ON, OFF, UNAVAILABLE = "✅", "⬜", "➖"

_DOW_SHORT = {"mon": "Пн", "tue": "Вт", "wed": "Ср", "thu": "Чт", "fri": "Пт", "sat": "Сб", "sun": "Вс"}
_DOW_EVERY = {
    "mon": "по понедельникам", "tue": "по вторникам", "wed": "по средам", "thu": "по четвергам",
    "fri": "по пятницам", "sat": "по субботам", "sun": "по воскресеньям",
}
_DAY_PRESETS = (("Каждый день", "*"), ("Будни", "mon-fri"), ("Выходные", "sat,sun"))

WELCOME = (
    "👋 Привет! Я слежу за подписчиками и безопасностью твоих аккаунтов.\n\n"
    "Пока всё в порядке, я молчу. О падении подписчиков, накрутке, смене названия, ссылок "
    "или админов и о письмах про новые входы пишу сразу, а сводку присылаю по расписанию.\n\n"
    f"Кнопка «{MENU_BUTTON_TEXT}» внизу экрана всегда возвращает на главную."
)


@dataclass(frozen=True)
class Screen:
    text: str
    keyboard: InlineKeyboardMarkup | None = None

    def noted(self, note: str) -> Screen:
        """The same screen under a line about what was just done."""
        return Screen(f"{esc(note)}\n\n{self.text}", self.keyboard)


def esc(value: object) -> str:
    return html.escape(str(value), quote=False)


def _button(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)


def _back(data: str, label: str) -> list[InlineKeyboardButton]:
    return [_button(f"← {label}", data)]


def _rows(buttons: list[InlineKeyboardButton], per_row: int = 2) -> list[list[InlineKeyboardButton]]:
    return [buttons[i : i + per_row] for i in range(0, len(buttons), per_row)]


def _check(on: bool) -> str:
    return ON if on else OFF


def _picked(selected: bool, label: str) -> str:
    return f"{ON} {label}" if selected else label


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def _titled(report: str) -> str:
    """A plain-text report with its first line as the bold title."""
    title, _, body = report.partition("\n")
    return f"<b>{esc(title)}</b>\n{esc(body)}" if body else f"<b>{esc(title)}</b>"


def persistent_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(MENU_BUTTON_TEXT)]],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Меню — кнопкой ниже, команды — через /",
    )


# ---------------------------------------------------------------------------
# Report schedule in words
# ---------------------------------------------------------------------------

def dow_days(dow: str) -> list[str]:
    """Days of a stored day-of-week expression ('*', 'sat', 'mon,thu', 'mon-fri'), in week order."""
    if dow == "*":
        return list(DOW_ORDER)
    if "-" in dow and "," not in dow:
        a, _, b = dow.partition("-")
        if a not in DOW_ORDER or b not in DOW_ORDER:
            return []
        i, j = DOW_ORDER.index(a), DOW_ORDER.index(b)
        span = DOW_ORDER[i : j + 1] if i <= j else DOW_ORDER[i:] + DOW_ORDER[: j + 1]
        return [d for d in DOW_ORDER if d in span]
    picked = set(dow.split(","))
    return [d for d in DOW_ORDER if d in picked]


def dow_expr(days: set[str]) -> str:
    """The stored expression for a set of days: '*' for all of them."""
    ordered = [d for d in DOW_ORDER if d in days]
    return "*" if len(ordered) == len(DOW_ORDER) else ",".join(ordered)


def dow_pretty(dow: str) -> str:
    """'каждый день', 'по будням', 'по субботам', 'Пн–Ср, Пт'."""
    days = dow_days(dow)
    if len(days) == len(DOW_ORDER):
        return "каждый день"
    if days == DOW_ORDER[:5]:
        return "по будням"
    if days == DOW_ORDER[5:]:
        return "по выходным"
    if len(days) == 1:
        return _DOW_EVERY[days[0]]
    runs: list[list[str]] = []
    for day in days:
        if runs and DOW_ORDER.index(runs[-1][-1]) == DOW_ORDER.index(day) - 1:
            runs[-1].append(day)
        else:
            runs.append([day])
    parts: list[str] = []
    for run in runs:
        if len(run) > 2:
            parts.append(f"{_DOW_SHORT[run[0]]}–{_DOW_SHORT[run[-1]]}")
        else:
            parts += [_DOW_SHORT[d] for d in run]
    return ", ".join(parts) or "ни в один день"


def next_report(dow: str, hour: int, minute: int, now: datetime | None = None) -> str:
    """When the next report goes out: 'сегодня в 08:00 UTC', 'сб 08.11 в 08:00 UTC'."""
    now = now or utcnow()
    days = set(dow_days(dow))
    for offset in range(8):
        day = (now + timedelta(days=offset)).date()
        at = datetime(day.year, day.month, day.day, hour, minute, tzinfo=now.tzinfo)
        code = DOW_ORDER[day.weekday()]
        if at <= now or code not in days:
            continue
        when = {0: "сегодня", 1: "завтра"}.get(offset) or f"{_DOW_SHORT[code].lower()} {day:%d.%m}"
        return f"{when} в {hour:02d}:{minute:02d} UTC"
    return "не запланирован"


# ---------------------------------------------------------------------------
# Home and followers
# ---------------------------------------------------------------------------

async def linkedin_is_manual(db: Database, config: Config) -> bool:
    """LinkedIn is connected but its number is typed in by hand: no working cookie."""
    if not BY_ID["linkedin"].enabled(config):
        return False
    if not await get_active_cookie(db, config):
        return True
    return await db.get_setting("cookie_expired_alerted") == "1"


async def home(db: Database, config: Config, report: str | None = None) -> Screen:
    """The follower report itself, the next report time and the way to everything else.

    report: a just-collected one, which carries that collection's failures.
    """
    if report is None:
        report, _ = await build_stats(db, config)
    dow, hour, minute = await get_report_schedule(db, config)
    text = f"{_titled(report)}\n\n⏭ Следующий отчёт: {next_report(dow, hour, minute)}"
    rows = [
        [_button("🔄 Обновить данные", NOW)],
        [_button("📈 Динамика", DYNAMICS), _button("🛡 Безопасность", SECURITY)],
    ]
    if await linkedin_is_manual(db, config):
        rows.append([_button("✏️ Ввести число LinkedIn", LI_ENTER)])
    rows.append([_button("⚙️ Настройки", SETTINGS), _button("❓ Помощь", HELP)])
    return Screen(text, InlineKeyboardMarkup(rows))


def loading() -> Screen:
    return Screen("⏳ Собираю свежие данные — это займёт несколько секунд…")


async def dynamics(db: Database) -> Screen:
    rows = [
        [_button("🖼 График за 30 дней", CHART), _button("📋 По дням", TABLE)],
        _back(HOME, "Главная"),
    ]
    return Screen(_titled(await build_week_report(db)), InlineKeyboardMarkup(rows))


async def table(db: Database, config: Config, platform_id: str = "all", days: int = 7) -> Screen:
    """Day-by-day table; platform and period are switched on the same screen."""
    if platform_id == "all":
        text = await build_history_all(db, days)
    else:
        text = await build_history_table(db, platform_id, days)
    choices = [("all", "Все")] + [(p.id, p.label) for p in platforms.enabled(config)]
    if platform_id not in dict(choices):  # a disconnected platform asked for by /history
        choices.append((platform_id, BY_ID[platform_id].label))
    which = [_button(_picked(pid == platform_id, label), f"{TABLE}:{pid}:{days}") for pid, label in choices]
    period = [_button(_picked(d == days, f"{d} дн."), f"{TABLE}:{platform_id}:{d}") for d in TABLE_PERIODS]
    return Screen(text, InlineKeyboardMarkup(_rows(which) + [period, _back(DYNAMICS, "Динамика")]))


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

def _platform_state(ans: dict[str, str], points: int) -> tuple[str, str]:
    if not ans:
        return "❓", "не заполнено"
    return ("✅" if points == hygiene.MAX_SCORE else "⚠️"), f"{points} из {hygiene.MAX_SCORE}"


async def security(db: Database, config: Config, top: int = 5) -> Screen:
    """Score, each account's state, what to do first, recent security events."""
    result = await hygiene.overall(db, config)
    if result is None:
        return Screen(
            "<b>🛡 Безопасность</b>\n\nНет подключённых платформ — подключи хотя бы одну в .env.",
            InlineKeyboardMarkup([_back(HOME, "Главная")]),
        )
    total, recs = result
    today = utcnow().date()
    lines = [f"<b>🛡 Безопасность: {total} из {hygiene.MAX_SCORE}</b>", ""]
    rows: list[list[InlineKeyboardButton]] = []
    for platform in platforms.enabled(config):
        ans = await hygiene.answers(db, platform)
        icon, state = _platform_state(ans, hygiene.score(platform, ans, today))
        lines.append(f"{icon} {platform.label} ({esc(platform.account)}) — {state}")
        rows.append([_button(f"{icon} {platform.label} · {state}", f"{SECURITY}:edit:{platform.id}")])
    if recs:
        lines += ["", "<b>Что сделать в первую очередь</b>"] + [f"• {esc(r)}" for r in recs[:top]]
        if len(recs) > top:
            lines.append(f"…и ещё {len(recs) - top} — в чек-листах аккаунтов")
    events = await db.recent_events(5)
    if events:
        lines += ["", "<b>Последние события</b>"]
        for e in events:
            day = parse_utc(e["occurred_at"]).strftime("%d.%m")
            lines.append(f"• {day} {esc(e['detail'].splitlines()[0])}")
    lines += ["", "Нажми на аккаунт, чтобы отметить пункты. Пароли я не спрашиваю и не храню."]
    rows.append(_back(HOME, "Главная"))
    return Screen("\n".join(lines), InlineKeyboardMarkup(rows))


def question_keys(platform: Platform) -> list[str]:
    """The checklist's steps in order: its items, then the password change."""
    return [item.key for item in hygiene.items(platform)] + [hygiene.PASSWORD_KEY]


async def next_unanswered(db: Database, platform: Platform, after: str) -> str | None:
    ans = await hygiene.answers(db, platform)
    keys = question_keys(platform)
    return next((key for key in keys[keys.index(after) + 1 :] if key not in ans), None)


async def checklist(db: Database, platform: Platform) -> Screen:
    """One account: a button per item with its current answer."""
    ans = await hygiene.answers(db, platform)
    today = utcnow().date()
    text = (
        f"<b>🛡 {esc(platform.label)}: {hygiene.score(platform, ans, today)} из {hygiene.MAX_SCORE}</b>\n"
        f"{esc(platform.account)}\n\n"
        "Нажми на пункт, чтобы отметить, как сейчас. Пароль вводить не нужно — только отметки."
    )
    rows: list[list[InlineKeyboardButton]] = []
    for item in hygiene.items(platform):
        icon, answer = hygiene.item_status(item, ans)
        rows.append([_button(f"{icon} {item.label}: {answer}", f"{SECURITY}:ask:{platform.id}:{item.key}")])
    icon, when = hygiene.password_status(ans, today)
    rows.append([
        _button(f"{icon} {hygiene.PASSWORD_LABEL}: {when}", f"{SECURITY}:ask:{platform.id}:{hygiene.PASSWORD_KEY}")
    ])
    rows.append(_back(SECURITY, "Безопасность"))
    return Screen(text, InlineKeyboardMarkup(rows))


async def question(db: Database, platform: Platform, key: str) -> Screen:
    """One checklist item: the question, why it matters, the answers as buttons."""
    ans = await hygiene.answers(db, platform)
    keys = question_keys(platform)
    if key == hygiene.PASSWORD_KEY:
        asked, advice = hygiene.PASSWORD_QUESTION, hygiene.PASSWORD_ADVICE
        _, current = hygiene.password_status(ans, utcnow().date())
        choices = _rows([
            _button(_cap(label), f"{SECURITY}:pwd:{platform.id}:{days}")
            for label, days in hygiene.PASSWORD_AGES.items()
        ])
    else:
        item = next(i for i in hygiene.items(platform) if i.key == key)
        asked, advice = item.question, item.advice
        chosen = hygiene.chosen(item, ans)
        current = chosen.button if chosen else "не отмечено"
        choices = [[
            _button(_picked(c is chosen, _cap(c.button)), f"{SECURITY}:set:{platform.id}:{key}:{c.value}")
            for c in item.choices
        ]]
    text = (
        f"<b>🛡 {esc(platform.label)} · вопрос {keys.index(key) + 1} из {len(keys)}</b>\n\n"
        f"<b>{esc(asked)}</b>\n\n"
        f"Совет: {esc(advice)}.\n\n"
        f"Сейчас: {esc(current)}"
    )
    return Screen(text, InlineKeyboardMarkup(choices + [_back(f"{SECURITY}:edit:{platform.id}", platform.label)]))


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

async def settings(db: Database, config: Config) -> Screen:
    dow, hour, minute = await get_report_schedule(db, config)
    quiet = await is_quiet_mode(db, config)
    build = f"сборка {esc(config.app_commit[:7])} · " if config.app_commit else ""
    text = "\n".join([
        "<b>⚙️ Настройки</b>",
        "",
        f"📅 Отчёт: {dow_pretty(dow)}, в {hour:02d}:{minute:02d} UTC",
        "Данные собираются каждый день в это время, а отчёт приходит в выбранные дни.",
        "",
        f"🔕 Тихий режим: {'включён' if quiet else 'выключен'}",
        "Когда включён, неделя без изменений — это одна строка вместо отчёта.",
        "",
        f"<i>Версия: {build}Python {py_platform.python_version()}</i>",
    ])
    tools = [_button("🧩 Мониторинги", MONITORS)]
    if BY_ID["linkedin"].enabled(config):
        tools.append(_button("💼 LinkedIn", LINKEDIN))
    rows = [
        [_button("📅 Дни отчёта", f"{SETTINGS}:days"), _button("🕗 Время отчёта", f"{SETTINGS}:time")],
        [_button(f"{_check(quiet)} Тихий режим", f"{SETTINGS}:quiet")],
        tools,
        _back(HOME, "Главная"),
    ]
    return Screen(text, InlineKeyboardMarkup(rows))


async def report_days(db: Database, config: Config) -> Screen:
    dow, hour, minute = await get_report_schedule(db, config)
    days = dow_days(dow)
    text = (
        "<b>📅 Дни отчёта</b>\n\n"
        f"Сейчас: {dow_pretty(dow)}, в {hour:02d}:{minute:02d} UTC\n\n"
        "Отметь дни, когда присылать отчёт. Данные собираются каждый день, "
        "а о проблемах я пишу сразу, в любой день."
    )
    toggles = [_button(f"{_check(d in days)} {_DOW_SHORT[d]}", f"{SETTINGS}:day:{d}") for d in DOW_ORDER]
    presets = [
        _button(_picked(dow_days(expr) == days, label), f"{SETTINGS}:days:{expr}") for label, expr in _DAY_PRESETS
    ]
    rows = [toggles[:4], toggles[4:], presets, _back(SETTINGS, "Настройки")]
    return Screen(text, InlineKeyboardMarkup(rows))


async def report_time(db: Database, config: Config) -> Screen:
    _, hour, minute = await get_report_schedule(db, config)
    text = (
        "<b>🕗 Время отчёта</b>\n\n"
        f"Сейчас: {hour:02d}:{minute:02d} UTC — это {(hour + 3) % 24:02d}:{minute:02d} по Москве\n\n"
        "Выбери час по UTC. Точное время с минутами — командой, например /settime 08:30"
    )
    hours = [
        _button(_picked((h, 0) == (hour, minute), f"{h:02d}:00"), f"{SETTINGS}:hour:{h}") for h in range(24)
    ]
    return Screen(text, InlineKeyboardMarkup(_rows(hours, 4) + [_back(SETTINGS, "Настройки")]))


async def monitors_screen(db: Database, config: Config) -> Screen:
    lines = ["<b>🧩 Мониторинги</b>", "", "<b>Платформы</b> — подключаются в .env"]
    for p in PLATFORMS:
        if p.enabled(config):
            lines.append(f"{ON} {p.label} — {esc(p.target(config))}")
        else:
            lines.append(f"{UNAVAILABLE} {p.label} — не подключено")
    lines += ["", "<b>Проверки</b> — нажми, чтобы включить или выключить"]
    rows: list[list[InlineKeyboardButton]] = []
    for m in monitors.MONITORS:
        if not m.requires(config):
            lines.append(f"{UNAVAILABLE} {esc(m.label)} — нужно: {esc(m.needs)}")
            continue
        on = await monitors.is_switched_on(db, m.id)
        lines.append(f"{_check(on)} {esc(m.label)} — {esc(m.description)}")
        rows.append([_button(f"{_check(on)} {m.label}", f"{MONITORS}:{m.id}")])
    rows.append(_back(SETTINGS, "Настройки"))
    return Screen("\n".join(lines), InlineKeyboardMarkup(rows))


async def linkedin(db: Database, config: Config) -> Screen:
    """How the LinkedIn number is collected, the cookie's age, the manual input."""
    lines = ["<b>💼 LinkedIn</b>", "", f"Профиль: {esc(config.linkedin_profile_url or 'не задан')}"]
    latest = await db.get_latest("linkedin")
    if latest:
        how = "введено вручную" if latest["source"] == "manual" else "собрано по cookie"
        when = parse_utc(latest["collected_at"]).strftime("%d.%m")
        lines.append(f"Последнее значение: {_fmt(latest['count'])} — {how} {when}")
    else:
        lines.append("Последнее значение: пока нет")
    lines.append("")

    age = await get_cookie_age_days(db)
    if await db.get_setting("cookie_expired_alerted") == "1":
        lines.append("🔴 LinkedIn отклонил cookie: пришли новый через /setcookie или вводи число вручную.")
    elif age is not None and age >= COOKIE_AGING_DAYS:
        lines.append(f"⚠️ Cookie установлен {age} дн. назад и скоро истечёт — пора обновить.")
    elif age is not None:
        lines.append(
            f"✅ Число собирается само по cookie. Он установлен {age} дн. назад, "
            f"напомню обновить через ~{COOKIE_AGING_DAYS - age} дн."
        )
    elif await db.get_setting("linkedin_li_at") or config.linkedin_li_at:
        lines.append(
            "✅ Число собирается само по cookie, но срок его жизни я не вижу. "
            "Пришли cookie через /setcookie — и я напомню, когда его обновить."
        )
    else:
        lines.append("✏️ Число вводится вручную: cookie не задан.")
    lines += [
        "",
        "<b>Автосбор</b>: отправь /setcookie и значение cookie li_at "
        "(linkedin.com → DevTools → Application → Cookies). Я проверю его и сразу удалю сообщение.",
        "<i>LinkedIn запрещает автоматический доступ, так что автосбор — на твой риск.</i>",
    ]
    rows = [[_button("✏️ Ввести число вручную", LI_ENTER)], _back(SETTINGS, "Настройки")]
    return Screen("\n".join(lines), InlineKeyboardMarkup(rows))


async def linkedin_prompt(db: Database) -> Screen:
    latest = await db.get_latest("linkedin")
    current = f"\nСейчас: {_fmt(latest['count'])}" if latest else ""
    return Screen(
        f"<b>✏️ LinkedIn вручную</b>\n\nПришли число подписчиков одним сообщением, например 4520.{current}",
        InlineKeyboardMarkup([[_button("Отмена", LI_CANCEL)]]),
    )


def linkedin_retry() -> Screen:
    return Screen(
        "Это не похоже на число. Пришли только цифры, например 4520, или нажми «Отмена».",
        InlineKeyboardMarkup([[_button("Отмена", LI_CANCEL)]]),
    )


def linkedin_confirm(prev: int, count: int) -> Screen:
    """A number far from the last one is likely a typo: ask before it becomes the baseline."""
    return Screen(
        f"<b>⚠️ Проверь число</b>\n\n{_fmt(count)} сильно отличается от прошлого значения "
        f"{_fmt(prev)}. Возможно, это опечатка.",
        InlineKeyboardMarkup([
            [_button(f"Сохранить {_fmt(count)}", f"{LINKEDIN}:save:{count}")],
            [_button("✏️ Ввести заново", LI_ENTER)],
            [_button("Отмена", HOME)],
        ]),
    )


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

def help_screen() -> Screen:
    text = "\n".join([
        "<b>❓ Помощь</b>",
        "",
        "Каждый день я собираю подписчиков и слежу за безопасностью аккаунтов. "
        "Пока всё в порядке — молчу; о проблеме пишу сразу, а сводку присылаю по расписанию.",
        "",
        "<b>Значки</b>",
        "✅ в порядке или включено · ⬜ выключено · ➖ не подключено",
        "⚠️ нужно внимание · ❓ не отмечено",
        "🟠 изменение · 🔴 сбой · 🚨 похоже на взлом",
        "",
        "<b>Команды</b>",
        "/start — главная",
        "/now — обновить данные",
        "/week — динамика за неделю и график",
        "/security — безопасность аккаунтов",
        "/settings — настройки",
        "/history [платформа] [дни] — таблица по дням, до 90 дней",
        "/linkedin &lt;число&gt; — ввести LinkedIn вручную",
        "/setcookie &lt;li_at&gt; — cookie LinkedIn для автосбора",
        "/settime ЧЧ:ММ — время отчёта по UTC",
        "/setday &lt;дни&gt; — дни отчёта: sat, mon-fri, mon,thu, daily",
        "/setquiet on|off — тихий режим",
        "/modules — мониторинги",
        "",
        "<b>Бэкап</b>",
        "По воскресеньям я присылаю файл с базой. Чтобы вернуть историю, ответь на него "
        "командой /restore — уже собранное не перезапишется.",
    ])
    return Screen(text, InlineKeyboardMarkup([_back(HOME, "Главная")]))

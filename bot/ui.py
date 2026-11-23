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
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from bot import monitors, notifier, platforms
from bot.config import DOW_ORDER, Config
from bot.db import Database, parse_utc, utcnow
from bot.i18n import language, plural, t
from bot.monitors import comments, hygiene
from bot.platforms import BY_ID, PLATFORMS
from bot.platforms import instagram as ig
from bot.platforms.base import Platform
from bot.platforms.linkedin import COOKIE_AGING_DAYS, get_active_cookie, get_cookie_age_days
from bot.reporter import _fmt, build_history_all, build_history_table, build_week_report
from bot.scheduler import build_stats, get_report_schedule, get_report_tz, is_quiet_mode

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
INSTAGRAM = "ig"
LI_ENTER = "li:enter"
LI_CANCEL = "li:cancel"
HELP = "help"
COMMENTS = comments.CALLBACK

# The persistent reply-keyboard button: tapping it sends this text back.
# Russian is the key; the keyboard shows t(MENU_BUTTON_TEXT).
MENU_BUTTON_TEXT = "🏠 Меню"
# Reply keyboards of earlier versions stay on the user's screen until replaced.
LEGACY_MENU_BUTTON_TEXTS = ("📊 Меню",)

TABLE_PERIODS = (7, 14, 30, 90)
# «🔕 Помолчать» presets: the argument of /mute each button stands for.
MUTE_CHOICES = ("1h", "4h", "8h", "1d")

# One meaning per icon across the bot: on / chosen, off, unavailable.
ON, OFF, UNAVAILABLE = "✅", "⬜", "➖"

# Russian names, translated with t() where they are shown (see bot/i18n.py).
_DOW_SHORT = {"mon": "Пн", "tue": "Вт", "wed": "Ср", "thu": "Чт", "fri": "Пт", "sat": "Сб", "sun": "Вс"}
_DOW_EVERY = {
    "mon": "по понедельникам", "tue": "по вторникам", "wed": "по средам", "thu": "по четвергам",
    "fri": "по пятницам", "sat": "по субботам", "sun": "по воскресеньям",
}
_DAY_PRESETS = (("Каждый день", "*"), ("Будни", "mon-fri"), ("Выходные", "sat,sun"))

# The zone picker, west to east; any other zone is set with /settz.
COMMON_ZONES = (
    ("America/New_York", "Нью-Йорк"),
    ("UTC", "UTC"),
    ("Europe/London", "Лондон"),
    ("Europe/Berlin", "Берлин"),
    ("Europe/Kaliningrad", "Калининград"),
    ("Europe/Moscow", "Москва"),
    ("Europe/Samara", "Самара"),
    ("Asia/Tbilisi", "Тбилиси"),
    ("Asia/Yekaterinburg", "Екатеринбург"),
    ("Asia/Almaty", "Алматы"),
    ("Asia/Novosibirsk", "Новосибирск"),
    ("Asia/Vladivostok", "Владивосток"),
)
_ZONE_NAMES = dict(COMMON_ZONES)

def welcome(claimed: bool = False) -> str:
    """The /start greeting in the chat language; claimed — this /start just
    made the sender the owner."""
    head = t("✅ Теперь этот бот твой: он отвечает только тебе.") + "\n\n" if claimed else ""
    return head + t(
        "👋 Привет! Я слежу за подписчиками и безопасностью твоих аккаунтов.\n\n"
        "Пока всё в порядке, я молчу. О падении подписчиков, накрутке, смене названия, ссылок "
        "или админов и о письмах про новые входы пишу сразу, а сводку присылаю по расписанию.\n\n"
        "Кнопка «{menu}» внизу экрана всегда возвращает на главную."
    ).format(menu=t(MENU_BUTTON_TEXT))


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


def _days(n: int) -> str:
    """The unit after a number of days: 'дн.' in Russian, day/days in English."""
    return plural(n, "дн.", "дн.", "дн.")


def _titled(report: str) -> str:
    """A plain-text report with its first line as the bold title."""
    title, _, body = report.partition("\n")
    return f"<b>{esc(title)}</b>\n{esc(body)}" if body else f"<b>{esc(title)}</b>"


def persistent_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(t(MENU_BUTTON_TEXT))]],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder=t("Меню — кнопкой ниже, команды — через /"),
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
        return t("каждый день")
    if days == DOW_ORDER[:5]:
        return t("по будням")
    if days == DOW_ORDER[5:]:
        return t("по выходным")
    if len(days) == 1:
        return t(_DOW_EVERY[days[0]])
    runs: list[list[str]] = []
    for day in days:
        if runs and DOW_ORDER.index(runs[-1][-1]) == DOW_ORDER.index(day) - 1:
            runs[-1].append(day)
        else:
            runs.append([day])
    parts: list[str] = []
    for run in runs:
        if len(run) > 2:
            parts.append(f"{t(_DOW_SHORT[run[0]])}–{t(_DOW_SHORT[run[-1]])}")
        else:
            parts += [t(_DOW_SHORT[d]) for d in run]
    return ", ".join(parts) or t("ни в один день")


def utc_offset(tz: ZoneInfo, now: datetime | None = None) -> str:
    """The zone's offset at the moment: 'UTC+3', 'UTC−4', 'UTC+5:30', 'UTC+0'."""
    offset = (now or utcnow()).astimezone(tz).utcoffset()
    minutes = round(offset.total_seconds() / 60) if offset else 0
    hours, rest = divmod(abs(minutes), 60)
    return f"UTC{'−' if minutes < 0 else '+'}{hours}" + (f":{rest:02d}" if rest else "")


def tz_name(tz: ZoneInfo, now: datetime | None = None) -> str:
    """'Москва (UTC+3)', 'Asia/Kolkata (UTC+5:30)', 'UTC'."""
    if tz.key == "UTC":
        return "UTC"
    name = t(_ZONE_NAMES[tz.key]) if tz.key in _ZONE_NAMES else tz.key
    return f"{name} ({utc_offset(tz, now)})"


def clock(hour: int, minute: int, tz: ZoneInfo) -> str:
    """A report time in the owner's zone: '11:00'; '08:00 UTC' while the zone is UTC."""
    return f"{hour:02d}:{minute:02d}" + (" UTC" if tz.key == "UTC" else "")


def next_report(dow: str, hour: int, minute: int, tz: ZoneInfo, now: datetime | None = None) -> str:
    """When the next report goes out, in its zone: 'сегодня в 11:00', 'сб 08.11 в 08:00 UTC'."""
    now = (now or utcnow()).astimezone(tz)
    days = set(dow_days(dow))
    for offset in range(8):
        day = (now + timedelta(days=offset)).date()
        at = datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)
        code = DOW_ORDER[day.weekday()]
        if at <= now or code not in days:
            continue
        if offset == 0:
            when = t("сегодня")
        elif offset == 1:
            when = t("завтра")
        else:
            # Russian writes the weekday in lower case mid-sentence; English keeps 'Sat'.
            short = t(_DOW_SHORT[code])
            when = f"{short.lower() if language() == 'ru' else short} {day:%d.%m}"
        return t("{when} в {time}").format(when=when, time=clock(hour, minute, tz))
    return t("не запланирован")


def shift_schedule(
    dow: str, hour: int, minute: int, old: ZoneInfo, new: ZoneInfo, now: datetime | None = None
) -> tuple[str, int, int]:
    """The same report moment told in another zone: its time and, when it crosses
    midnight, its days. Offsets are today's, so across a DST change the moment
    is kept as it is today."""
    today = (now or utcnow()).astimezone(old).date()
    at = datetime(today.year, today.month, today.day, hour, minute, tzinfo=old)
    moved = at.astimezone(new)
    shift = (moved.date() - at.date()).days
    if shift:
        dow = dow_expr({DOW_ORDER[(DOW_ORDER.index(d) + shift) % 7] for d in dow_days(dow)})
    return dow, moved.hour, moved.minute


async def _schedule(db: Database, config: Config) -> tuple[str, int, int, ZoneInfo]:
    dow, hour, minute = await get_report_schedule(db, config)
    return dow, hour, minute, await get_report_tz(db, config)


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
    dow, hour, minute, tz = await _schedule(db, config)
    text = f"{_titled(report)}\n\n" + t("⏭ Следующий отчёт: {next}").format(next=next_report(dow, hour, minute, tz))
    silence = await notifier.silence_status(db, config)
    if silence:
        text += f"\n{esc(silence)}"
    rows = [
        [_button(t("🔄 Обновить данные"), NOW)],
        [_button(t("📈 Динамика"), DYNAMICS), _button(t("🛡 Безопасность"), SECURITY)],
    ]
    if await linkedin_is_manual(db, config):
        rows.append([_button(t("✏️ Ввести число LinkedIn"), LI_ENTER)])
    rows.append([_button(t("⚙️ Настройки"), SETTINGS), _button(t("❓ Помощь"), HELP)])
    return Screen(text, InlineKeyboardMarkup(rows))


def loading() -> Screen:
    return Screen(t("⏳ Собираю свежие данные — это займёт несколько секунд…"))


async def dynamics(db: Database) -> Screen:
    rows = [
        [_button(t("🖼 График за 30 дней"), CHART), _button(t("📋 По дням"), TABLE)],
        _back(HOME, t("Главная")),
    ]
    return Screen(_titled(await build_week_report(db)), InlineKeyboardMarkup(rows))


async def table(db: Database, config: Config, platform_id: str = "all", days: int = 7) -> Screen:
    """Day-by-day table; platform and period are switched on the same screen."""
    if platform_id == "all":
        text = await build_history_all(db, days)
    else:
        text = await build_history_table(db, platform_id, days)
    choices = [("all", t("Все"))] + [(p.id, p.label) for p in platforms.enabled(config)]
    if platform_id not in dict(choices):  # a disconnected platform asked for by /history
        choices.append((platform_id, BY_ID[platform_id].label))
    which = [_button(_picked(pid == platform_id, label), f"{TABLE}:{pid}:{days}") for pid, label in choices]
    period = [
        _button(_picked(d == days, f"{d} {_days(d)}"), f"{TABLE}:{platform_id}:{d}") for d in TABLE_PERIODS
    ]
    return Screen(text, InlineKeyboardMarkup(_rows(which) + [period, _back(DYNAMICS, t("Динамика"))]))


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

def _platform_state(ans: dict[str, str], points: int) -> tuple[str, str]:
    if not ans:
        return "❓", t("не заполнено")
    state = t("{points} из {max}").format(points=points, max=hygiene.MAX_SCORE)
    return ("✅" if points == hygiene.MAX_SCORE else "⚠️"), state


async def security(db: Database, config: Config, top: int = 5) -> Screen:
    """Score, each account's state, what to do first, recent security events."""
    result = await hygiene.overall(db, config)
    if result is None:
        return Screen(
            t("<b>🛡 Безопасность</b>\n\nНет подключённых платформ — подключи хотя бы одну в .env."),
            InlineKeyboardMarkup([_back(HOME, t("Главная"))]),
        )
    total, recs = result
    today = utcnow().date()
    lines = [t("<b>🛡 Безопасность: {total} из {max}</b>").format(total=total, max=hygiene.MAX_SCORE), ""]
    rows: list[list[InlineKeyboardButton]] = []
    for platform in platforms.enabled(config):
        ans = await hygiene.answers(db, platform)
        icon, state = _platform_state(ans, hygiene.score(platform, ans, today))
        lines.append(f"{icon} {platform.label} ({esc(t(platform.account))}) — {state}")
        rows.append([_button(f"{icon} {platform.label} · {state}", f"{SECURITY}:edit:{platform.id}")])
    if recs:
        lines += ["", t("<b>Что сделать в первую очередь</b>")] + [f"• {esc(t(r))}" for r in recs[:top]]
        if len(recs) > top:
            lines.append(t("…и ещё {n} — в чек-листах аккаунтов").format(n=len(recs) - top))
    events = await db.recent_events(5)
    if events:
        lines += ["", t("<b>Последние события</b>")]
        for e in events:
            day = parse_utc(e["occurred_at"]).strftime("%d.%m")
            lines.append(f"• {day} {esc(e['detail'].splitlines()[0])}")
    lines += ["", t("Нажми на аккаунт, чтобы отметить пункты. Пароли я не спрашиваю и не храню.")]
    rows.append([_button(t("💬 Комментарии канала"), COMMENTS)])
    rows.append(_back(HOME, t("Главная")))
    return Screen("\n".join(lines), InlineKeyboardMarkup(rows))


COMMENTS_STATS_DAYS = 30


async def comments_screen(db: Database, config: Config) -> Screen:
    """What the comment monitor does, and the accuracy table its cards built."""
    monitor = monitors.BY_ID[comments.MONITOR_ID]
    lines = [t("<b>💬 Комментарии канала</b>"), ""]
    if not monitor.requires(config):
        lines.append(
            t("Не подключено — нужно: {needs}. Тогда я буду смотреть каждый комментарий в группе обсуждения "
              "и присылать карточку с кнопками на запрещённый контент.").format(needs=esc(t(monitor.needs)))
        )
        return Screen("\n".join(lines), InlineKeyboardMarkup([_back(SECURITY, t("Безопасность"))]))
    on = await monitors.is_switched_on(db, comments.MONITOR_ID)
    lines.append(
        t("Режим: только сообщаю. Каждый комментарий в группе обсуждения смотрит модель; на запрещённый контент "
          "приходит карточка, а удалить или забанить — кнопкой под ней. Сам я ничего не удаляю.")
    )
    if config.comments_chat_id is None:
        lines.append(t("Группа: группа обсуждения канала {channel}, бот должен быть в ней админом с правом удалять "
                       "сообщения и блокировать участников.").format(channel=esc(config.telegram_channel_id)))
    else:
        lines.append(t("Группа: {chat}, бот должен быть в ней админом с правом удалять сообщения и блокировать "
                       "участников.").format(chat=esc(config.comments_chat_id)))
    lines.append(t("Модель: {model}").format(model=esc(config.comments_model)))
    if not on:
        lines.append(t("⬜ Выключено в /modules"))
    stats = await db.review_stats(COMMENTS_STATS_DAYS)
    lines += ["", t("<b>За {days} дней</b>").format(days=COMMENTS_STATS_DAYS)]
    lines.append(t("Проверено комментариев: {n}").format(n=stats["checked"]))
    by_category = stats["categories"]
    if not by_category:
        lines.append(t("Помеченных пока нет."))
    else:
        lines.append(t("Помечено · подтверждено · ложных:"))
        confirmed = false_positive = 0
        for category, row in sorted(by_category.items(), key=lambda kv: -kv[1]["flagged"]):
            icon = "🔴" if category in comments.classifier.DANGEROUS else "🟠"
            label = esc(t(comments.LABELS.get(category, category)))
            lines.append(f"{icon} {label} — {row['flagged']} · {row['confirmed'] or 0} · {row['false_positive'] or 0}")
            confirmed += row["confirmed"] or 0
            false_positive += row["false_positive"] or 0
        judged = confirmed + false_positive
        if judged:
            lines.append(
                t("Точность по твоим отметкам: {pct}% ({confirmed} из {judged})").format(
                    pct=round(100 * confirmed / judged), confirmed=confirmed, judged=judged
                )
            )
        else:
            lines.append(t("Отмечай карточки кнопками — из отметок складывается точность."))
    return Screen("\n".join(lines), InlineKeyboardMarkup([_back(SECURITY, t("Безопасность"))]))


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
    text = t(
        "<b>🛡 {label}: {points} из {max}</b>\n"
        "{account}\n\n"
        "Нажми на пункт, чтобы отметить, как сейчас. Пароль вводить не нужно — только отметки."
    ).format(
        label=esc(platform.label),
        points=hygiene.score(platform, ans, today),
        max=hygiene.MAX_SCORE,
        account=esc(t(platform.account)),
    )
    rows: list[list[InlineKeyboardButton]] = []
    for item in hygiene.items(platform):
        icon, answer = hygiene.item_status(item, ans)
        rows.append([_button(f"{icon} {t(item.label)}: {t(answer)}", f"{SECURITY}:ask:{platform.id}:{item.key}")])
    icon, when = hygiene.password_status(ans, today)
    rows.append([
        _button(
            f"{icon} {t(hygiene.PASSWORD_LABEL)}: {t(when)}", f"{SECURITY}:ask:{platform.id}:{hygiene.PASSWORD_KEY}"
        )
    ])
    rows.append(_back(SECURITY, t("Безопасность")))
    return Screen(text, InlineKeyboardMarkup(rows))


async def question(db: Database, platform: Platform, key: str) -> Screen:
    """One checklist item: the question, why it matters, the answers as buttons."""
    ans = await hygiene.answers(db, platform)
    keys = question_keys(platform)
    if key == hygiene.PASSWORD_KEY:
        asked, advice = t(hygiene.PASSWORD_QUESTION), t(hygiene.PASSWORD_ADVICE)
        _, current = hygiene.password_status(ans, utcnow().date())
        current = t(current)
        choices = _rows([
            _button(_cap(t(label)), f"{SECURITY}:pwd:{platform.id}:{days}")
            for label, days in hygiene.PASSWORD_AGES.items()
        ])
    else:
        item = next(i for i in hygiene.items(platform) if i.key == key)
        asked, advice = t(item.question), t(item.advice)
        chosen = hygiene.chosen(item, ans)
        current = t(chosen.button) if chosen else t("не отмечено")
        choices = [[
            _button(_picked(c is chosen, _cap(t(c.button))), f"{SECURITY}:set:{platform.id}:{key}:{c.value}")
            for c in item.choices
        ]]
    text = t(
        "<b>🛡 {label} · вопрос {n} из {total}</b>\n\n"
        "<b>{question}</b>\n\n"
        "Совет: {advice}.\n\n"
        "Сейчас: {current}"
    ).format(
        label=esc(platform.label),
        n=keys.index(key) + 1,
        total=len(keys),
        question=esc(asked),
        advice=esc(advice),
        current=esc(current),
    )
    return Screen(text, InlineKeyboardMarkup(choices + [_back(f"{SECURITY}:edit:{platform.id}", platform.label)]))


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

async def settings(db: Database, config: Config) -> Screen:
    dow, hour, minute, tz = await _schedule(db, config)
    quiet = await is_quiet_mode(db, config)
    build = t("сборка {commit} · ").format(commit=esc(config.app_commit[:7])) if config.app_commit else ""
    text = "\n".join([
        t("<b>⚙️ Настройки</b>"),
        "",
        t("📅 Отчёт: {days}, в {time}").format(days=dow_pretty(dow), time=clock(hour, minute, tz)),
        t("🌍 Часовой пояс: {tz}").format(tz=esc(tz_name(tz))),
        t("Данные собираются каждый день в это время, а отчёт приходит в выбранные дни."),
        "",
        t("🔕 Тихий режим: {state}").format(state=t("включён") if quiet else t("выключен")),
        t("Когда включён, неделя без изменений — это одна строка вместо отчёта."),
        "",
        t("🔔 Когда писать: {when}").format(when=esc(await _when_summary(db, config))),
        "",
        t("<i>Версия: {build}Python {python}</i>").format(build=build, python=py_platform.python_version()),
    ])
    tools = [_button(t("🧩 Мониторинги"), MONITORS)]
    if BY_ID["instagram"].enabled(config):
        tools.append(_button("📸 Instagram", INSTAGRAM))
    if BY_ID["linkedin"].enabled(config):
        tools.append(_button("💼 LinkedIn", LINKEDIN))
    rows = [
        [_button(t("📅 Дни отчёта"), f"{SETTINGS}:days"), _button(t("🕗 Время отчёта"), f"{SETTINGS}:time")],
        [_button(t("🌍 Часовой пояс"), f"{SETTINGS}:tz")],
        [_button(f"{_check(quiet)} {t('Тихий режим')}", f"{SETTINGS}:quiet"), _button(t("🔔 Когда писать"), f"{SETTINGS}:when")],
        tools,
        _back(HOME, t("Главная")),
    ]
    return Screen(text, InlineKeyboardMarkup(rows))


async def _when_summary(db: Database, config: Config) -> str:
    """One line for the settings screen: the quiet hours and a running mute."""
    hours = await notifier.quiet_hours(db)
    text = t("тихие часы {hours}").format(hours=notifier.quiet_hours_pretty(hours)) if hours else t("всегда")
    until = await notifier.mute_until_local(db, config)
    if until:
        text += " · " + t("тишина до {until}").format(until=until)
    return text


async def when_to_write(db: Database, config: Config) -> Screen:
    """Quiet hours (presets, off) and «🔕 Помолчать»: what rings through either is fixed."""
    hours = await notifier.quiet_hours(db)
    tz = await get_report_tz(db, config)
    until = await notifier.mute_until_local(db, config)
    lines = [
        t("<b>🔔 Когда писать</b>"),
        "",
        t("🌙 Тихие часы: {state}").format(
            state=notifier.quiet_hours_pretty(hours) if hours else t("выключены")
        ),
        t("Ночью некритичное ждёт до утра и приходит одной сводкой. Часы — по поясу {tz}.").format(
            tz=esc(tz_name(tz))
        ),
        "",
        t("🔕 Помолчать: {state}").format(state=t("до {until}").format(until=until) if until else t("сейчас не молчу")),
        t("На время: всё, кроме критичного, ждёт и приходит сводкой, когда тишина закончится. Команда: /mute 8h, снять — /unmute."),
        "",
        esc(notifier.what_rings_through()),
    ]
    current = f"{hours[0]}-{hours[1]}" if hours else None
    quiet_row = [
        _button(_picked(preset == current, f"🌙 {notifier.quiet_hours_pretty(notifier.parse_quiet_hours(preset))}"), f"{SETTINGS}:qh:{preset}")
        for preset in notifier.QUIET_PRESETS
    ] + [_button(_picked(hours is None, t("🌙 выкл")), f"{SETTINGS}:qh:off")]
    mute_row = [_button(f"🔕 {_duration_label(choice)}", f"{SETTINGS}:mute:{choice}") for choice in MUTE_CHOICES]
    rows = [quiet_row, mute_row]
    if until:
        rows.append([_button(t("🔔 Снять тишину"), f"{SETTINGS}:mute:off")])
    rows.append(_back(SETTINGS, t("Настройки")))
    return Screen("\n".join(lines), InlineKeyboardMarkup(rows))


def _duration_label(choice: str) -> str:
    """'1h' → '1 ч', '1d' → '1 д' — a mute button's label."""
    n, unit = int(choice[:-1]), choice[-1]
    if unit == "d":
        return f"{n} {plural(n, 'день', 'дня', 'дней')}"
    if unit == "h":
        return f"{n} {plural(n, 'час', 'часа', 'часов')}"
    return f"{n} {plural(n, 'минута', 'минуты', 'минут')}"


def mute_note(until: str) -> str:
    """The answer to /mute and the 🔕 buttons."""
    return (
        t("🔕 Молчу до {until}.").format(until=until) + "\n"
        + notifier.what_rings_through() + "\n"
        + t("Снова писать обо всём: /unmute")
    )


async def report_days(db: Database, config: Config) -> Screen:
    dow, hour, minute, tz = await _schedule(db, config)
    days = dow_days(dow)
    text = t(
        "<b>📅 Дни отчёта</b>\n\n"
        "Сейчас: {days}, в {time}\n\n"
        "Отметь дни, когда присылать отчёт. Данные собираются каждый день, "
        "а о проблемах я пишу сразу, в любой день."
    ).format(days=dow_pretty(dow), time=clock(hour, minute, tz))
    toggles = [_button(f"{_check(d in days)} {t(_DOW_SHORT[d])}", f"{SETTINGS}:day:{d}") for d in DOW_ORDER]
    presets = [
        _button(_picked(dow_days(expr) == days, t(label)), f"{SETTINGS}:days:{expr}") for label, expr in _DAY_PRESETS
    ]
    rows = [toggles[:4], toggles[4:], presets, _back(SETTINGS, t("Настройки"))]
    return Screen(text, InlineKeyboardMarkup(rows))


async def report_time(db: Database, config: Config) -> Screen:
    _, hour, minute, tz = await _schedule(db, config)
    if tz.key == "UTC":
        zone = t("Часы ниже — по UTC. Чтобы выбирать по своим часам, укажи часовой пояс.")
    else:
        zone = t("Часы ниже — по поясу {tz}.").format(tz=esc(tz_name(tz)))
    text = t(
        "<b>🕗 Время отчёта</b>\n\n"
        "Сейчас: {time}\n\n"
        "{zone} Точное время с минутами — командой, например /settime 08:30"
    ).format(time=clock(hour, minute, tz), zone=zone)
    hours = [
        _button(_picked((h, 0) == (hour, minute), f"{h:02d}:00"), f"{SETTINGS}:hour:{h}") for h in range(24)
    ]
    rows = _rows(hours, 4) + [[_button(t("🌍 Часовой пояс"), f"{SETTINGS}:tz")], _back(SETTINGS, t("Настройки"))]
    return Screen(text, InlineKeyboardMarkup(rows))


async def timezone(db: Database, config: Config) -> Screen:
    tz = await get_report_tz(db, config)
    text = t(
        "<b>🌍 Часовой пояс</b>\n\n"
        "Сейчас: {tz}, там {now:%H:%M}\n\n"
        "По этому поясу считаются время и дни отчёта. Выбери свой или пришли его название командой, "
        "например /settz Asia/Kolkata"
    ).format(tz=esc(tz_name(tz)), now=utcnow().astimezone(tz))
    picks = []
    for key, name in COMMON_ZONES:
        label = name if key == "UTC" else f"{t(name)} {utc_offset(ZoneInfo(key)).removeprefix('UTC')}"
        picks.append(_button(_picked(key == tz.key, label), f"{SETTINGS}:tz:{key}"))
    return Screen(text, InlineKeyboardMarkup(_rows(picks) + [_back(SETTINGS, t("Настройки"))]))


async def monitors_screen(db: Database, config: Config) -> Screen:
    lines = [t("<b>🧩 Мониторинги</b>"), "", t("<b>Платформы</b> — подключаются в .env")]
    for p in PLATFORMS:
        if p.enabled(config):
            lines.append(f"{ON} {p.label} — {esc(p.target(config))}")
        else:
            lines.append(f"{UNAVAILABLE} {p.label} — {t('не подключено')}")
    lines += ["", t("<b>Проверки</b> — нажми, чтобы включить или выключить")]
    rows: list[list[InlineKeyboardButton]] = []
    for m in monitors.MONITORS:
        if not m.requires(config):
            lines.append(
                t("{icon} {label} — нужно: {needs}").format(icon=UNAVAILABLE, label=esc(t(m.label)), needs=esc(t(m.needs)))
            )
            continue
        on = await monitors.is_switched_on(db, m.id)
        lines.append(f"{_check(on)} {esc(t(m.label))} — {esc(t(m.description))}")
        rows.append([_button(f"{_check(on)} {t(m.label)}", f"{MONITORS}:{m.id}")])
    rows.append(_back(SETTINGS, t("Настройки")))
    return Screen("\n".join(lines), InlineKeyboardMarkup(rows))


async def linkedin(db: Database, config: Config) -> Screen:
    """How the LinkedIn number is collected, the cookie's age, the manual input."""
    lines = [
        "<b>💼 LinkedIn</b>",
        "",
        t("Профиль: {url}").format(url=esc(config.linkedin_profile_url or t("не задан"))),
    ]
    latest = await db.get_latest("linkedin")
    if latest:
        how = t("введено вручную") if latest["source"] == "manual" else t("собрано по cookie")
        when = parse_utc(latest["collected_at"]).strftime("%d.%m")
        lines.append(
            t("Последнее значение: {count} — {how} {when}").format(count=_fmt(latest["count"]), how=how, when=when)
        )
    else:
        lines.append(t("Последнее значение: пока нет"))
    lines.append("")

    age = await get_cookie_age_days(db)
    if await db.get_setting("cookie_expired_alerted") == "1":
        lines.append(t("🟠 LinkedIn отклонил cookie: пришли новый через /setcookie или вводи число вручную."))
    elif age is not None and age >= COOKIE_AGING_DAYS:
        lines.append(
            t("⚠️ Cookie установлен {age} {d} назад и скоро истечёт — пора обновить.").format(age=age, d=_days(age))
        )
    elif age is not None:
        left = COOKIE_AGING_DAYS - age
        lines.append(
            t(
                "✅ Число собирается само по cookie. Он установлен {age} {d} назад, "
                "напомню обновить через ~{left} {ld}."
            ).format(age=age, d=_days(age), left=left, ld=_days(left))
        )
    elif await db.get_setting("linkedin_li_at") or config.linkedin_li_at:
        lines.append(
            t(
                "✅ Число собирается само по cookie, но срок его жизни я не вижу. "
                "Пришли cookie через /setcookie — и я напомню, когда его обновить."
            )
        )
    else:
        lines.append(t("✏️ Число вводится вручную: cookie не задан."))
    lines += [
        "",
        t(
            "<b>Автосбор</b>: отправь /setcookie и значение cookie li_at "
            "(linkedin.com → DevTools → Application → Cookies). Я проверю его и сразу удалю сообщение."
        ),
        t("<i>LinkedIn запрещает автоматический доступ, так что автосбор — на твой риск.</i>"),
    ]
    rows = [[_button(t("✏️ Ввести число вручную"), LI_ENTER)], _back(SETTINGS, t("Настройки"))]
    return Screen("\n".join(lines), InlineKeyboardMarkup(rows))


async def instagram(db: Database, config: Config) -> Screen:
    """How the Instagram number is collected and how long the token lives."""
    lines = [
        "<b>📸 Instagram</b>",
        "",
        t("Аккаунт: {account}").format(account=esc(BY_ID["instagram"].target(config) or t("не задан"))),
    ]
    latest = await db.get_latest("instagram")
    if latest:
        when = parse_utc(latest["collected_at"]).strftime("%d.%m")
        lines.append(t("Последнее значение: {count} — собрано {when}").format(count=_fmt(latest["count"]), when=when))
    else:
        lines.append(t("Последнее значение: пока нет"))
    lines.append("")

    token = await ig.get_active_token(db, config)
    age = await ig.get_token_age_days(db)
    if not token:
        lines.append(t("⚠️ Токена нет: без него число не собирается."))
    elif await db.get_setting("instagram_token_alerted") == "1":
        lines.append(t("🟠 Instagram отклонил токен: отозван или истёк — пришли новый через /igtoken."))
    elif age is None:
        lines.append(t("✅ Число собирается само по токену из переменных окружения."))
    else:
        lines.append(
            t(
                "✅ Число собирается само по токену. Он задан {age} {d} назад и бессрочный: "
                "если Meta его отзовёт, я скажу."
            ).format(age=age, d=_days(age))
        )
    lines += [
        "",
        t(
            "<b>Как подключить</b>: аккаунт должен быть профессиональным (Автор или Бизнес). "
            "На developers.facebook.com создай приложение с вариантом «Instagram API», открой "
            "«API setup with Unified login», добавь свой аккаунт как Instagram Tester, прими приглашение "
            "в Instagram (Настройки → Website permissions → Tester invitations) и нажми «Generate token». "
            "Отправь /igtoken и токен одним сообщением — я проверю его и сразу удалю сообщение."
        ),
        t("<i>Это официальный API: бот читает только публичные данные своего аккаунта.</i>"),
    ]
    return Screen("\n".join(lines), InlineKeyboardMarkup([_back(SETTINGS, t("Настройки"))]))


async def linkedin_prompt(db: Database) -> Screen:
    latest = await db.get_latest("linkedin")
    current = t("\nСейчас: {count}").format(count=_fmt(latest["count"])) if latest else ""
    return Screen(
        t("<b>✏️ LinkedIn вручную</b>\n\nПришли число подписчиков одним сообщением, например 4520.{current}").format(
            current=current
        ),
        InlineKeyboardMarkup([[_button(t("Отмена"), LI_CANCEL)]]),
    )


def linkedin_retry() -> Screen:
    return Screen(
        t("Это не похоже на число. Пришли только цифры, например 4520, или нажми «Отмена»."),
        InlineKeyboardMarkup([[_button(t("Отмена"), LI_CANCEL)]]),
    )


def linkedin_confirm(prev: int, count: int) -> Screen:
    """A number far from the last one is likely a typo: ask before it becomes the baseline."""
    return Screen(
        t(
            "<b>⚠️ Проверь число</b>\n\n{count} сильно отличается от прошлого значения "
            "{prev}. Возможно, это опечатка."
        ).format(count=_fmt(count), prev=_fmt(prev)),
        InlineKeyboardMarkup([
            [_button(t("Сохранить {count}").format(count=_fmt(count)), f"{LINKEDIN}:save:{count}")],
            [_button(t("✏️ Ввести заново"), LI_ENTER)],
            [_button(t("Отмена"), HOME)],
        ]),
    )


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

def help_screen() -> Screen:
    text = "\n".join([
        t("<b>❓ Помощь</b>"),
        "",
        t(
            "Каждый день я собираю подписчиков и слежу за безопасностью аккаунтов. "
            "Пока всё в порядке — молчу; о проблеме пишу сразу, а сводку присылаю по расписанию."
        ),
        "",
        t("<b>Значки</b>"),
        t("✅ в порядке или включено · ⬜ выключено · ➖ не подключено"),
        t("⚠️ нужно внимание · ❓ не отмечено"),
        t("🚨 похоже на взлом · 🔴 аккаунт недоступен — звонят сразу, даже ночью"),
        t("🟠 изменение или сбой — тихо; ночью и в тишине ждёт сводки"),
        "",
        t("<b>Команды</b>"),
        t("/start — главная"),
        t("/now — обновить данные"),
        t("/week — динамика за неделю и график"),
        t("/security — безопасность аккаунтов"),
        t("/settings — настройки"),
        t("/history [платформа] [дни] — таблица по дням, до 90 дней"),
        t("/linkedin &lt;число&gt; — ввести LinkedIn вручную"),
        t("/setcookie &lt;li_at&gt; — cookie LinkedIn для автосбора"),
        t("/igtoken &lt;токен&gt; — токен Instagram для автосбора"),
        t("/settime ЧЧ:ММ — время отчёта"),
        t("/setday &lt;дни&gt; — дни отчёта: sat, mon-fri, mon,thu, daily"),
        t("/settz &lt;пояс&gt; — часовой пояс, например Europe/Moscow"),
        t("/setquiet on|off — тихий режим"),
        t("/mute &lt;время&gt; — помолчать: 1h, 8h, 1d (по умолчанию 8h); /unmute — снять"),
        t("/modules — мониторинги"),
        t("/comments — комментарии канала: что проверено и насколько точно"),
        "",
        t("<b>Бэкап</b>"),
        t(
            "По воскресеньям я присылаю файл с базой. Чтобы вернуть историю, ответь на него "
            "командой /restore — уже собранное не перезапишется."
        ),
    ])
    return Screen(text, InlineKeyboardMarkup([_back(HOME, t("Главная"))]))

"""The bot's menu: every screen as text and buttons, without Telegram I/O.

Navigation is a tree rooted at the home screen. Every other screen has a
«← <parent>» button, and a command opens the same screen as its button.
Texts are Telegram HTML, so every dynamic value goes through esc(), which
also strips invisible direction and format characters (monitors.clean).

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

from bot import monitors, notifier, platforms, security_log, watchdog
from bot.callbacks import (
    BACKUP,
    CHANNEL,
    CHART,
    COMMENTS,
    CONNECTIONS,
    DYNAMICS,
    HOME,
    IG_TOKEN,
    INPUT_CANCEL,
    INSTAGRAM,
    LI_CANCEL,
    LI_COOKIE,
    LI_ENTER,
    LINKEDIN,
    MONITORS,
    MUTE,
    MUTE_OFF,
    NOW,
    RESTORE,
    SECURITY,
    SETTINGS,
    TABLE,
    TZ_OTHER,
    WATCHDOG,
    WD_URL,
)
from bot.config import DOW_ORDER, Config
from bot.db import HELD_KEEP_DAYS, Database, parse_utc, utcnow
from bot.i18n import language, plural, t
from bot.monitors import channel, comments, hygiene
from bot.platforms import BY_ID, PLATFORMS
from bot.platforms import instagram as ig
from bot.platforms.base import Platform
from bot.platforms.linkedin import COOKIE_AGING_DAYS, get_active_cookie, get_cookie_age_days
from bot.reporter import _fmt, build_history_all, build_history_table, build_week_report
from bot.scheduler import build_stats, get_report_schedule, get_report_tz, is_quiet_mode

# Callback data of the screens and actions: bot/callbacks.py, re-exported here
# for the handlers (ui.HOME …); the two monitors name theirs the same way.
assert COMMENTS == comments.CALLBACK and CHANNEL == channel.CALLBACK

# The persistent reply keyboard (BOT_PRINCIPLES §2): tapping a button sends
# its text back. Three doors under the input field, one tap from anywhere in
# a chat full of alerts — the dashboard, what the bot does with every command,
# what the icons mean. No ☰ command list: these are the way in, and a refresh
# and a mute are one tap away on the home screen. Russian is the key; the
# keyboard shows t(…).
HOME_BUTTON_TEXT = "🏠 Главная"
ABOUT_BUTTON_TEXT = "📖 Что я умею"
ICONS_BUTTON_TEXT = "❓ Значки"
# Reply keyboards of earlier versions stay on the owner's screen until a
# message brings the new one, and their buttons keep doing what they did:
# the menu of 1.0–1.4, and the refresh and the mute of 1.4.0.
LEGACY_HOME_BUTTON_TEXTS = ("📊 Меню", "🏠 Меню")
LEGACY_REFRESH_BUTTON_TEXT = "🔄 Обновить"
LEGACY_MUTE_BUTTON_TEXT = "🔕 Тихо 8 ч"
# The labels every screen shares (§2): the way home, the way out of a step.
HOME_LABEL, CANCEL_LABEL = "🏠 Главная", "✖️ Отмена"

TABLE_PERIODS = (7, 14, 30, 90)
# The minutes a report may start at by button; any minute by /settime.
MINUTE_CHOICES = (0, 15, 30, 45)
# «🔕 Помолчать» presets: the argument of /mute each button stands for.
MUTE_CHOICES = ("1h", "4h", "8h", "1d")

# One meaning per icon across the bot (the dictionary: bot/monitors/__init__.py):
# on / chosen, off, not connected.
ON, OFF, UNAVAILABLE = monitors.OK, monitors.OFF, monitors.NOT_CONNECTED

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
    ("Asia/Tashkent", "Ташкент"),
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
        "Под полем ввода — три кнопки: «{home}» — главный экран, «{about}» — что я делаю и все команды, "
        "«{icons}» — что значат значки и что звонит."
    ).format(home=t(HOME_BUTTON_TEXT), about=t(ABOUT_BUTTON_TEXT), icons=t(ICONS_BUTTON_TEXT))


@dataclass(frozen=True)
class Screen:
    text: str
    keyboard: InlineKeyboardMarkup | None = None

    def noted(self, note: str) -> Screen:
        """The same screen under a line about what was just done."""
        return Screen(f"{esc(note)}\n\n{self.text}", self.keyboard)


def esc(value: object) -> str:
    return html.escape(monitors.clean(value), quote=False)


def _button(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)


def _back(data: str, label: str) -> list[InlineKeyboardButton]:
    return [_button(f"← {label}", data)]


def _home() -> list[InlineKeyboardButton]:
    """The way back to the dashboard, named the same everywhere (§2)."""
    return [_button(t(HOME_LABEL), HOME)]


def _cancel(data: str) -> InlineKeyboardButton:
    return _button(t(CANCEL_LABEL), data)


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
        [[KeyboardButton(t(HOME_BUTTON_TEXT)), KeyboardButton(t(ABOUT_BUTTON_TEXT)), KeyboardButton(t(ICONS_BUTTON_TEXT))]],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder=t("Всё — кнопками ниже"),
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
    """LinkedIn is connected but its number is typed in by hand: no working
    cookie, or no number yet — the first one read by cookie is confirmed by hand."""
    if not BY_ID["linkedin"].enabled(config):
        return False
    if not await get_active_cookie(db, config) or await db.get_latest("linkedin") is None:
        return True
    return await db.get_setting("cookie_expired_alerted") == "1"


async def last_collected(db: Database, config: Config, tz: ZoneInfo) -> str | None:
    """«сегодня 08:00» / «21.11 08:00» — when the newest row of an enabled
    platform was collected; None before the first collection."""
    newest: datetime | None = None
    for platform in platforms.enabled(config):
        latest = await db.get_latest(platform.id)
        if latest is None:
            continue
        try:
            at = parse_utc(latest["collected_at"])
        except (ValueError, TypeError):
            continue
        if newest is None or at > newest:
            newest = at
    if newest is None:
        return None
    local = newest.astimezone(tz)
    today = utcnow().astimezone(tz).date()
    return t("сегодня {time}").format(time=local.strftime("%H:%M")) if local.date() == today else local.strftime("%d.%m %H:%M")


async def setup_todo(db: Database, config: Config) -> list[tuple[str, str]]:
    """What a fresh install still needs, as (callback, line): the time zone
    while none was ever chosen (the report would come at 08:00 UTC), the
    Instagram token, the first LinkedIn number. Empty once everything is set."""
    todo: list[tuple[str, str]] = []
    if await db.get_setting("report_tz") is None:
        tz = await get_report_tz(db, config)
        todo.append((f"{SETTINGS}:tz", t("часовой пояс — пока {tz}, выбери свой").format(tz=tz_name(tz))))
    if BY_ID["instagram"].enabled(config) and not await ig.get_active_token(db, config):
        todo.append((CONNECTIONS, t("токен Instagram — без него число не собирается")))
    if BY_ID["linkedin"].enabled(config) and await db.get_latest("linkedin") is None:
        todo.append((CONNECTIONS, t("LinkedIn — cookie для автосбора или первое число вручную")))
    return todo


async def home(db: Database, config: Config, report: str | None = None) -> Screen:
    """The follower report itself, the next report time and the way to everything else.

    report: a just-collected one, which carries that collection's failures.
    """
    if report is None:
        report, _ = await build_stats(db, config)
    dow, hour, minute, tz = await _schedule(db, config)
    lines = [_titled(report), ""]
    collected = await last_collected(db, config, tz)
    if collected:
        lines.append(t("🕒 Последний сбор: {when}").format(when=esc(collected)))
    lines.append(t("⏭ Следующий отчёт: {next}").format(next=next_report(dow, hour, minute, tz)))
    silence = await notifier.silence_status(db, config)
    if silence:
        lines.append(esc(silence))
    todo = await setup_todo(db, config)
    if todo:
        lines += ["", t("🧭 Осталось настроить:")] + [f"• {esc(line)}" for _, line in todo]
    rows = [
        [_button(t("🔄 Обновить данные"), NOW)],
        [_button(t("📈 Динамика"), DYNAMICS), _button(t("🛡 Безопасность"), SECURITY)],
    ]
    middle = [_button(t("📣 Канал"), CHANNEL)] if BY_ID["telegram"].enabled(config) else []
    middle.append(_button(t("🔌 Подключения"), CONNECTIONS))
    rows.append(middle)
    if any(callback == f"{SETTINGS}:tz" for callback, _ in todo):
        rows.append([_button(t("🌍 Выбрать часовой пояс"), f"{SETTINGS}:tz")])
    if await linkedin_is_manual(db, config):
        rows.append([_button(t("✏️ Ввести число LinkedIn"), LI_ENTER)])
    # A refresh is the first row; silence and the settings the last — one tap
    # from the dashboard, as the bottom buttons of 1.4.0 were.
    if await notifier.mute_until(db) is not None:
        silence_button = _button(t("🔔 Снять тишину"), f"{MUTE_OFF}:{HOME}")
    else:
        silence_button = _button(t("🔕 Помолчать…"), MUTE)
    rows.append([silence_button, _button(t("⚙️ Настройки"), SETTINGS)])
    return Screen("\n".join(lines), InlineKeyboardMarkup(rows))


def mute_picker() -> Screen:
    """«🔕 Помолчать…» on the home screen: how long, and what still rings."""
    text = "\n".join([
        t("<b>🔕 Помолчать</b>"),
        "",
        esc(notifier.what_rings_through()),
        "",
        t("Тихие часы на каждую ночь — ⚙️ Настройки → 🔔 Когда писать. Команда: /mute 8h, снять — /unmute."),
    ])
    presets = [_button(f"🔕 {_duration_label(choice)}", f"{MUTE}:{choice}:{HOME}") for choice in MUTE_CHOICES]
    return Screen(text, InlineKeyboardMarkup([*_rows(presets), _home()]))


async def connections(db: Database, config: Config) -> Screen:
    """Every network: whether it is in .env, whether its number comes in by
    itself, and the button that fixes what does not. The one screen a fresh
    install needs; the per-network screens hang under it."""
    lines = [t("<b>🔌 Подключения</b>"), ""]
    rows: list[list[InlineKeyboardButton]] = []
    for platform in PLATFORMS:
        if not platform.enabled(config):
            lines.append(t("{icon} {label} — не подключено: {needs} в .env").format(
                icon=UNAVAILABLE, label=platform.label, needs=_ENV_NEEDS[platform.id]
            ))
            continue
        target = esc(platform.target(config))
        latest = await db.get_latest(platform.id)
        state = ""
        if platform.id == "instagram":
            if not await ig.get_active_token(db, config):
                state = t("🟠 нужен токен")
            elif await db.get_setting("instagram_token_alerted") == "1":
                state = t("🟠 токен отклонён")
        elif platform.id == "linkedin":
            if await db.get_setting("cookie_expired_alerted") == "1":
                state = t("🟠 cookie отклонён, число вручную")
            elif not await get_active_cookie(db, config):
                state = t("✏️ число вручную")
            elif latest is None:
                state = t("🟠 подтверди первое число")
        if not state:
            state = t("✅ собирается") if latest is not None else t("⏳ первый сбор ещё не был")
        lines.append(f"{platform.label} — {target} · {state}")
        if platform.id == "instagram":
            rows.append([_button("📸 Instagram", INSTAGRAM)])
        elif platform.id == "linkedin":
            rows.append([_button("💼 LinkedIn", LINKEDIN)])
    lines += ["", await watchdog_line(db, config)]
    rows.append([_button(t("⏱ Сторож"), WATCHDOG)])
    lines += ["", t("Сети включаются в .env и перезапуском бота; токен Instagram, cookie LinkedIn и сторож — кнопками здесь.")]
    rows.append(_home())
    return Screen("\n".join(lines), InlineKeyboardMarkup(rows))


def _local(iso: str | None, tz: ZoneInfo) -> str:
    """«сегодня 08:00» / «21.11 08:00» in the owner's zone; '' when unknown."""
    try:
        at = parse_utc(iso).astimezone(tz) if iso else None
    except ValueError:
        return ""
    if at is None:
        return ""
    if at.date() == utcnow().astimezone(tz).date():
        return t("сегодня {time}").format(time=at.strftime("%H:%M"))
    return at.strftime("%d.%m %H:%M")


async def watchdog_line(db: Database, config: Config) -> str:
    """One line for 🔌 Подключения: whether a watchdog hears from the bot."""
    address = await watchdog.url(db, config)
    if not address:
        return t("{icon} ⏱ Сторож — не подключён: если я остановлюсь, никто не скажет").format(icon=UNAVAILABLE)
    who = esc(watchdog.name(address))
    rec = await watchdog.last(db)
    error = rec.get("error")
    when = _local(rec.get("at"), await get_report_tz(db, config))
    if error:
        icon = monitors.UNCHECKED if error.partition(":")[0] in watchdog.UNCHECKED_REASONS else monitors.WARNING
        return t("{icon} ⏱ Сторож — {who}: {reason}").format(icon=icon, who=who, reason=esc(watchdog.reason(error)))
    if when:
        return t("{icon} ⏱ Сторож — {who}, отметка {when}").format(icon=ON, who=who, when=esc(when))
    return t("{icon} ⏱ Сторож — {who}, первая отметка после ежедневного сбора").format(icon=monitors.PENDING, who=who)


async def watchdog_screen(db: Database, config: Config) -> Screen:
    """⏱ Сторож: who watches the bot itself, and how to connect one from the chat."""
    where = await watchdog.source(db, config)
    lines = [t("<b>⏱ Сторож</b>"), "", await watchdog_line(db, config)]
    if where == "chat":
        lines.append(t("Ссылка задана здесь, в чате; адрес я не показываю — по нему можно отмечаться за меня."))
    elif where == "env":
        lines.append(t("Ссылка — из HEALTHCHECK_URL в .env. Пришли другую — она заменит переменную."))
    lines += [
        "",
        t("Если я остановлюсь — упадёт сервер, кончится место, отзовут токен бота — написать об этом я уже не смогу. "
          "Сторож — сервис, у которого я отмечаюсь после каждого ежедневного сбора; не отметился вовремя — он пишет тебе сам."),
        "",
        t("<b>Как подключить</b> (бесплатно, 2 минуты):"),
        t("1. На healthchecks.io создай check: период — 1 день, grace — 3 часа."),
        t("2. Скопируй его ссылку вида https://hc-ping.com/… и нажми «🔗 Прислать ссылку»."),
        t("3. Я сразу отмечусь пробным пингом и прочитаю ответ: если check не найден, скажу."),
        t("Адрес heartbeat из TofsDevOps тоже подходит — тогда на его главном экране появятся строки по сетям."),
    ]
    rows = [[_button(t("🔗 Прислать ссылку"), WD_URL)]]
    if where:
        rows.append([_button(t("🔄 Проверить снова"), f"{WATCHDOG}:test")])
    if where == "chat":
        rows.append([_button(t("⏏ Отключить"), f"{WATCHDOG}:off")])
    rows.append(_back(CONNECTIONS, t("Подключения")))
    return Screen("\n".join(lines), InlineKeyboardMarkup(rows))


def watchdog_off_confirm() -> Screen:
    """Removing is asked first (BOT_PRINCIPLES §5)."""
    return Screen(
        t("<b>⏏ Отключить сторожа?</b>\n\nЯ перестану отмечаться по ссылке из чата; если задан HEALTHCHECK_URL — "
          "буду отмечаться по нему. Сам check на healthchecks.io поставь на паузу, иначе он напишет, что я пропал."),
        InlineKeyboardMarkup([[_button(t("✅ Да, отключить"), f"{WATCHDOG}:off:yes"), _cancel(WATCHDOG)]]),
    )


# What .env needs for a network that is not connected (shown on 🔌 Подключения).
_ENV_NEEDS = {
    "telegram": "TELEGRAM_CHANNEL_ID",
    "youtube": "YOUTUBE_API_KEY + YOUTUBE_CHANNEL_ID",
    "instagram": "INSTAGRAM_USERNAME",
    "linkedin": "LINKEDIN_PROFILE_URL",
}


def loading() -> Screen:
    return Screen(t("⏳ Собираю свежие данные — это займёт несколько секунд…"))


async def dynamics(db: Database) -> Screen:
    rows = [
        [_button(t("🖼 График за 30 дней"), CHART), _button(t("📋 По дням"), TABLE)],
        _home(),
    ]
    return Screen(_titled(await build_week_report(db)), InlineKeyboardMarkup(rows))


async def channel_screen(db: Database, config: Config) -> Screen:
    """Life of the Telegram channel: joins and leaves, where they came from,
    posts and their reactions — what an admin bot sees without TGStat."""
    target = esc(config.telegram_channel_id or "")
    lines = [t("<b>📣 Канал {channel}</b>").format(channel=target), ""]
    monitor = monitors.BY_ID[channel.MONITOR_ID]
    if not monitor.requires(config):
        lines.append(t("Не подключено — нужно: {needs}.").format(needs=esc(t(monitor.needs))))
        return Screen("\n".join(lines), InlineKeyboardMarkup([_home()]))
    on = await monitors.is_switched_on(db, channel.MONITOR_ID)
    if not on:
        lines.append(t("⬜ Выключено — события не записываются. Включить — кнопкой ниже."))
        lines.append("")
    lines += await channel.overview(db, config, await get_report_tz(db, config))
    lines += [
        "",
        t("Просмотры, пересылки и цитирование Bot API не отдаёт — они в статистике самого Telegram "
          "(в канале: ⋮ → Статистика)."),
    ]
    rows = [
        [_button(f"{_check(on)} {t(monitor.label)}", f"{MONITORS}:{channel.MONITOR_ID}:{CHANNEL}")],
        _home(),
    ]
    return Screen("\n".join(lines), InlineKeyboardMarkup(rows))


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
        return monitors.UNMARKED, t("не заполнено")
    state = t("{points} из {max}").format(points=points, max=hygiene.MAX_SCORE)
    return (monitors.OK if points == hygiene.MAX_SCORE else monitors.WARNING), state


async def security(db: Database, config: Config, top: int = 5) -> Screen:
    """Score, each account's state, what to do first, recent security events."""
    result = await hygiene.overall(db, config)
    if result is None:
        return Screen(
            t("<b>🛡 Безопасность</b>\n\nНет подключённых платформ — подключи хотя бы одну в .env."),
            InlineKeyboardMarkup([_home()]),
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
            lines.append(f"• {day} {esc(security_log.line(e['detail']))}")
    lines += ["", t("Нажми на аккаунт, чтобы отметить пункты. Пароли я не спрашиваю и не храню.")]
    rows.append([_button(t("💬 Комментарии канала"), COMMENTS)])
    rows.append(_home())
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
        lines.append(t("⬜ Выключено — комментарии не проверяются. Включить — кнопкой ниже."))
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
    rows = [
        [_button(f"{_check(on)} {t(monitor.label)}", f"{MONITORS}:{comments.MONITOR_ID}:{COMMENTS}")],
        _back(SECURITY, t("Безопасность")),
    ]
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
        t("📝 Коротко без изменений: {state}").format(state=t("включено") if quiet else t("выключено")),
        t("Когда включено, неделя без изменений — это одна строка вместо отчёта."),
        "",
        t("🔔 Когда писать: {when}").format(when=esc(await _when_summary(db, config))),
        "",
        t("<i>Версия: {build}Python {python}</i>").format(build=build, python=py_platform.python_version()),
    ])
    rows = [
        [_button(t("📅 Дни отчёта"), f"{SETTINGS}:days"), _button(t("🕗 Время отчёта"), f"{SETTINGS}:time")],
        [_button(t("🌍 Часовой пояс"), f"{SETTINGS}:tz")],
        [_button(f"{_check(quiet)} {t('Коротко без изменений')}", f"{SETTINGS}:quiet"), _button(t("🔔 Когда писать"), f"{SETTINGS}:when")],
        [_button(t("🧩 Мониторинги"), MONITORS), _button(t("🔌 Подключения"), CONNECTIONS)],
        [_button(t("📦 Бэкап сейчас"), BACKUP)],
        _home(),
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
        t("Сводка — строка на событие, 🔴 и 🟠 первыми, у каждого время; «ℹ️ N» под ней присылает пункт целиком. "
          "Полные тексты храню {days} дн.").format(days=HELD_KEEP_DAYS),
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
        "{zone} Час — в сетке, минуты — в ряду под ней; любое время — командой, например /settime 08:37"
    ).format(time=clock(hour, minute, tz), zone=zone)
    hours = [_button(_picked(h == hour, f"{h:02d}:00"), f"{SETTINGS}:hour:{h}") for h in range(24)]
    minutes = [_button(_picked(m == minute, f":{m:02d}"), f"{SETTINGS}:minute:{m}") for m in MINUTE_CHOICES]
    rows = _rows(hours, 4) + [minutes, [_button(t("🌍 Часовой пояс"), f"{SETTINGS}:tz")], _back(SETTINGS, t("Настройки"))]
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
    rows = _rows(picks) + [[_button(t("✏️ Другой пояс…"), TZ_OTHER)], _back(SETTINGS, t("Настройки"))]
    return Screen(text, InlineKeyboardMarkup(rows))


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
            t("🟠 Cookie установлен {age} {d} назад и скоро истечёт — пора обновить.").format(age=age, d=_days(age))
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
            "<b>Автосбор</b>: нажми «🔑 Прислать cookie» и пришли значение cookie li_at "
            "(linkedin.com → DevTools → Application → Cookies); то же — командой /setcookie. "
            "Я проверю его и сразу удалю сообщение."
        ),
        t("<i>LinkedIn запрещает автоматический доступ, так что автосбор — на твой риск.</i>"),
    ]
    rows = [
        [_button(t("🔑 Прислать cookie"), LI_COOKIE), _button(t("✏️ Ввести число вручную"), LI_ENTER)],
        _back(CONNECTIONS, t("Подключения")),
    ]
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
        lines.append(t("🟠 Токена нет: без него число не собирается."))
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
            "Потом нажми «🔑 Прислать токен» и пришли его одним сообщением (то же — командой /igtoken) — "
            "я проверю его и сразу удалю сообщение."
        ),
        t("<i>Это официальный API: бот читает только публичные данные своего аккаунта.</i>"),
    ]
    rows = [[_button(t("🔑 Прислать токен"), IG_TOKEN)], _back(CONNECTIONS, t("Подключения"))]
    return Screen("\n".join(lines), InlineKeyboardMarkup(rows))


async def linkedin_prompt(db: Database) -> Screen:
    latest = await db.get_latest("linkedin")
    current = t("\nСейчас: {count}").format(count=_fmt(latest["count"])) if latest else ""
    return Screen(
        t("<b>✏️ LinkedIn вручную</b>\n\nПришли число подписчиков одним сообщением, например 4520.{current}").format(
            current=current
        ),
        InlineKeyboardMarkup([[_cancel(LI_CANCEL)]]),
    )


# The text-input conversations (bot/handlers.py): what is asked for, by kind.
INPUT_PROMPTS = {
    "cookie": (
        "🔑 Пришли значение cookie li_at одним сообщением "
        "(linkedin.com → DevTools → Application → Cookies → li_at → Value). "
        "Я проверю его и сразу удалю сообщение."
    ),
    "token": (
        "🔑 Пришли токен Instagram одним сообщением "
        "(developers.facebook.com → приложение → API setup with Unified login → Generate token). "
        "Я проверю его и сразу удалю сообщение."
    ),
    "tz": "🌍 Пришли название часового пояса из базы IANA одним сообщением, например Asia/Kolkata или America/Chicago.",
    "watchdog": (
        "🔗 Пришли ссылку сторожа одним сообщением: https://hc-ping.com/… из healthchecks.io или адрес heartbeat "
        "из TofsDevOps. Я отмечусь по ней пробным пингом и сразу удалю сообщение."
    ),
}


def input_prompt(kind: str) -> Screen:
    """«Send it in one message» with a cancel button; the answer is the next message."""
    return Screen(esc(t(INPUT_PROMPTS[kind])), InlineKeyboardMarkup([[_cancel(INPUT_CANCEL)]]))


def input_retry(note: str) -> Screen:
    """A step's value was not taken: why, and the way out; the step stays open."""
    return Screen(esc(note), InlineKeyboardMarkup([[_cancel(INPUT_CANCEL)]]))


def input_retry_tz() -> Screen:
    return Screen(
        t("Не знаю такой часовой пояс. Нужно название из базы IANA, например Europe/Moscow, или нажми «✖️ Отмена»."),
        InlineKeyboardMarkup([[_cancel(INPUT_CANCEL)]]),
    )


def restore_prompt() -> InlineKeyboardMarkup:
    """Under a .db file sent without a caption: restore, or not."""
    return InlineKeyboardMarkup([[
        _button(t("✅ Восстановить"), f"{RESTORE}:yes"), _cancel(f"{RESTORE}:no"),
    ]])


def linkedin_retry() -> Screen:
    return Screen(
        t("Это не похоже на число. Пришли только цифры, например 4520, или нажми «✖️ Отмена»."),
        InlineKeyboardMarkup([[_cancel(LI_CANCEL)]]),
    )


def linkedin_confirm(prev: int, count: int) -> Screen:
    """A number far from the last one is likely a typo: ask before it becomes the baseline."""
    return Screen(
        t(
            "<b>✏️ Проверь число</b>\n\n{count} сильно отличается от прошлого значения "
            "{prev}. Возможно, это опечатка."
        ).format(count=_fmt(count), prev=_fmt(prev)),
        InlineKeyboardMarkup([
            [_button(t("Сохранить {count}").format(count=_fmt(count)), f"{LINKEDIN}:save:{count}")],
            [_button(t("✏️ Ввести заново"), LI_ENTER)],
            [_cancel(HOME)],
        ]),
    )


# ---------------------------------------------------------------------------
# «📖 Что я умею» and «❓ Значки»
# ---------------------------------------------------------------------------

# What is 🔴 for this bot (BOT_PRINCIPLES §1 leaves it to each bot): the
# legend says it in as many words, the README too.
CRITICAL_HERE = (
    "🔴 у меня — это: похоже на взлом (новый админ или владелец, ссылка в описании, пропавшие видео "
    "или публикации, новый вход, смена пароля, почты или 2FA), профиль не читается, почтовый воркер "
    "молчит, комментарий, за который блокируют группу. 🟠 — истёкший cookie, отклонённый токен, сбои "
    "сбора, падение подписчиков, смена названия или аватарки."
)


def icon_legend() -> list[str]:
    """The icon dictionary as lines: icon — what it means — what I do with it."""
    lines = []
    for icon, meaning, does in monitors.ICON_LEGEND:
        line = f"{icon} {t(meaning)}"
        if does:
            line += f" — {t(does)}"
        lines.append(esc(line))
    return [*lines, "", esc(t(CRITICAL_HERE))]


# Every command, as «📖 Что я умею» lists them: shortcuts to what the buttons do.
COMMAND_LINES = (
    "/start, /stats — главная",
    "/now — обновить данные",
    "/week — динамика за неделю и график",
    "/history [платформа] [дни] — таблица по дням, до 90 дней",
    "/channel — жизнь канала: подписки и отписки, откуда пришли, посты и реакции",
    "/security — безопасность аккаунтов",
    "/comments — комментарии канала: что проверено и насколько точно",
    "/connections — подключения: что собирается само, чему нужен токен или cookie",
    "/settings — настройки",
    "/modules — мониторинги",
    "/settime ЧЧ:ММ — время отчёта",
    "/setday <дни> — дни отчёта: sat, mon-fri, mon,thu, daily",
    "/settz <пояс> — часовой пояс, например Europe/Moscow",
    "/setquiet on|off — одна строка вместо отчёта, если за неделю без изменений",
    "/mute <время> — помолчать: 1h, 8h, 1d (по умолчанию 8h); /unmute — снять",
    "/linkedin <число> — ввести LinkedIn вручную",
    "/setcookie [li_at] — cookie LinkedIn для автосбора; без значения — спрошу его следующим сообщением",
    "/cookieage — сколько живёт cookie LinkedIn",
    "/igtoken [токен] — токен Instagram для автосбора; без значения — спрошу его следующим сообщением",
    "/restore — вернуть историю из бэкапа: ответом на файл или подписью к нему",
    "/cancel — выйти из шага ввода",
    "/icons — значки: что значат и что звонит",
    "/help — этот экран",
)


def about_screen() -> Screen:
    """«📖 Что я умею» (a button under the input field, and /help): what the
    bot does by itself, where everything is, and every command."""
    text = "\n".join([
        t("<b>📖 Что я умею</b>"),
        "",
        t(
            "Пока всё в порядке — молчу; о проблеме пишу сразу, а сводку присылаю по расписанию. "
            "Сети подключаются в .env, остальное — кнопками."
        ),
        "",
        t("<b>Подписчики</b>"),
        t("• Каждый день собираю подписчиков Telegram, YouTube, Instagram и LinkedIn — тех сетей, что подключены."),
        t("• Отчёт по расписанию: за день, неделю и месяц, график за 30 дней, лидер недели, прогноз до круглого "
          "числа; 1-го числа — итоги месяца."),
        t("• Сразу пишу о падении подписчиков, наплыве ботов, круглом числе и о том, что сбор не работает."),
        t("• 📣 Канал — подписки и отписки, откуда пришли, посты и реакции."),
        "",
        t("<b>Безопасность</b>"),
        t("• Каждые 30 минут сверяю профиль: название, описание и ссылки, аватарку, админов и владельца, "
          "число видео и публикаций."),
        t("• Письма безопасности, если подключён почтовый воркер: новый вход, смена пароля, почты или 2FA, код входа."),
        t("• Комментарии канала, если есть ключ Claude: карточка с кнопками на то, за что блокируют группу. "
          "Сам ничего не удаляю."),
        t("• Чек-лист 2FA и паролей — балл в отчёте. Пароли не спрашиваю и не храню."),
        "",
        t("<b>Сам за собой</b>"),
        t("• По воскресеньям присылаю бэкап базы (и по кнопке «📦 Бэкап сейчас» в настройках). Пришли файл "
          "обратно — верну историю, уже собранное не перезапишется."),
        t("• После обновления пишу «🔄 Бот обновился», по воскресеньям — об уязвимостях в своих пакетах."),
        "",
        t("<b>Где что</b>"),
        t("🏠 Главная — отчёт, «🔄 Обновить данные», 📈 Динамика, 🛡 Безопасность, 📣 Канал, 🔌 Подключения, "
          "«🔕 Помолчать…», ⚙️ Настройки."),
        t("❓ Значки — что значат значки и что звонит. Под тревогами — кнопки туда, где разбираться."),
        "",
        t("<b>Команды</b> — короткие пути к тому же, что на кнопках:"),
        *(esc(t(line)) for line in COMMAND_LINES),
    ])
    return Screen(text, InlineKeyboardMarkup([_home()]))


def icons_screen() -> Screen:
    """«❓ Значки» (a button under the input field): the icon dictionary
    (BOT_PRINCIPLES §1) and what rings."""
    text = "\n".join([
        t("<b>❓ Значки</b>"),
        "",
        t("Значок говорит, насколько срочно; слова — что случилось. Значки одни на тревогах, экранах и в отчётах."),
        "",
        *icon_legend(),
        "",
        t("<b>Что звонит</b>"),
        t(
            "Звонит только 🔴 — даже ночью, в тихие часы и в «🔕 Помолчать». Остальное приходит без звука, "
            "а в тихие часы и в тишине ждёт и приходит одной сводкой. Отчёт по расписанию — тоже без звука."
        ),
        t("Помолчать — «🔕 Помолчать…» на главной или /mute 8h; тихие часы — ⚙️ Настройки → 🔔 Когда писать. "
          "«⚙️ Не присылать такие» под тревогой выключает такие уведомления."),
    ])
    return Screen(text, InlineKeyboardMarkup([_home()]))

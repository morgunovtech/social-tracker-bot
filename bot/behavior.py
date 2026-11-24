"""An update that changed how the bot behaves says so once (BOT_PRINCIPLES §6).

On every start the bot writes down what it actually does — when the report
comes and in which zone, the quiet hours, which checks are on, which
security mails ring and the thresholds of its alerts — next to what the
owner set for it: the chat settings and the .env values it is computed
from. On the next start it compares. A value that moved while everything
the owner set stayed the same was moved by the new version, and the owner
hears once, with a button to the setting; a change the owner made, in the
chat or in .env, is theirs and is not told back.

The first case is 1.5.0 (#52): the zone of the schedule started following
the chat language, and REPORT_HOUR_UTC=4 silently went from 04:00 UTC to
04:00 Moscow. That happened before there was anything to compare with, so a
bot that has run before and still keeps its schedule in the language's zone
— no TIMEZONE, no REPORT_TZ, no zone picked in the chat — hears it once,
with the first snapshot.

What is stored is the values and the inputs, never a secret: a monitor's
«configured» is a yes or no, not the key behind it.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Bot

from bot import callbacks, monitors, notifier
from bot.config import DEFAULT_TZ, Config
from bot.db import Database, utcnow
from bot.i18n import t
from bot.monitors import collection, comments, followers, mail, profile
from bot.notifier import Priority
from bot.scheduler import get_report_schedule, get_report_tz, is_quiet_mode

logger = logging.getLogger(__name__)

SNAPSHOT_KEY = "behavior_snapshot"
# The .env values the schedule is computed from: the owner's, read as they are written.
SCHEDULE_ENV = ("REPORT_HOUR", "REPORT_HOUR_UTC", "REPORT_MINUTE", "REPORT_DOW", "TIMEZONE", "REPORT_TZ", "BOT_LANG")
SCHEDULE_CHAT = ("report_dow", "report_time", "report_tz")
# The version that made the zone follow the language.
ZONE_BY_LANGUAGE = "1.5.0"


@dataclass(frozen=True)
class Threshold:
    key: str
    monitor: str     # told only while this monitor is on
    label: str       # Russian, translated where shown
    value: Callable[[], object]


THRESHOLDS: tuple[Threshold, ...] = (
    Threshold("follower_drop", "followers", "падение подписчиков — тревога от стольких за сутки",
              lambda: followers.DROP_ALERT_MIN_ABS),
    Threshold("follower_drop_pct", "followers", "падение подписчиков — и от такой доли, %",
              lambda: followers.DROP_ALERT_MIN_PCT),
    Threshold("collection_streak", "collection", "сбор не удаётся — тревога на такой день подряд",
              lambda: collection.ALERT_STREAK),
    Threshold("profile_unreachable", "profile", "профиль не читается — тревога после стольких проверок подряд",
              lambda: profile.UNREACHABLE_AFTER),
    Threshold("mail_silent", "mail", "почтовый воркер молчит — тревога после стольких опросов подряд",
              lambda: mail.UNREACHABLE_AFTER),
    Threshold("comments_critical", "comments", "опасный комментарий звонит при уверенности от, %",
              lambda: comments.CRITICAL_CONFIDENCE),
)


@dataclass
class Pending:
    """What detect() found: the lines to tell, the screens their buttons open,
    and the snapshot to keep once they are told."""

    lines: list[str] = field(default_factory=list)
    screens: list[str] = field(default_factory=list)
    snapshot: str = ""

    def add(self, line: str, *screens: str) -> None:
        self.lines.append(line)
        self.screens += [s for s in screens if s not in self.screens]


def _env(names: tuple[str, ...]) -> dict[str, str]:
    return {name: (os.getenv(name) or "").strip() for name in names}


async def current(db: Database, config: Config) -> dict[str, dict]:
    """What the bot does now, item by item, each with the inputs the owner set."""
    dow, hour, minute = await get_report_schedule(db, config)
    tz = await get_report_tz(db, config)
    items: dict[str, dict] = {
        "schedule": {
            "value": {"dow": dow, "time": f"{hour:02d}:{minute:02d}", "tz": tz.key},
            "inputs": {"env": _env(SCHEDULE_ENV), "chat": {k: await db.get_setting(k) for k in SCHEDULE_CHAT}},
        },
        "quiet_hours": {
            "value": "{}-{}".format(*hours) if (hours := await notifier.quiet_hours(db)) else None,
            "inputs": {"chat": await db.get_setting(notifier.QUIET_HOURS_KEY)},
        },
        "short_week": {
            "value": await is_quiet_mode(db, config),
            "inputs": {"env": _env(("QUIET_IF_NO_CHANGE",)), "chat": await db.get_setting("quiet_if_no_change")},
        },
    }
    for m in monitors.MONITORS:
        items[f"monitor:{m.id}"] = {
            "value": await monitors.is_on(db, config, m.id),
            "inputs": {"chat": await db.get_setting(monitors.switch_key(m.id)), "configured": m.requires(config),
                       "connected": await monitors.is_connected(db, m.id)},
        }
    for kind in mail.KINDS:
        items[f"mail:{kind.id}"] = {"value": kind.level, "inputs": {}}
    for threshold in THRESHOLDS:
        items[f"threshold:{threshold.key}"] = {"value": threshold.value(), "inputs": {}}
    return items


def _schedule_text(value: dict) -> str:
    """«по субботам, 04:00 по поясу Москва (UTC+3)» — in the zone it names."""
    from bot import ui  # the screens import the scheduler; read at call time

    tz = ZoneInfo(value["tz"])
    hour, minute = (int(part) for part in value["time"].split(":"))
    return t("{days}, {time} по поясу {zone}").format(
        days=ui.dow_pretty(value["dow"]), time=f"{hour:02d}:{minute:02d}", zone=ui.tz_name(tz)
    )


def _level(level: str) -> str:
    return t("🔴 звонит") if level == "critical" else t("🟠 без звука")


def _on(on: bool) -> str:
    return t("включена") if on else t("выключена")


def _kind_title(kind_id: str) -> str:
    kind = next((k for k in mail.KINDS if k.id == kind_id), None)
    return t(kind.title) if kind else kind_id


def _monitor_label(monitor_id: str) -> str:
    m = monitors.BY_ID.get(monitor_id)
    return t(m.label) if m else monitor_id


def _changes(previous: dict[str, dict], now: dict[str, dict], pending: Pending) -> None:
    """The items the update moved: the value changed while the owner's inputs did not."""
    on = {key.split(":", 1)[1]: item["value"] for key, item in now.items() if key.startswith("monitor:")}
    for key, item in now.items():
        kind, _, name = key.partition(":")
        before = previous.get(key)
        if before is None:
            # New in this version: a check that starts working, a mail it starts telling apart.
            if kind == "monitor" and item["value"]:
                m = monitors.BY_ID[name]
                pending.add(t("• Новая проверка включена: {label} — {what}").format(
                    label=t(m.label), what=t(m.description)), callbacks.MONITORS)
            elif kind == "mail" and on.get("mail"):
                pending.add(t("• Письма «{title}» теперь распознаю: {level}").format(
                    title=_kind_title(name), level=_level(item["value"])))
            continue
        if before.get("inputs") != item["inputs"] or before.get("value") == item["value"]:
            continue    # the owner changed it, or nothing moved
        if key == "schedule":
            pending.add(t("• Отчёт: {now} — было {before}").format(
                now=_schedule_text(item["value"]), before=_schedule_text(before["value"])),
                callbacks.OPEN_TZ, callbacks.OPEN_TIME)
        elif key == "quiet_hours":
            pending.add(t("• Тихие часы: {now} — было {before}").format(
                now=item["value"] or t("выключены"), before=before["value"] or t("выключены")), callbacks.OPEN_WHEN)
        elif key == "short_week":
            pending.add(t("• «Коротко без изменений»: {now} — было {before}").format(
                now=t("включено") if item["value"] else t("выключено"),
                before=t("включено") if before["value"] else t("выключено")), callbacks.SETTINGS)
        elif kind == "monitor":
            pending.add(t("• Проверка «{label}»: {now} — была {before}").format(
                label=_monitor_label(name), now=_on(item["value"]), before=_on(before["value"])), callbacks.MONITORS)
        elif kind == "mail" and on.get("mail"):
            pending.add(t("• Письма «{title}»: {now} — было {before}").format(
                title=_kind_title(name), now=_level(item["value"]), before=_level(before["value"])))
        elif kind == "threshold":
            threshold = next(th for th in THRESHOLDS if th.key == name)
            if on.get(threshold.monitor):
                pending.add(t("• {label}: {now} — было {before}").format(
                    label=t(threshold.label), now=item["value"], before=before["value"]))


async def _zone_by_language(db: Database, config: Config, now: dict[str, dict], at: datetime | None = None) -> str:
    """1.5.0's move, told once to a bot that ran before it was comparable:
    the schedule is in the language's zone only because nothing chose one."""
    schedule = now["schedule"]
    env, chat = schedule["inputs"]["env"], schedule["inputs"]["chat"]
    zone = schedule["value"]["tz"]
    # Chosen somewhere — in .env or in the chat — or UTC anyway: nothing moved.
    if env["TIMEZONE"] or env["REPORT_TZ"] or any(chat.values()) or zone == "UTC" or zone != DEFAULT_TZ[config.lang]:
        return ""
    hour, minute = (int(part) for part in schedule["value"]["time"].split(":"))
    today = (at or utcnow()).date()
    then = datetime(today.year, today.month, today.day, hour, minute, tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo(zone))
    return t(
        "• Отчёт: {now}. До версии {version} это же время считалось по UTC — {then} по этому поясу: "
        "с {version} пояс, пока его не выбрали, следует языку бота. Я не знаю, где ты, — выбери свой пояс, "
        "отчёт останется в тот же момент, а время поправишь кнопкой «🕗 Время отчёта»."
    ).format(now=_schedule_text(schedule["value"]), version=ZONE_BY_LANGUAGE, then=then.strftime("%H:%M"))


async def detect(db: Database, config: Config, ran_before: bool) -> Pending:
    """Compare with the last start. ran_before — the bot has started before
    (its «🔄 Бот обновился» snapshot exists), read before that snapshot is
    written."""
    now = await current(db, config)
    pending = Pending(snapshot=json.dumps({"items": now}, ensure_ascii=False))
    raw = await db.get_setting(SNAPSHOT_KEY)
    try:
        previous = json.loads(raw)["items"] if raw else None
    except (ValueError, KeyError, TypeError):
        previous = None
    if previous is None:
        if ran_before:
            line = await _zone_by_language(db, config, now)
            if line:
                pending.add(line, callbacks.OPEN_TZ, callbacks.OPEN_TIME)
        return pending
    _changes(previous, now, pending)
    return pending


async def announce(bot: Bot, config: Config, db: Database, pending: Pending) -> bool:
    """One message for everything the update moved; the snapshot is kept only
    once it went out (or there was nothing to say), so a send that failed is
    told at the next start. True when a message was sent."""
    if pending.lines:
        text = "\n".join([
            t("ℹ️ После обновления я работаю иначе — это поменяла новая версия, а не ты:"),
            *pending.lines,
            t("Если так не нужно — поменяй кнопкой ниже."),
        ])
        if not await notifier.send(bot, config, db, text, Priority.NORMAL, actions=pending.screens):
            return False
    await db.set_setting(SNAPSHOT_KEY, pending.snapshot)
    return bool(pending.lines)

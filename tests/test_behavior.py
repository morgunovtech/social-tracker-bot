"""An update that changed how the bot behaves says so once (bot/behavior.py)."""

from __future__ import annotations

import dataclasses
import json

from conftest import buttons

from bot import behavior, callbacks, monitors, notifier
from bot.behavior import SNAPSHOT_KEY, announce, detect
from bot.monitors import mail, profile


async def _start(bot, config, db, ran_before: bool = True) -> list[str]:
    """One start of the bot: detect, then tell; the messages it sent."""
    before = len(bot.messages)
    await announce(bot, config, db, await detect(db, config, ran_before))
    return bot.messages[before:]


async def _moved(db, key: str, **changes) -> None:
    """Pretend the last start saw something else for this item."""
    snapshot = json.loads(await db.get_setting(SNAPSHOT_KEY))
    snapshot["items"][key].update(changes)
    await db.set_setting(SNAPSHOT_KEY, json.dumps(snapshot))


async def test_first_start_only_takes_the_snapshot(bot, config, db):
    assert await _start(bot, config, db, ran_before=False) == []
    assert await _start(bot, config, db) == []            # nothing moved
    snapshot = json.loads(await db.get_setting(SNAPSHOT_KEY))["items"]
    assert snapshot["schedule"]["value"] == {"dow": "sat", "time": "08:00", "tz": "UTC"}
    assert snapshot["monitor:followers"] == {"value": True, "inputs": {"chat": None, "configured": True, "connected": True}}


async def test_an_update_that_moved_the_schedule_says_so_once(bot, config, db):
    await _start(bot, config, db, ran_before=False)
    # The last start saw 08:00 UTC; this one, with the same .env, reads it in Moscow.
    await _moved(db, "schedule", value={"dow": "sat", "time": "08:00", "tz": "Europe/Moscow"})
    (text,) = await _start(bot, config, db)
    assert text.startswith("ℹ️ После обновления я работаю иначе")
    assert "• Отчёт: по субботам, 08:00 по поясу UTC — было по субботам, 08:00 по поясу Москва (UTC+3)" in text
    assert buttons(bot.markups[-1]) == {
        "open:rtz": "🌍 Часовой пояс", "open:rtime": "🕗 Время отчёта", "mute:8h": "🔕 Тихо 8 ч",
    }
    assert await _start(bot, config, db) == []            # once


async def test_a_change_the_owner_made_is_not_told_back(bot, config, db):
    await _start(bot, config, db, ran_before=False)
    # In the chat: the time is the owner's now.
    await db.set_setting("report_time", "09:30")
    assert await _start(bot, config, db) == []
    # In .env: the same, even though the value moved.
    await _moved(db, "schedule", inputs={"env": {"REPORT_HOUR": "6"}, "chat": {}})
    assert await _start(bot, config, db) == []
    # A switched-off monitor and quiet hours set in the chat.
    await monitors.set_switch(db, "followers", False)
    await notifier.set_quiet_hours(db, "23-8")
    assert await _start(bot, config, db) == []


async def test_new_checks_and_new_levels(bot, config, db):
    mail_on = dataclasses.replace(config, security_mail_url="https://mail.example", security_mail_token="x")
    await _start(bot, mail_on, db, ran_before=False)
    snapshot = json.loads(await db.get_setting(SNAPSHOT_KEY))
    del snapshot["items"]["monitor:hygiene"]                 # «new in this version»
    del snapshot["items"]["mail:login_code"]
    snapshot["items"]["mail:new_login"]["value"] = "warning"  # rang quietly before
    snapshot["items"]["threshold:profile_unreachable"]["value"] = profile.UNREACHABLE_AFTER - 1
    await db.set_setting(SNAPSHOT_KEY, json.dumps(snapshot))
    (text,) = await _start(bot, mail_on, db)
    assert "• Новая проверка включена: Чек-лист безопасности — 2FA и пароли" in text
    assert "• Письма «пришёл код входа» теперь распознаю: 🟠 без звука" in text
    assert "• Письма «новый вход в аккаунт»: 🔴 звонит — было 🟠 без звука" in text
    assert f"профиль не читается — тревога после стольких проверок подряд: {profile.UNREACHABLE_AFTER} — было" in text
    assert "open:mod" in buttons(bot.markups[-1])


async def test_levels_of_a_monitor_that_is_off_are_not_news(bot, config, db):
    # No mail worker configured: what its mails would do is nobody's concern.
    await _start(bot, config, db, ran_before=False)
    await _moved(db, "mail:new_login", value="warning")
    assert await _start(bot, config, db) == []


async def test_zone_by_language_is_told_once_to_a_bot_that_ran_before(bot, config, db, monkeypatch):
    # Production on 2026-11-24: REPORT_HOUR_UTC=4, BOT_LANG=ru, no zone anywhere.
    for name, value in {"REPORT_HOUR_UTC": "4", "REPORT_HOUR": "", "REPORT_TZ": "", "TIMEZONE": ""}.items():
        monkeypatch.setenv(name, value)
    ru = dataclasses.replace(config, report_hour=4, report_tz="Europe/Moscow", lang="ru")
    (text,) = await _start(bot, ru, db)
    assert "• Отчёт: по субботам, 04:00 по поясу Москва (UTC+3). До версии 1.5.0 это же время считалось по UTC — " \
           "07:00 по этому поясу" in text
    assert {"open:rtz", "open:rtime"} <= set(buttons(bot.markups[-1]))
    assert await _start(bot, ru, db) == []


async def test_zone_by_language_is_not_told_when_a_zone_was_chosen(bot, config, db, monkeypatch):
    monkeypatch.setenv("REPORT_TZ", "")
    ru = dataclasses.replace(config, report_tz="Europe/Moscow", lang="ru")
    assert await _start(bot, ru, db, ran_before=False) == []          # a fresh install: there was no «before»
    await db.set_setting(SNAPSHOT_KEY, "")
    await db.set_setting("report_tz", "Asia/Tashkent")                # picked in the chat
    assert await _start(bot, ru, db) == []
    await db.set_setting(SNAPSHOT_KEY, "")
    await db.set_setting("report_tz", "")
    monkeypatch.setenv("TIMEZONE", "Europe/Moscow")                    # set in .env
    assert await _start(bot, ru, db) == []


async def test_nothing_is_kept_until_the_owner_hears_it(bot, config, db):
    await _start(bot, config, db, ran_before=False)
    await _moved(db, "quiet_hours", value="23-8")
    nobody = dataclasses.replace(config, admin_chat_id=None)          # before the first /start
    assert await _start(bot, nobody, db) == []
    (text,) = await _start(bot, config, db)
    assert "• Тихие часы: выключены — было 23-8" in text
    assert "open:when" in buttons(bot.markups[-1])


async def test_the_buttons_open_their_screens(make_update, make_context, bot, config, db):
    from bot import handlers

    for screen, title in ((callbacks.OPEN_TZ, "🌍 Часовой пояс"), (callbacks.OPEN_TIME, "🕗 Время отчёта"),
                          (callbacks.OPEN_WHEN, "🔔 Когда писать"), (callbacks.MONITORS, "🧩 Мониторинги"),
                          (callbacks.SETTINGS, "⚙️ Настройки")):
        update = make_update(callback=f"{callbacks.OPEN}:{screen}")
        await handlers.on_callback(update, make_context())
        assert title in bot.messages[-1]


def test_every_threshold_names_a_monitor():
    assert {th.monitor for th in behavior.THRESHOLDS} <= set(monitors.BY_ID)
    assert all(kind.level in ("critical", "warning") for kind in mail.KINDS)

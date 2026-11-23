"""English for bot/handlers, bot/main, bot/scheduler and bot/db (see bot/i18n.py)."""

from __future__ import annotations

STRINGS: dict[str, str] = {
    # bot/handlers.py
    "⛔ Доступ запрещён.": "⛔ Access denied.",
    "⚠️ Что-то пошло не так ({error}). Попробуй ещё раз; подробности — в логах бота.":
        "⚠️ Something went wrong ({error}). Try again; the details are in the bot's logs.",
    "⚠️ Собрать данные не получилось — подробности в логах. Ниже последние сохранённые.":
        "⚠️ Could not collect the data — the details are in the logs. Below is the last saved data.",
    "✅ Часовой пояс: {tz}": "✅ Time zone: {tz}",
    "✅ Часовой пояс: {tz}. Отчёт придёт в тот же момент, что и раньше, — ниже его время по этому поясу":
        "✅ Time zone: {tz}. The report will arrive at the same moment as before — its time in this zone is below",
    "✅ LinkedIn: {count} — сохранено": "✅ LinkedIn: {count} — saved",
    "Это личный бот: он отвечает только своему владельцу.": "This is a personal bot: it answers only its owner.",
    "⏳ Уже собираю данные — результат появится в сообщении выше.":
        "⏳ Already collecting — the result will appear in the message above.",
    "Пришли число вместе с командой, например: /linkedin 4520":
        "Send the number with the command, for example: /linkedin 4520",
    "Нужно целое число без знака, например: /linkedin 4520":
        "It must be a whole number without a sign, for example: /linkedin 4520",
    "Формат: /history [платформа] [дни], например: /history telegram 30":
        "Format: /history [platform] [days], for example: /history telegram 30",
    "Неизвестная платформа. Доступны: all, {platforms}": "Unknown platform. Available: all, {platforms}",
    "Количество дней должно быть числом, например: /history all 30":
        "The number of days must be a number, for example: /history all 30",
    "Количество дней — от 1 до {max}.": "The number of days must be from 1 to {max}.",
    "Неверный формат. Нужно ЧЧ:ММ, например: /settime 08:00":
        "Wrong format. It must be HH:MM, for example: /settime 08:00",
    "✅ Отчёт теперь в {time}": "✅ The report now comes at {time}",
    "❌ Не понял дни: «{days}».\nПримеры: /setday sat, /setday mon,thu, /setday mon-fri, /setday daily":
        "❌ Could not read the days: \"{days}\".\n"
        "Examples: /setday sat, /setday mon,thu, /setday mon-fri, /setday daily",
    "✅ Отчёт: {days}": "✅ Report: {days}",
    "❌ Не знаю такой часовой пояс: «{tz}».\n"
    "Нужно название из базы IANA, например /settz Europe/Moscow или /settz Asia/Almaty. "
    "Частые пояса — кнопками: /settz без названия.":
        "❌ Unknown time zone: \"{tz}\".\n"
        "It must be an IANA name, for example /settz Europe/Moscow or /settz Asia/Almaty. "
        "Common zones are a button away: /settz without a name.",
    "✅ Тихий режим включён": "✅ Quiet mode on",
    "✅ Тихий режим выключен": "✅ Quiet mode off",
    "Пришли cookie вместе с командой: /setcookie <значение li_at>\n\n"
    "Где взять: linkedin.com → DevTools → Application → Cookies → li_at → Value. "
    "Сообщение с cookie я сразу удалю.":
        "Send the cookie with the command: /setcookie <li_at value>\n\n"
        "Where to find it: linkedin.com → DevTools → Application → Cookies → li_at → Value. "
        "I will delete the message with the cookie right away.",
    "⚠️ Удалить сообщение с cookie не получилось — удали его из чата вручную.":
        "⚠️ Could not delete the message with the cookie — delete it from the chat yourself.",
    "❌ Это не похоже на cookie: значение слишком короткое.":
        "❌ This does not look like a cookie: the value is too short.",
    "❌ Не задан LINKEDIN_PROFILE_URL — не на чем проверить cookie.":
        "❌ LINKEDIN_PROFILE_URL is not set — there is nothing to check the cookie against.",
    "⏳ Проверяю cookie…": "⏳ Checking the cookie…",
    "LinkedIn отклонил cookie": "LinkedIn rejected the cookie",
    "не удалось получить число подписчиков (подробности в логах)":
        "could not get the follower count (details in the logs)",
    "❌ Cookie не сохранён: {reason}.\nПроверь, что значение скопировано целиком, без лишних символов.":
        "❌ Cookie not saved: {reason}.\nCheck that the value is copied whole, with no extra characters.",
    "Проверка прошла: {count} подписчиков.": "Check passed: {count} followers.",
    "Проверка вернула {count} — слишком далеко от прошлого {prev}, число не записано. "
    "Если оно верное, введи его: /linkedin {raw}":
        "The check returned {count} — too far from the previous {prev}, the number was not recorded. "
        "If it is right, enter it: /linkedin {raw}",
    "✅ Cookie сохранён. {fetched}": "✅ Cookie saved. {fetched}",
    "Пришли токен вместе с командой: /igtoken <токен>\n\n"
    "Где взять: developers.facebook.com → твоё приложение → Instagram API → "
    "«API setup with Unified login» → Generate token. Сообщение с токеном я сразу удалю.":
        "Send the token with the command: /igtoken <token>\n\n"
        "Where to find it: developers.facebook.com → your app → Instagram API → "
        "\"API setup with Unified login\" → Generate token. I will delete the message with the token right away.",
    "⚠️ Удалить сообщение с токеном не получилось — удали его из чата вручную.":
        "⚠️ Could not delete the message with the token — delete it from the chat yourself.",
    "❌ Это не похоже на токен: значение слишком короткое.":
        "❌ This does not look like a token: the value is too short.",
    "❌ Не задан INSTAGRAM_USERNAME — Instagram не подключён.":
        "❌ INSTAGRAM_USERNAME is not set — Instagram is not connected.",
    "⏳ Проверяю токен…": "⏳ Checking the token…",
    "Instagram отклонил токен": "Instagram rejected the token",
    "не удалось связаться с Instagram (подробности в логах)": "could not reach Instagram (details in the logs)",
    "токен выдан не для @{username} — проверь INSTAGRAM_USERNAME и какой аккаунт добавлен в приложение Meta":
        "the token was not issued for @{username} — check INSTAGRAM_USERNAME "
        "and which account is added to the Meta app",
    "Instagram не ответил (подробности в логах)": "Instagram did not answer (details in the logs)",
    "❌ Токен не сохранён: {reason}.\nПроверь, что значение скопировано целиком, без лишних символов.":
        "❌ Token not saved: {reason}.\nCheck that the value is copied whole, with no extra characters.",
    "Проверка прошла: @{username}, {count} подписчиков.": "Check passed: @{username}, {count} followers.",
    "Проверка прошла: @{username}, но число подписчиков API не вернул.":
        "Check passed: @{username}, but the API did not return the follower count.",
    "✅ Токен сохранён. {fetched}": "✅ Token saved. {fetched}",
    "Чтобы вернуть историю, ответь командой /restore на сообщение с бэкапом "
    "(«📦 Еженедельный бэкап базы») или пришли файл .db с подписью /restore.\n\n"
    "Данные из бэкапа добавятся к текущим: уже собранное не перезапишется.":
        "To bring the history back, reply /restore to the backup message "
        "(\"📦 Weekly database backup\") or send the .db file with the caption /restore.\n\n"
        "The backup is merged into the current data: nothing already collected is overwritten.",
    "❌ Файл больше 20 МБ — Telegram не даст боту его скачать.":
        "❌ The file is over 20 MB — Telegram will not let the bot download it.",
    "⏳ Восстанавливаю…": "⏳ Restoring…",
    "❌ Не похоже на бэкап этого бота: {error}.": "❌ This does not look like a backup of this bot: {error}.",
    "пусто": "empty",
    "✅ Восстановлено, добавлено записей: {added}. Всего: {total} ({period}).":
        "✅ Restored, records added: {added}. Total: {total} ({period}).",
    "Такой команды нет. Все команды — в /help.": "No such command. All commands are in /help.",
    "Не понимаю это сообщение. Главная — кнопка «{button}» внизу, все команды — /help.":
        "I do not understand this message. The \"{button}\" button below opens the home screen, "
        "all commands are in /help.",
    "Уже собираю данные — подожди несколько секунд": "Already collecting — give it a few seconds",
    "Для графика пока мало данных: нужно хотя бы два дня": "Not enough data for a chart yet: it needs at least two days",
    "График — ниже": "The chart is below",
    "Сохранено": "Saved",
    "Тихий режим включён": "Quiet mode on",
    "Тихий режим выключен": "Quiet mode off",
    "Нужен хотя бы один день": "At least one day is needed",
    "Отчёт будет приходить в {time}": "The report will come at {time}",
    "включено": "on",
    "выключено": "off",
    "Это меню устарело — вот актуальное": "That menu is outdated — here is the current one",
    "Отменено": "Cancelled",
    "Отменено.": "Cancelled.",
    # /mute and /unmute
    "Максимум — 7 дней: дольше тишина уже не пауза, а выключенный мониторинг.":
        "Seven days at most: a longer silence is not a pause but monitoring switched off.",
    "Использование: /mute <время>\nПримеры: /mute 1h, /mute 8h, /mute 30m, /mute 1d\nПо умолчанию: 8h":
        "Usage: /mute <time>\nExamples: /mute 1h, /mute 8h, /mute 30m, /mute 1d\nDefault: 8h",
    "🔔 Снова пишу обо всём.": "🔔 Writing about everything again.",
    # bot/main.py: the / menu
    "Главная: подписчики и статус": "Home: followers and status",
    "Обновить данные": "Refresh the data",
    "Динамика за неделю": "This week's dynamics",
    "Безопасность аккаунтов": "Account security",
    "Настройки": "Settings",
    "Помощь и все команды": "Help and all commands",
    # bot/scheduler.py
    "📉 Подписчики за 30 дней": "📉 Followers over 30 days",
    "📦 Еженедельный бэкап базы. Чтобы вернуть из него историю, ответь на это сообщение "
    "командой /restore. LinkedIn cookie и токен Instagram в копию не входят: после "
    "восстановления пришли их заново через /setcookie и /igtoken.":
        "📦 Weekly database backup. To bring the history back from it, reply /restore to this message. "
        "The LinkedIn cookie and the Instagram token are not in the copy: after a restore, "
        "send them again with /setcookie and /igtoken.",
    "😴 Без изменений за неделю — всё стабильно ✅": "😴 No changes this week — all steady ✅",
    # bot/db.py: why a file is not a backup (shown by /restore)
    "файл повреждён": "the file is corrupted",
    "это не файл базы SQLite": "it is not an SQLite database file",
    "в файле нет таблиц бота": "the file has none of the bot's tables",
}
PLURALS: dict[str, tuple[str, str]] = {}

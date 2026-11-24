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
    "⏳ Уже собираю данные — по расписанию или по другой команде. Подожди минуту и повтори.":
        "⏳ Already collecting — on schedule or for another command. Wait a minute and try again.",
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
    "✅ Коротко без изменений: включено": "✅ Short when unchanged: on",
    "✅ Коротко без изменений: выключено": "✅ Short when unchanged: off",
    "🟠 Удалить сообщение с cookie не получилось — удали его из чата вручную.":
        "🟠 Could not delete the message with the cookie — delete it from the chat yourself.",
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
    "Проверка вернула {count}. Это первое значение — сверь его со страницей профиля и подтверди: /linkedin {raw}": (
        "The check returned {count}. It is the first value — compare it with the profile page and confirm: /linkedin {raw}"
    ),
    "⏳ Эта команда пришла, пока я был выключен: сообщение с секретом я удалил, "
    "чтобы оно не лежало в чате. Пришли его заново.": (
        "⏳ This command arrived while I was switched off: I deleted the message with the secret "
        "so it does not stay in the chat. Send it again."
    ),
    "Проверка прошла: {count} подписчиков.": "Check passed: {count} followers.",
    "Проверка вернула {count} — слишком далеко от прошлого {prev}, число не записано. "
    "Если оно верное, введи его: /linkedin {raw}":
        "The check returned {count} — too far from the previous {prev}, the number was not recorded. "
        "If it is right, enter it: /linkedin {raw}",
    "✅ Cookie сохранён. {fetched}": "✅ Cookie saved. {fetched}",
    "🟠 Удалить сообщение с токеном не получилось — удали его из чата вручную.":
        "🟠 Could not delete the message with the token — delete it from the chat yourself.",
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
    "Уже собираю данные — подожди несколько секунд": "Already collecting — give it a few seconds",
    "Для графика пока мало данных: нужно хотя бы два дня": "Not enough data for a chart yet: it needs at least two days",
    "График — ниже": "The chart is below",
    "Сохранено": "Saved",
    "{label}: выключено. Включить снова — ⚙️ Настройки → 🧩 Мониторинги":
        "{label}: off. To switch it back on — ⚙️ Settings → 🧩 Monitors",
    "📦 Отправляю бэкап…": "📦 Sending the backup…",
    "Чтобы вернуть историю, пришли файл бэкапа («📦 Еженедельный бэкап базы») и подтверди кнопкой, "
    "или ответь на него командой /restore.\n\n"
    "Данные из бэкапа добавятся к текущим: уже собранное не перезапишется.":
        "To bring the history back, send the backup file (\"📦 Weekly database backup\") and confirm with the button, "
        "or reply to it with /restore.\n\n"
        "The backup's data is added to the current data: what is already collected is not overwritten.",
    "Это бэкап базы? Могу вернуть из него историю — уже собранное не перезапишется.":
        "Is this a database backup? I can bring the history back from it — what is already collected is not overwritten.",
    "Не знаю, что делать с этим файлом. Бэкап базы (.db) я восстановлю — пришли его и подтверди кнопкой.":
        "I don't know what to do with this file. A database backup (.db) I can restore — send it and confirm with the button.",
    "Файл не нашёл — пришли его заново или ответь на него командой /restore":
        "I can't find the file — send it again or reply to it with /restore",
    "Коротко без изменений: включено": "Short when unchanged: on",
    "Коротко без изменений: выключено": "Short when unchanged: off",
    "Нужен хотя бы один день": "At least one day is needed",
    "Отчёт будет приходить в {time}": "The report will come at {time}",
    "включено": "on",
    "выключено": "off",
    "Отменено": "Cancelled",
    "Отменено.": "Cancelled.",
    # /mute and /unmute
    "Максимум — 7 дней: дольше тишина уже не пауза, а выключенный мониторинг.":
        "Seven days at most: a longer silence is not a pause but monitoring switched off.",
    "Использование: /mute <время>\nПримеры: /mute 1h, /mute 8h, /mute 30m, /mute 1d\nПо умолчанию: 8h":
        "Usage: /mute <time>\nExamples: /mute 1h, /mute 8h, /mute 30m, /mute 1d\nDefault: 8h",
    "🔔 Снова пишу обо всём.": "🔔 Writing about everything again.",
    # bot/main.py: the / menu
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
    # The three buttons (BOT_PRINCIPLES §2): what is not understood, a stale button, the note after the update
    "Не понял. Всё — кнопками под полем ввода: 🏠 Главная, 📖 Что я умею, ❓ Значки.":
        "Didn't get that. Everything is on the buttons under the input field: 🏠 Home, 📖 What I do, ❓ Icons.",
    "Кнопка устарела — вот главная. Она всегда под полем ввода: «🏠 Главная»":
        "This button is outdated — here is the home screen. It is always under the input field: \"🏠 Home\"",
    "Полного текста уже нет: я храню его {days} дн. после сводки.":
        "The full text is gone: I keep it for {days} days after the digest.",
    "Такой команды нет. Все команды — в «📖 Что я умею» под полем ввода.":
        "No such command. Every command is in \"📖 What I do\" under the input field.",
    "Главные кнопки теперь под полем ввода: 🏠 Главная, 📖 Что я умею и ❓ Значки. Меню ☰ убрал — "
    "команды работают как раньше, а «🔄 Обновить данные» и «🔕 Помолчать…» — на главной.":
        "The main buttons are now under the input field: 🏠 Home, 📖 What I do and ❓ Icons. The ☰ menu is gone — "
        "commands work as before, and \"🔄 Refresh data\" and \"🔕 Mute…\" are on the home screen.",
    # ⏱ Сторож from the chat
    "🟠 Удалить сообщение со ссылкой не получилось — удали его из чата вручную.":
        "🟠 Could not delete the message with the link — delete it from the chat yourself.",
    "❌ Нужна ссылка https://…, например https://hc-ping.com/… из healthchecks.io. "
    "Пришли её ещё раз или нажми «✖️ Отмена».":
        "❌ It needs an https://… link, e.g. https://hc-ping.com/… from healthchecks.io. "
        "Send it again or press \"✖️ Cancel\".",
    "⏳ Отмечаюсь пробным пингом…": "⏳ Checking in with a test ping…",
    "❌ Сторож не на связи: {reason}. Проверь, что ссылка скопирована целиком и check не удалён, "
    "и пришли её ещё раз — или нажми «✖️ Отмена».":
        "❌ The watchdog is not reachable: {reason}. Check that the whole link was copied and the check was not "
        "deleted, and send it again — or press \"✖️ Cancel\".",
    "✅ Сторож подключён и на связи ({who}). Дальше отмечаюсь после каждого ежедневного сбора.":
        "✅ The watchdog is connected and reachable ({who}). From now on I check in after every daily collection.",
    "✅ Сторож на связи": "✅ The watchdog is reachable",
    "🟠 Удалить сообщение с ключом не получилось — удали его из чата вручную.":
        "🟠 Could not delete the message with the key — delete it from the chat yourself.",
    "⏳ Проверяю ключ…": "⏳ Checking the key…",
    "❌ {source} не принял ключ: {reason}. Пришли его ещё раз или нажми «✖️ Отмена».":
        "❌ {source} did not take the key: {reason}. Send it again or tap «✖️ Cancel».",
    "✅ {source} подключён: {seen}": "✅ {source} is connected: {seen}",
    "✅ Брендовые слова: {words}": "✅ Brand words: {words}",
    "Брендовые слова убраны": "Brand words removed",
    "⏳ Собираю отчёт…": "⏳ Building the report…",
    "🔎 За неделю сказать нечего: подключённые источники ничего не нашли.":
        "🔎 Nothing to say for the week: the connected sources found nothing.",
    "Сторож отключён": "The watchdog is disconnected",
    (
        "⏱ Ещё один шаг — сторож. Пока я работаю, о проблемах пишу сам; если остановлюсь — упадёт сервер, "
        "кончится место, отзовут токен — сказать об этом будет некому. Сторож — бесплатный healthchecks.io: "
        "я отмечаюсь у него после каждого ежедневного сбора, а не отметился — он пишет тебе. Две минуты, кнопка ниже."
    ): (
        "⏱ One more step — a watchdog. While I work, I report problems myself; if I stop — the server goes down, "
        "the disk fills up, the token is revoked — nobody will tell you. A watchdog is the free healthchecks.io: "
        "I check in with it after every daily collection, and when I miss it, it writes to you. Two minutes, the button below."
    ),
}
PLURALS: dict[str, tuple[str, str]] = {}

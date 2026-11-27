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
    "❌ Сначала подключи Instagram: 🔌 Подключения → «➕ Instagram».":
        "❌ Connect Instagram first: 🔌 Connections → «➕ Instagram».",
    "❌ Нужен @username канала или ссылка t.me/…, а у закрытого канала — любой его пост, пересланный сюда. Пришли ещё раз или нажми «✖️ Отмена».":
        "❌ I need the channel's @username or a t.me/… link, and for a private channel any of its posts forwarded here. "
        "Send it again or press «✖️ Cancel».",
    "❌ По ссылке-приглашению я не узнаю, какой это канал. Перешли сюда любой пост из канала — или нажми «✖️ Отмена».":
        "❌ An invite link doesn't tell me which channel it is. Forward any post from the channel here — or press «✖️ Cancel».",
    "❌ Не вижу этот канал — я всё ещё его администратор?":
        "❌ I can't see this channel — am I still its admin?",
    "❌ Не вижу канал {channel}. Проверь имя и добавь меня в администраторы канала, потом пришли его ещё раз — или нажми «✖️ Отмена».":
        "❌ I cannot see the channel {channel}. Check the name and make me an admin of the channel, "
        "then send it again — or press «✖️ Cancel».",
    "✅ Telegram-канал {channel} подключён: сейчас {count}.":
        "✅ The Telegram channel {channel} is connected: {count} now.",
    "Чтобы видеть вступления, посты и реакции, добавь меня в администраторы канала.":
        "To see joins, posts and reactions, make me an admin of the channel.",
    "❌ Нужен id канала — 24 знака, начинается с UC (YouTube → Настройки → Расширенные настройки), или ссылка youtube.com/channel/UC…. Пришли ещё раз или нажми «✖️ Отмена».":
        "❌ I need the channel id — 24 characters, starts with UC (YouTube → Settings → Advanced settings), "
        "or a youtube.com/channel/UC… link. Send it again or press «✖️ Cancel».",
    "❌ Это не похоже на ключ YouTube Data API. Пришли его ещё раз или нажми «✖️ Отмена».":
        "❌ This does not look like a YouTube Data API key. Send it again or press «✖️ Cancel».",
    "❌ YouTube не отдал число подписчиков канала {channel} с этим ключом. Проверь, что в проекте включён YouTube Data API v3 и id канала верный, и пришли ключ ещё раз — или нажми «✖️ Отмена».":
        "❌ YouTube did not return the subscriber count of {channel} with this key. Check that YouTube Data API v3 "
        "is enabled in the project and the channel id is right, then send the key again — or press «✖️ Cancel».",
    "✅ YouTube подключён: сейчас {count}.": "✅ YouTube is connected: {count} now.",
    "❌ Нужен @username Instagram или ссылка на профиль. Пришли ещё раз или нажми «✖️ Отмена».":
        "❌ I need an Instagram @username or a profile link. Send it again or press «✖️ Cancel».",
    "✅ Instagram @{username} записан. Остался токен: кнопка «📸 Instagram» ниже.":
        "✅ Instagram @{username} is saved. The token is left: the «📸 Instagram» button below.",
    "❌ Нужна ссылка на профиль вида linkedin.com/in/…. Пришли ещё раз или нажми «✖️ Отмена».":
        "❌ I need a profile link like linkedin.com/in/…. Send it again or press «✖️ Cancel».",
    "✅ Профиль LinkedIn записан. Дальше — cookie или число вручную: кнопка «💼 LinkedIn» ниже.":
        "✅ The LinkedIn profile is saved. Next — the cookie or the number by hand: the «💼 LinkedIn» button below.",
    "⏳ Проверяю токен…": "⏳ Checking the token…",
    "Instagram отклонил токен": "Instagram rejected the token",
    "не удалось связаться с Instagram (подробности в логах)": "could not reach Instagram (details in the logs)",
    "токен выдан не для @{username} — проверь @username в «🔌 Подключения» и какой аккаунт добавлен в приложение Meta":
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
    "Язык: {lang}. Кнопки под полем ввода обновил.": "Language: {lang}. The buttons under the input field are updated.",
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
    "❌ Не знаю такой пояс: «{tz}».\nПришли город по-английски или название пояса, например /settz Berlin или /settz Asia/Almaty. Частые пояса — кнопками: /settz без названия.":
        "❌ I do not know that zone: «{tz}».\nSend a city in English or a zone name, for example /settz Berlin or /settz Asia/Almaty. Common zones are buttons: /settz without a name.",
    "⏳ Отмечаюсь у сторожа…":
        "⏳ Checking in with the watchdog…",
    "Убрал то, что было задано в чате. Если сеть задана в настройках хостинга — действует она.":
        "Removed what was set in the chat. If the network is set in the hosting settings, that one is in force.",
    "❌ Ключ не принят: проверь, что он скопирован целиком и не отозван.":
        "❌ The key was not accepted: check that it was copied whole and not revoked.",
    "❌ У ключа нет доступа к API: проверь его рабочее пространство на console.anthropic.com.":
        "❌ The key has no access to the API: check its workspace on console.anthropic.com.",
    "❌ Ключ работает, но модель {model} ему недоступна.":
        "❌ The key works, but the model {model} is not available to it.",
    "⚠️ Не смог проверить ключ: Anthropic сейчас не отвечает. Попробуй через пару минут.":
        "⚠️ I could not check the key: Anthropic is not answering right now. Try again in a couple of minutes.",
    "Пришли ключ ещё раз или нажми «✖️ Отмена».":
        "Send the key again or press «✖️ Cancel».",
    "Убрал ключ, заданный в чате. Если ключ задан в настройках хостинга — действует он.":
        "Removed the key set in the chat. If a key is set in the hosting settings, that one is in force.",
    "❌ Это не похоже на ключ Claude API: он начинается с sk-ant-.":
        "❌ This does not look like a Claude API key: it starts with sk-ant-.",
    "✅ Ключ Claude принят: модель {model} ему доступна. Проверяю комментарии со следующего.":
        "✅ The Claude key is accepted: the model {model} is available to it. I check comments from the next one on.",
    "Лимит: {n} в сутки":
        "Limit: {n} a day",
    "Лимит снят":
        "Limit removed",
    "Ящик отключён":
        "The mailbox is disconnected",
    "Воркер отключён":
        "The worker is disconnected",
    "🟠 Удалить сообщение не получилось — удали его из чата вручную.":
        "🟠 I could not delete the message — delete it from the chat yourself.",
    "Убрал ящик, заданный в чате.":
        "Removed the mailbox set in the chat.",
    "❌ Это не похоже на адрес почты. Пришли его ещё раз или нажми «✖️ Отмена».":
        "❌ This does not look like an email address. Send it again or press «✖️ Cancel».",
    "❌ Пока я умею только Gmail и Яндекс: адрес на gmail.com, yandex.ru, ya.ru или yandex.com. Заведи такой ящик для бота и пришли его адрес — или нажми «✖️ Отмена».":
        "❌ So far I can read only Gmail and Yandex: an address at gmail.com, yandex.ru, ya.ru or yandex.com. Make such a mailbox for the bot and send its address — or press «✖️ Cancel».",
    "❌ Сначала адрес ящика: нажми «📮 Отдельный ящик» ещё раз.":
        "❌ The mailbox's address first: press «📮 A separate mailbox» again.",
    "❌ Ящик {address} не принял пароль. Нужен пароль приложения, а не пароль от почты.":
        "❌ The mailbox {address} did not take the password. It needs an app password, not the mailbox's own one.",
    "Яндекс: проверь, что почтовые программы (IMAP) разрешены, и учти, что новый пароль приложения может заработать не сразу — тогда пришли его чуть позже.":
        "Yandex: check that email clients (IMAP) are allowed, and a new app password may start working only after a while — then send it a bit later.",
    "⚠️ Не смог достучаться до почтового сервера. Попробуй через пару минут.":
        "⚠️ I could not reach the mail server. Try again in a couple of minutes.",
    "Пришли пароль ещё раз или нажми «✖️ Отмена».":
        "Send the password again or press «✖️ Cancel».",
    "✅ Ящик {address} подключён: читаю новые письма раз в 5 минут; то, что уже лежит в ящике, не трогаю.":
        "✅ The mailbox {address} is connected: I read new mail every 5 minutes and leave what is already there alone.",
    "Убрал воркер, заданный в чате. Если он задан в настройках хостинга — действует он.":
        "Removed the worker set in the chat. If one is set in the hosting settings, that one is in force.",
    "❌ Нужен адрес вида https://socialbot-mail.<аккаунт>.workers.dev. Пришли ещё раз или нажми «✖️ Отмена».":
        "❌ It needs an address like https://socialbot-mail.<account>.workers.dev. Send it again or press «✖️ Cancel».",
    "❌ Сначала адрес воркера: нажми «☁️ Свой воркер» ещё раз.":
        "❌ The worker's address first: press «☁️ Your own worker» again.",
    "❌ Воркер не принял токен. Пришли тот, что задан у воркера, или нажми «✖️ Отмена».":
        "❌ The worker did not take the token. Send the one the worker has, or press «✖️ Cancel».",
    "⚠️ Воркер не ответил. Проверь адрес и пришли токен ещё раз — или нажми «✖️ Отмена».":
        "⚠️ The worker did not answer. Check the address and send the token again — or press «✖️ Cancel».",
    "✅ Воркер подключён: забираю у него письма раз в 5 минут.":
        "✅ The worker is connected: I fetch its mail every 5 minutes.",
}
PLURALS: dict[str, tuple[str, str]] = {}

"""English for bot/ui (see bot/i18n.py)."""

from __future__ import annotations

STRINGS: dict[str, str] = {
    # Reply keyboard and greeting
    "🏠 Меню": "🏠 Menu",
    "📊 Меню": "📊 Menu",
    "✅ Теперь этот бот твой: он отвечает только тебе.": "✅ This bot is yours now: it answers only you.",
    "👋 Привет! Я слежу за подписчиками и безопасностью твоих аккаунтов.\n\n"
    "Пока всё в порядке, я молчу. О падении подписчиков, накрутке, смене названия, ссылок "
    "или админов и о письмах про новые входы пишу сразу, а сводку присылаю по расписанию.\n\n"
    "Кнопка «{menu}» внизу экрана всегда возвращает на главную.":
        "👋 Hi! I keep an eye on your accounts' followers and security.\n\n"
        "While everything is fine, I stay quiet. A drop in followers, fake growth, a changed name, "
        "links or admins, and emails about new sign-ins I report right away; the summary comes on schedule.\n\n"
        "The \"{menu}\" button at the bottom of the screen always takes you home.",
    "Меню — кнопкой ниже, команды — через /": "Menu: the button below; commands: via /",
    # Report schedule in words
    "каждый день": "every day",
    "по будням": "on weekdays",
    "по выходным": "on weekends",
    "ни в один день": "on no day",
    "Пн": "Mon",
    "Вт": "Tue",
    "Ср": "Wed",
    "Чт": "Thu",
    "Пт": "Fri",
    "Сб": "Sat",
    "Вс": "Sun",
    "по понедельникам": "on Mondays",
    "по вторникам": "on Tuesdays",
    "по средам": "on Wednesdays",
    "по четвергам": "on Thursdays",
    "по пятницам": "on Fridays",
    "по субботам": "on Saturdays",
    "по воскресеньям": "on Sundays",
    "Нью-Йорк": "New York",
    "Лондон": "London",
    "Берлин": "Berlin",
    "Калининград": "Kaliningrad",
    "Москва": "Moscow",
    "Самара": "Samara",
    "Тбилиси": "Tbilisi",
    "Екатеринбург": "Yekaterinburg",
    "Ташкент": "Tashkent",
    "Алматы": "Almaty",
    "Новосибирск": "Novosibirsk",
    "Владивосток": "Vladivostok",
    "сегодня": "today",
    "завтра": "tomorrow",
    "{when} в {time}": "{when} at {time}",
    "не запланирован": "not scheduled",
    # Home and followers
    "⏭ Следующий отчёт: {next}": "⏭ Next report: {next}",
    "🔄 Обновить данные": "🔄 Refresh data",
    "📈 Динамика": "📈 Trends",
    "🛡 Безопасность": "🛡 Security",
    "✏️ Ввести число LinkedIn": "✏️ Enter LinkedIn count",
    "⚙️ Настройки": "⚙️ Settings",
    "❓ Помощь": "❓ Help",
    "⏳ Собираю свежие данные — это займёт несколько секунд…": "⏳ Collecting fresh data — this takes a few seconds…",
    "🖼 График за 30 дней": "🖼 30-day chart",
    "📋 По дням": "📋 By day",
    "Главная": "Home",
    "Все": "All",
    "Динамика": "Trends",
    # Security
    "не заполнено": "not filled in",
    "{points} из {max}": "{points} of {max}",
    "<b>🛡 Безопасность</b>\n\nНет подключённых платформ — подключи хотя бы одну в .env.":
        "<b>🛡 Security</b>\n\nNo platforms are connected — connect at least one in .env.",
    "<b>🛡 Безопасность: {total} из {max}</b>": "<b>🛡 Security: {total} of {max}</b>",
    "<b>Что сделать в первую очередь</b>": "<b>What to do first</b>",
    "…и ещё {n} — в чек-листах аккаунтов": "…and {n} more — in the account checklists",
    "<b>Последние события</b>": "<b>Recent events</b>",
    "Нажми на аккаунт, чтобы отметить пункты. Пароли я не спрашиваю и не храню.":
        "Tap an account to mark its items. I never ask for or store passwords.",
    "<b>🛡 {label}: {points} из {max}</b>\n"
    "{account}\n\n"
    "Нажми на пункт, чтобы отметить, как сейчас. Пароль вводить не нужно — только отметки.":
        "<b>🛡 {label}: {points} of {max}</b>\n"
        "{account}\n\n"
        "Tap an item to mark how things are now. No password needed — just the marks.",
    "Безопасность": "Security",
    "не отмечено": "not marked",
    "<b>🛡 {label} · вопрос {n} из {total}</b>\n\n"
    "<b>{question}</b>\n\n"
    "Совет: {advice}.\n\n"
    "Сейчас: {current}":
        "<b>🛡 {label} · question {n} of {total}</b>\n\n"
        "<b>{question}</b>\n\n"
        "Tip: {advice}.\n\n"
        "Now: {current}",
    # Settings
    "сборка {commit} · ": "build {commit} · ",
    "<b>⚙️ Настройки</b>": "<b>⚙️ Settings</b>",
    "📅 Отчёт: {days}, в {time}": "📅 Report: {days}, at {time}",
    "🌍 Часовой пояс: {tz}": "🌍 Time zone: {tz}",
    "Данные собираются каждый день в это время, а отчёт приходит в выбранные дни.":
        "Data is collected every day at this time; the report comes on the chosen days.",
    "📝 Коротко без изменений: {state}": "📝 Short when unchanged: {state}",
    "включён": "on",
    "выключен": "off",
    "Когда включено, неделя без изменений — это одна строка вместо отчёта.":
        "When it is on, a week without changes is a single line instead of a report.",
    "<i>Версия: {build}Python {python}</i>": "<i>Version: {build}Python {python}</i>",
    "🧩 Мониторинги": "🧩 Monitors",
    "📅 Дни отчёта": "📅 Report days",
    "🕗 Время отчёта": "🕗 Report time",
    "🌍 Часовой пояс": "🌍 Time zone",
    "Коротко без изменений": "Short when unchanged",
    "📦 Бэкап сейчас": "📦 Backup now",
    "<b>📅 Дни отчёта</b>\n\n"
    "Сейчас: {days}, в {time}\n\n"
    "Отметь дни, когда присылать отчёт. Данные собираются каждый день, "
    "а о проблемах я пишу сразу, в любой день.":
        "<b>📅 Report days</b>\n\n"
        "Now: {days}, at {time}\n\n"
        "Mark the days to send the report on. Data is collected every day, "
        "and I report problems right away, on any day.",
    "Каждый день": "Every day",
    "Будни": "Weekdays",
    "Выходные": "Weekends",
    "Настройки": "Settings",
    "Часы ниже — по UTC. Чтобы выбирать по своим часам, укажи часовой пояс.":
        "The hours below are UTC. To pick by your own clock, set a time zone.",
    "Часы ниже — по поясу {tz}.": "The hours below are in {tz}.",
    "<b>🕗 Время отчёта</b>\n\n"
    "Сейчас: {time}\n\n"
    "{zone} Час — в сетке, минуты — в ряду под ней; любое время — командой, например /settime 08:37":
        "<b>🕗 Report time</b>\n\n"
        "Now: {time}\n\n"
        "{zone} The hour in the grid, the minutes in the row under it; any time by command, e.g. /settime 08:37",
    "✏️ Другой пояс…": "✏️ Another zone…",
    "<b>🌍 Часовой пояс</b>\n\n"
    "Сейчас: {tz}, там {now:%H:%M}\n\n"
    "По этому поясу считаются время и дни отчёта. Выбери свой или пришли его название командой, "
    "например /settz Asia/Kolkata":
        "<b>🌍 Time zone</b>\n\n"
        "Now: {tz}, where it is {now:%H:%M}\n\n"
        "The report time and days follow this zone. Pick yours or send its name with the command, "
        "e.g. /settz Asia/Kolkata",
    "<b>🧩 Мониторинги</b>": "<b>🧩 Monitors</b>",
    "<b>Платформы</b> — подключаются в .env": "<b>Platforms</b> — connected in .env",
    "не подключено": "not connected",
    "<b>Проверки</b> — нажми, чтобы включить или выключить": "<b>Checks</b> — tap to turn on or off",
    "{icon} {label} — нужно: {needs}": "{icon} {label} — needs: {needs}",
    # LinkedIn
    "Профиль: {url}": "Profile: {url}",
    "не задан": "not set",
    "введено вручную": "entered by hand",
    "собрано по cookie": "collected via cookie",
    "Последнее значение: {count} — {how} {when}": "Last value: {count} — {how} {when}",
    "Последнее значение: пока нет": "Last value: none yet",
    "🟠 LinkedIn отклонил cookie: пришли новый через /setcookie или вводи число вручную.":
        "🟠 LinkedIn rejected the cookie: send a new one with /setcookie or enter the count by hand.",
    "⚠️ Cookie установлен {age} {d} назад и скоро истечёт — пора обновить.":
        "⚠️ The cookie was set {age} {d} ago and expires soon — time to renew it.",
    "✅ Число собирается само по cookie. Он установлен {age} {d} назад, "
    "напомню обновить через ~{left} {ld}.":
        "✅ The count is collected automatically via cookie. It was set {age} {d} ago; "
        "I will remind you to renew it in ~{left} {ld}.",
    "✅ Число собирается само по cookie, но срок его жизни я не вижу. "
    "Пришли cookie через /setcookie — и я напомню, когда его обновить.":
        "✅ The count is collected automatically via cookie, but I cannot see how long it lives. "
        "Send the cookie with /setcookie and I will remind you when to renew it.",
    "✏️ Число вводится вручную: cookie не задан.": "✏️ The count is entered by hand: no cookie is set.",
    "<b>Автосбор</b>: нажми «🔑 Прислать cookie» и пришли значение cookie li_at "
    "(linkedin.com → DevTools → Application → Cookies); то же — командой /setcookie. "
    "Я проверю его и сразу удалю сообщение.":
        "<b>Automatic collection</b>: press \"🔑 Send the cookie\" and send the value of the li_at cookie "
        "(linkedin.com → DevTools → Application → Cookies); the /setcookie command does the same. "
        "I will check it and delete the message right away.",
    "🔑 Прислать cookie": "🔑 Send the cookie",
    "🔑 Прислать токен": "🔑 Send the token",
    "<i>LinkedIn запрещает автоматический доступ, так что автосбор — на твой риск.</i>":
        "<i>LinkedIn forbids automated access, so automatic collection is at your own risk.</i>",
    "✏️ Ввести число вручную": "✏️ Enter count by hand",
    # Instagram
    "Аккаунт: {account}": "Account: {account}",
    "Последнее значение: {count} — собрано {when}": "Last value: {count} — collected {when}",
    "⚠️ Токена нет: без него число не собирается.": "⚠️ No token: without it the count is not collected.",
    "🟠 Instagram отклонил токен: отозван или истёк — пришли новый через /igtoken.":
        "🟠 Instagram rejected the token: revoked or expired — send a new one with /igtoken.",
    "✅ Число собирается само по токену из переменных окружения.":
        "✅ The count is collected automatically with the token from the environment variables.",
    "✅ Число собирается само по токену. Он задан {age} {d} назад и бессрочный: "
    "если Meta его отзовёт, я скажу.":
        "✅ The count is collected automatically with the token. It was set {age} {d} ago and does not expire: "
        "if Meta revokes it, I will tell you.",
    "<b>Как подключить</b>: аккаунт должен быть профессиональным (Автор или Бизнес). "
    "На developers.facebook.com создай приложение с вариантом «Instagram API», открой "
    "«API setup with Unified login», добавь свой аккаунт как Instagram Tester, прими приглашение "
    "в Instagram (Настройки → Website permissions → Tester invitations) и нажми «Generate token». "
    "Потом нажми «🔑 Прислать токен» и пришли его одним сообщением (то же — командой /igtoken) — "
    "я проверю его и сразу удалю сообщение.":
        "<b>How to connect</b>: the account must be professional (Creator or Business). "
        "On developers.facebook.com create an app of the \"Instagram API\" kind, open "
        "\"API setup with Unified login\", add your account as an Instagram Tester, accept the invitation "
        "in Instagram (Settings → Website permissions → Tester invitations) and press \"Generate token\". "
        "Then press \"🔑 Send the token\" and send it in one message (the /igtoken command does the same) — "
        "I will check it and delete the message right away.",
    "<i>Это официальный API: бот читает только публичные данные своего аккаунта.</i>":
        "<i>This is the official API: the bot reads only its own account's public data.</i>",
    # Manual LinkedIn input
    "\nСейчас: {count}": "\nNow: {count}",
    "<b>✏️ LinkedIn вручную</b>\n\nПришли число подписчиков одним сообщением, например 4520.{current}":
        "<b>✏️ LinkedIn by hand</b>\n\nSend the follower count in one message, e.g. 4520.{current}",
    "Отмена": "Cancel",
    "Это не похоже на число. Пришли только цифры, например 4520, или нажми «Отмена».":
        "That does not look like a number. Send digits only, e.g. 4520, or press \"Cancel\".",
    "<b>⚠️ Проверь число</b>\n\n{count} сильно отличается от прошлого значения "
    "{prev}. Возможно, это опечатка.":
        "<b>⚠️ Check the number</b>\n\n{count} differs a lot from the previous value "
        "{prev}. It may be a typo.",
    "Сохранить {count}": "Save {count}",
    "✏️ Ввести заново": "✏️ Enter again",
    # Help
    "<b>❓ Помощь</b>": "<b>❓ Help</b>",
    "Каждый день я собираю подписчиков и слежу за безопасностью аккаунтов. "
    "Пока всё в порядке — молчу; о проблеме пишу сразу, а сводку присылаю по расписанию.":
        "Every day I collect follower counts and watch over the accounts' security. "
        "While everything is fine, I stay quiet; I report a problem right away, and the summary comes on schedule.",
    "<b>Значки</b>": "<b>Icons</b>",
    "✅ в порядке или включено · ⬜ выключено · ➖ не подключено": "✅ fine or on · ⬜ off · ➖ not connected",
    "⚠️ нужно внимание · ❓ не отмечено": "⚠️ needs attention · ❓ not marked",
    "🚨 похоже на взлом · 🔴 аккаунт недоступен — звонят сразу, даже ночью":
        "🚨 looks like a break-in · 🔴 account unreachable — ring at once, even at night",
    "🟠 изменение или сбой — тихо; ночью и в тишине ждёт сводки":
        "🟠 change or failure — silent; at night and while muted it waits for the digest",
    "<b>Команды</b>": "<b>Commands</b>",
    "/start — главная": "/start — home",
    "/now — обновить данные": "/now — refresh data",
    "/week — динамика за неделю и график": "/week — the week's trends and a chart",
    "/security — безопасность аккаунтов": "/security — account security",
    "/settings — настройки": "/settings — settings",
    "/history [платформа] [дни] — таблица по дням, до 90 дней": "/history [platform] [days] — day-by-day table, up to 90 days",
    "/linkedin &lt;число&gt; — ввести LinkedIn вручную": "/linkedin &lt;count&gt; — enter LinkedIn by hand",
    "/setcookie &lt;li_at&gt; — cookie LinkedIn для автосбора": "/setcookie &lt;li_at&gt; — LinkedIn cookie for automatic collection",
    "/igtoken &lt;токен&gt; — токен Instagram для автосбора": "/igtoken &lt;token&gt; — Instagram token for automatic collection",
    "/settime ЧЧ:ММ — время отчёта": "/settime HH:MM — report time",
    "/setday &lt;дни&gt; — дни отчёта: sat, mon-fri, mon,thu, daily": "/setday &lt;days&gt; — report days: sat, mon-fri, mon,thu, daily",
    "/settz &lt;пояс&gt; — часовой пояс, например Europe/Moscow": "/settz &lt;zone&gt; — time zone, e.g. Europe/Moscow",
    "/setquiet on|off — одна строка вместо отчёта, если за неделю без изменений":
        "/setquiet on|off — one line instead of the report when a week brought no change",
    "/connections — подключения: что собирается само, чему нужен токен или cookie":
        "/connections — connections: what is collected by itself, what needs a token or a cookie",
    "<b>Кнопки внизу</b>": "<b>The buttons at the bottom</b>",
    "🏠 Меню — главная · 🔄 Обновить — собрать данные сейчас · 🔕 Тихо 8 ч — помолчать":
        "🏠 Menu — home · 🔄 Refresh — collect the data now · 🔕 Quiet for 8 h — mute",
    "Под тревогами и отчётами — кнопки туда, где разбираться; ⚙️ — выключить такие уведомления.":
        "Under alerts and reports — buttons to where to look into it; ⚙️ — stop sending such notifications.",
    "/mute &lt;время&gt; — помолчать: 1h, 8h, 1d (по умолчанию 8h); /unmute — снять":
        "/mute &lt;time&gt; — pause notifications: 1h, 8h, 1d (default 8h); /unmute — resume",
    # 🔔 Когда писать: quiet hours and /mute (bot/ui.py when_to_write, bot/notifier.py)
    "🔔 Когда писать: {when}": "🔔 When to write: {when}",
    "🔔 Когда писать": "🔔 When to write",
    "тихие часы {hours}": "quiet hours {hours}",
    "всегда": "always",
    "тишина до {until}": "muted until {until}",
    "<b>🔔 Когда писать</b>": "<b>🔔 When to write</b>",
    "🌙 Тихие часы: {state}": "🌙 Quiet hours: {state}",
    "выключены": "off",
    "Ночью некритичное ждёт до утра и приходит одной сводкой. Часы — по поясу {tz}.":
        "At night anything non-critical waits for the morning and comes as one digest. Hours in {tz}.",
    "🔕 Помолчать: {state}": "🔕 Mute: {state}",
    "до {until}": "until {until}",
    "сейчас не молчу": "not muted now",
    "На время: всё, кроме критичного, ждёт и приходит сводкой, когда тишина закончится. "
    "Команда: /mute 8h, снять — /unmute.":
        "For a while: everything but the critical waits and comes as a digest when the silence ends. "
        "Command: /mute 8h, lift it with /unmute.",
    "🌙 выкл": "🌙 off",
    "🔔 Снять тишину": "🔔 Unmute",
    "🔕 Молчу до {until}.": "🔕 Muted until {until}.",
    "Снова писать обо всём: /unmute": "To hear about everything again: /unmute",
    "🔕 Тишина до {until}": "🔕 Muted until {until}",
    "🌙 Тихие часы до {end:02d}:00": "🌙 Quiet hours until {end:02d}:00",
    "🚨 и 🔴 — похоже на взлом, новый вход, смена пароля, пропавший профиль — придут сразу, со звуком. "
    "Остальное пришлю сводкой, когда тишина закончится.":
        "🚨 and 🔴 — a likely break-in, a new sign-in, a changed password, a vanished profile — come at once, "
        "with sound. Everything else comes as a digest when the silence ends.",
    "🌙 Накопилось, пока было тихо:": "🌙 Piled up while it was quiet:",
    "🌙 (продолжение)": "🌙 (continued)",
    "/modules — мониторинги": "/modules — monitors",
    "/comments — комментарии канала: что проверено и насколько точно": (
        "/comments — the channel's comments: what was checked and how accurately"
    ),
    # Comments screen
    "💬 Комментарии канала": "💬 Channel comments",
    "<b>💬 Комментарии канала</b>": "<b>💬 Channel comments</b>",
    "Не подключено — нужно: {needs}. Тогда я буду смотреть каждый комментарий в группе обсуждения "
    "и присылать карточку с кнопками на запрещённый контент.": (
        "Not connected — needed: {needs}. Then I will look at every comment in the discussion group "
        "and send a card with buttons for prohibited content."
    ),
    "Режим: только сообщаю. Каждый комментарий в группе обсуждения смотрит модель; на запрещённый контент "
    "приходит карточка, а удалить или забанить — кнопкой под ней. Сам я ничего не удаляю.": (
        "Mode: report only. A model looks at every comment in the discussion group; prohibited content "
        "becomes a card, and deleting or banning is a button under it. I delete nothing myself."
    ),
    "Группа: группа обсуждения канала {channel}, бот должен быть в ней админом с правом удалять "
    "сообщения и блокировать участников.": (
        "Group: the discussion group of {channel}; the bot must be its admin with the rights to delete "
        "messages and ban members."
    ),
    "Группа: {chat}, бот должен быть в ней админом с правом удалять сообщения и блокировать "
    "участников.": (
        "Group: {chat}; the bot must be its admin with the rights to delete messages and ban members."
    ),
    "Модель: {model}": "Model: {model}",
    "⬜ Выключено — комментарии не проверяются. Включить — кнопкой ниже.":
        "⬜ Switched off — comments are not checked. The button below switches it on.",
    "<b>За {days} дней</b>": "<b>Last {days} days</b>",
    "Проверено комментариев: {n}": "Comments checked: {n}",
    "Помеченных пока нет.": "Nothing flagged yet.",
    "Помечено · подтверждено · ложных:": "Flagged · confirmed · false:",
    "Точность по твоим отметкам: {pct}% ({confirmed} из {judged})": "Accuracy by your marks: {pct}% ({confirmed} of {judged})",
    "Отмечай карточки кнопками — из отметок складывается точность.": "Mark the cards with the buttons — the marks add up to the accuracy.",
    # The channel screen (bot/ui.py channel_screen)
    "📣 Канал": "📣 Channel",
    "<b>📣 Канал {channel}</b>": "<b>📣 Channel {channel}</b>",
    "Не подключено — нужно: {needs}.": "Not connected — needed: {needs}.",
    "⬜ Выключено — события не записываются. Включить — кнопкой ниже.":
        "⬜ Switched off — events are not recorded. The button below switches it on.",
    "Просмотры, пересылки и цитирование Bot API не отдаёт — они в статистике самого Telegram "
    "(в канале: ⋮ → Статистика).": (
        "Views, forwards and citations are not in the Bot API — they are in Telegram's own statistics "
        "(in the channel: ⋮ → Statistics)."
    ),
    "/channel — жизнь канала: подписки и отписки, откуда пришли, посты и реакции": (
        "/channel — life of the channel: joins and leaves, where they came from, posts and reactions"
    ),
    "<b>Бэкап</b>": "<b>Backup</b>",
    "По воскресеньям я присылаю файл с базой (и по кнопке «📦 Бэкап сейчас» в настройках). "
    "Чтобы вернуть историю, пришли этот файл или ответь на него командой /restore — "
    "уже собранное не перезапишется.":
        "On Sundays I send the database file (and on the \"📦 Backup now\" button in the settings). "
        "To bring the history back, send that file or reply to it with /restore — "
        "what is already collected is not overwritten.",
    # the text-input conversations and the restore prompt
    "🔑 Пришли значение cookie li_at одним сообщением "
    "(linkedin.com → DevTools → Application → Cookies → li_at → Value). "
    "Я проверю его и сразу удалю сообщение.":
        "🔑 Send the value of the li_at cookie in one message "
        "(linkedin.com → DevTools → Application → Cookies → li_at → Value). "
        "I will check it and delete the message right away.",
    "🔑 Пришли токен Instagram одним сообщением "
    "(developers.facebook.com → приложение → API setup with Unified login → Generate token). "
    "Я проверю его и сразу удалю сообщение.":
        "🔑 Send the Instagram token in one message "
        "(developers.facebook.com → your app → API setup with Unified login → Generate token). "
        "I will check it and delete the message right away.",
    "🌍 Пришли название часового пояса из базы IANA одним сообщением, например Asia/Kolkata или America/Chicago.":
        "🌍 Send the name of the time zone from the IANA database in one message, e.g. Asia/Kolkata or America/Chicago.",
    "Не знаю такой часовой пояс. Нужно название из базы IANA, например Europe/Moscow, или нажми «Отмена».":
        "Unknown time zone. It must be an IANA name, e.g. Europe/Moscow, or press \"Cancel\".",
    "✅ Восстановить": "✅ Restore",
    # the reply keyboard, the home screen, 🔌 Подключения
    "🔄 Обновить": "🔄 Refresh",
    "сегодня {time}": "today {time}",
    "🕒 Последний сбор: {when}": "🕒 Last collection: {when}",
    "🧭 Осталось настроить:": "🧭 Left to set up:",
    "часовой пояс — пока отчёт по UTC": "the time zone — for now the report comes in UTC",
    "токен Instagram — без него число не собирается": "the Instagram token — no count without it",
    "LinkedIn — cookie для автосбора или первое число вручную":
        "LinkedIn — a cookie for automatic collection, or the first number by hand",
    "🌍 Выбрать часовой пояс": "🌍 Choose the time zone",
    "<b>🔌 Подключения</b>": "<b>🔌 Connections</b>",
    "Подключения": "Connections",
    "{icon} {label} — не подключено: {needs} в .env": "{icon} {label} — not connected: {needs} in .env",
    "⚠️ нужен токен": "⚠️ a token is needed",
    "🟠 токен отклонён": "🟠 the token was rejected",
    "🟠 cookie отклонён, число вручную": "🟠 the cookie was rejected, the number by hand",
    "✏️ число вручную": "✏️ the number by hand",
    "⚠️ подтверди первое число": "⚠️ confirm the first number",
    "✅ собирается": "✅ collected",
    "⏳ первый сбор ещё не был": "⏳ no collection yet",
    "Сети включаются в .env и перезапуском бота; токен Instagram и cookie LinkedIn — кнопками здесь.":
        "Networks are switched on in .env and a restart of the bot; the Instagram token and the LinkedIn cookie — "
        "with the buttons here.",
    # bot/callbacks.py — the rows under alerts and reports
    "🏠 Главная": "🏠 Home",
    "💬 Комментарии": "💬 Comments",
    "🔌 Подключения": "🔌 Connections",
    "🔕 Тихо 8 ч": "🔕 Quiet for 8 h",
    "⚙️ Не присылать такие": "⚙️ Stop sending these",
}

# Russian singular → (English singular, English plural).
PLURALS: dict[str, tuple[str, str]] = {
    "дн.": ("day", "days"),
    "день": ("day", "days"),
    "час": ("hour", "hours"),
    "минута": ("minute", "minutes"),
}

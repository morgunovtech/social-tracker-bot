"""English for bot/ui (see bot/i18n.py)."""

from __future__ import annotations

STRINGS: dict[str, str] = {
    # Reply keyboard and greeting
    "📊 Меню": "📊 Menu",
    "✅ Теперь этот бот твой: он отвечает только тебе.": "✅ This bot is yours now: it answers only you.",
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
    "⏳ Собираю свежие данные — это займёт несколько секунд…": "⏳ Collecting fresh data — this takes a few seconds…",
    "🖼 График за 30 дней": "🖼 30-day chart",
    "📋 По дням": "📋 By day",
    "Все": "All",
    "Динамика": "Trends",
    # Security
    "не заполнено": "not filled in",
    "{points} из {max}": "{points} of {max}",
    "<b>🛡 Безопасность</b>\n\nНет подключённых платформ — подключи хотя бы одну: 🔌 Подключения.":
        "<b>🛡 Security</b>\n\nNo platforms are connected — connect at least one: 🔌 Connections.",
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
    "🧩 Мониторинги": "🧩 Monitors",
    "📅 Дни отчёта": "📅 Report days",
    "🕗 Время отчёта": "🕗 Report time",
    "🌍 Часовой пояс": "🌍 Time zone",
    "🗣 Язык / Language": "🗣 Language",
    "🗣 Язык: {lang}": "🗣 Language: {lang}",
    "русский": "Russian",
    "английский": "English",
    "🗣 Говорю по-английски, как твой Telegram. Перейти на русский — кнопка ниже.": "🗣 I speak English, as your Telegram does. To switch to Russian, use the button below.",
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
    "<b>Платформы</b> — подключаются в «🔌 Подключения»": "<b>Platforms</b> — connected in «🔌 Connections»",
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
    "🟠 Cookie установлен {age} {d} назад и скоро истечёт — пора обновить.":
        "🟠 The cookie was set {age} {d} ago and expires soon — time to renew it.",
    "✅ Число собирается само по cookie. Он установлен {age} {d} назад, "
    "напомню обновить через ~{left} {ld}.":
        "✅ The count is collected automatically via cookie. It was set {age} {d} ago; "
        "I will remind you to renew it in ~{left} {ld}.",
    "✅ Число собирается само по cookie, но срок его жизни я не вижу. "
    "Пришли cookie через /setcookie — и я напомню, когда его обновить.":
        "✅ The count is collected automatically via cookie, but I cannot see how long it lives. "
        "Send the cookie with /setcookie and I will remind you when to renew it.",
    "✏️ Число вводится вручную: cookie не задан.": "✏️ The count is entered by hand: no cookie is set.",
    "🔑 Прислать cookie": "🔑 Send the cookie",
    "🔑 Прислать токен": "🔑 Send the token",
    "<i>LinkedIn запрещает автоматический доступ, так что автосбор — на твой риск.</i>":
        "<i>LinkedIn forbids automated access, so automatic collection is at your own risk.</i>",
    "✏️ Ввести число вручную": "✏️ Enter count by hand",
    # Instagram
    "Аккаунт: {account}": "Account: {account}",
    "Последнее значение: {count} — собрано {when}": "Last value: {count} — collected {when}",
    "🟠 Токена нет: без него число не собирается.": "🟠 No token: without it the count is not collected.",
    "🟠 Instagram отклонил токен: отозван или истёк — пришли новый через /igtoken.":
        "🟠 Instagram rejected the token: revoked or expired — send a new one with /igtoken.",
    "✅ Число собирается само по токену. Он задан {age} {d} назад и бессрочный: "
    "если Meta его отзовёт, я скажу.":
        "✅ The count is collected automatically with the token. It was set {age} {d} ago and does not expire: "
        "if Meta revokes it, I will tell you.",
    "<i>Это официальный API: бот читает только публичные данные своего аккаунта.</i>":
        "<i>This is the official API: the bot reads only its own account's public data.</i>",
    # Manual LinkedIn input
    "\nСейчас: {count}": "\nNow: {count}",
    "<b>✏️ LinkedIn вручную</b>\n\nПришли число подписчиков одним сообщением, например 4520.{current}":
        "<b>✏️ LinkedIn by hand</b>\n\nSend the follower count in one message, e.g. 4520.{current}",
    "<b>✏️ Проверь число</b>\n\n{count} сильно отличается от прошлого значения "
    "{prev}. Возможно, это опечатка.":
        "<b>✏️ Check the number</b>\n\n{count} differs a lot from the previous value "
        "{prev}. It may be a typo.",
    "Сохранить {count}": "Save {count}",
    "✏️ Ввести заново": "✏️ Enter again",
    # Help
    # The icon dictionary (bot/monitors/__init__.py, ICON_LEGEND)
    "нужно действие сейчас": "act now",
    "звонит сразу, даже ночью и в тишине": "rings at once, even at night and while muted",
    "нужно действие, но не сегодня": "act, but not today",
    "без звука; ночью и в тишине ждёт сводки": "silent; at night and while muted it waits for the digest",
    "в порядке · снова работает · включено": "fine · works again · on",
    "не смог проверить": "could not check",
    "попробую ещё раз сам, тревогу не поднимаю": "I will try again myself, no alarm raised",
    "жду первой проверки": "waiting for the first check",
    "факт, который не проблема": "a fact, not a problem",
    "пункт чек-листа без ответа": "a checklist item without an answer",
    "/now — обновить данные": "/now — refresh data",
    "/week — динамика за неделю и график": "/week — the week's trends and a chart",
    "/security — безопасность аккаунтов": "/security — account security",
    "/settings — настройки": "/settings — settings",
    "/history [платформа] [дни] — таблица по дням, до 90 дней": "/history [platform] [days] — day-by-day table, up to 90 days",
    "/settime ЧЧ:ММ — время отчёта": "/settime HH:MM — report time",
    "/setquiet on|off — одна строка вместо отчёта, если за неделю без изменений":
        "/setquiet on|off — one line instead of the report when a week brought no change",
    "/connections — подключения: что собирается само, чему нужен токен или cookie":
        "/connections — connections: what is collected by itself, what needs a token or a cookie",
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
    "🔴 — похоже на взлом, новый вход, смена пароля, пропавший профиль, замолчавший почтовый воркер, "
    "опасный комментарий — придёт сразу, со звуком. Остальное пришлю сводкой, когда тишина закончится.":
        "🔴 — a likely hijack, a new sign-in, a changed password, a vanished profile, a silent mail worker, "
        "a dangerous comment — comes at once, with sound. Everything else comes as a digest when the silence ends.",
    "🌙 Накопилось, пока было тихо:": "🌙 Piled up while it was quiet:",
    "🌙 (продолжение)": "🌙 (continued)",
    "ℹ️ N — пункт целиком, с его кнопками.": "ℹ️ N — the item in full, with its buttons.",
    "Сводка — строка на событие, 🔴 и 🟠 первыми, у каждого время; «ℹ️ N» под ней присылает пункт целиком. "
    "Полные тексты храню {days} дн.":
        "The digest is a line per event, 🔴 and 🟠 first, each with its time; \"ℹ️ N\" under it sends the item "
        "in full. I keep the full texts for {days} days.",
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
    # the text-input conversations and the restore prompt
    "✅ Восстановить": "✅ Restore",
    # the reply keyboard, the home screen, 🔌 Подключения
    "🔄 Обновить": "🔄 Refresh",
    "сегодня {time}": "today {time}",
    "📤 <b>Отправки</b>": "📤 <b>Deliveries</b>",
    # 🔎 Репутация (bot/ui.py reputation_screen) and its inputs
    "🔎 Репутация": "🔎 Reputation",
    "<b>🔎 Репутация</b>": "<b>🔎 Reputation</b>",
    (
        "Раз в неделю — один отчёт: сколько раз тебя и твои продукты искали и сколько раз ИИ-ассистенты "
        "открывали твои страницы, рядом — рост подписчиков. "
        "Нечего сказать — молчу. Ключи — только на чтение; я их не показываю и в бэкап не кладу."
    ): (
        "Once a week, one report: how often you and your products were searched for and how often AI assistants "
        "opened your pages, next to the follower growth. "
        "Nothing to say — I stay silent. The keys are read-only; I never show them or put them in the backup."
    ),
    "🏷 Брендовые слова: {words}": "🏷 Brand words: {words}",
    "{icon} Брендовые слова не заданы — без них поиски не считаются":
        "{icon} No brand words yet — without them searches are not counted",
    "🏷 Брендовые слова": "🏷 Brand words",
    "Search Console — брендовые запросы": "Search Console — brand queries",
    "Вебмастер — брендовые запросы": "Yandex.Webmaster — brand queries",
    "Последний отчёт: {when}": "Last report: {when}",
    "Отчёта ещё не было.": "No report yet.",
    "📨 Отчёт сейчас": "📨 Report now",
    (
        "🏷 Пришли через запятую, как тебя и твои продукты ищут: имя и фамилию (обоими алфавитами, если так ищут), "
        "названия продуктов и сайтов — например: Семён Моргунов, Semyon Morgunov, FoundYou, Fingerprint. "
        "Регистр не важен; пробел внутри слова находит и слитное написание."
    ): (
        "🏷 Send, comma-separated, how people search for you and your products: your name (in both alphabets if "
        "people search that way), the names of the products and sites — for example: Semyon Morgunov, FoundYou, "
        "Fingerprint. Case does not matter; a space inside a word also finds it written as one."
    ),
    "{icon} {label} — не подключено: 🔌 Подключения → 🔎 Репутация":
        "{icon} {label} — not connected: 🔌 Connections → 🔎 Reputation",
    "🕒 Последний сбор: {when}": "🕒 Last collection: {when}",
    "🧭 Осталось настроить:": "🧭 Left to set up:",
    "часовой пояс — пока {tz}, выбери свой": "the time zone — {tz} for now, pick yours",
    "токен Instagram — без него число не собирается": "the Instagram token — no count without it",
    "LinkedIn — cookie для автосбора или первое число вручную":
        "LinkedIn — a cookie for automatic collection, or the first number by hand",
    "🌍 Выбрать часовой пояс": "🌍 Choose the time zone",
    "<b>🔌 Подключения</b>": "<b>🔌 Connections</b>",
    "Подключения": "Connections",
    "{icon} {label} — не подключено": "{icon} {label} — not connected",
    "📣 Пришли @username канала или ссылку t.me/…, а если канал закрытый — перешли сюда любой его пост. Сначала добавь меня в администраторы канала: так я увижу и подписчиков, и вступления с постами. Убрать канал, заданный здесь, — пришли «-».":
        "📣 Send the channel's @username or a t.me/… link; for a private channel, forward any of its posts here. "
        "Make me an admin of the channel first: that is how I see the followers, the joins and the posts. "
        "To remove a channel set here, send «-».",
    "📣 Ты сделал меня администратором канала «{title}». Подключить его? Я буду считать подписчиков и записывать вступления, посты и реакции.":
        "📣 You made me an admin of the channel «{title}». Connect it? I'll count the subscribers and record "
        "joins, posts and reactions.",
    "✅ Подключить канал": "✅ Connect the channel",
    "▶️ Шаг 1 из 2. Пришли id канала YouTube — 24 знака, начинается с UC (studio.youtube.com → Настройки → Канал → Расширенные настройки), или ссылку youtube.com/channel/UC…. Убрать канал, заданный здесь, — пришли «-».":
        "▶️ Step 1 of 2. Send the YouTube channel id — 24 characters, starts with UC "
        "(studio.youtube.com → Settings → Channel → Advanced settings), or a youtube.com/channel/UC… link. "
        "To remove a channel set here, send «-».",
    "📸 Пришли @username Instagram (аккаунт должен быть профессиональным: Creator или Business). Токен попрошу следующим шагом. Убрать аккаунт, заданный здесь, — пришли «-».":
        "📸 Send your Instagram @username (the account must be professional: Creator or Business). "
        "I will ask for the token as the next step. To remove an account set here, send «-».",
    "💼 Пришли ссылку на свой профиль LinkedIn вида https://www.linkedin.com/in/имя/. Убрать профиль, заданный здесь, — пришли «-».":
        "💼 Send the link to your LinkedIn profile, like https://www.linkedin.com/in/name/. "
        "To remove a profile set here, send «-».",
    "🟠 нужен токен": "🟠 a token is needed",
    "🟠 токен отклонён": "🟠 the token was rejected",
    "🟠 cookie отклонён, число вручную": "🟠 the cookie was rejected, the number by hand",
    "✏️ число вручную": "✏️ the number by hand",
    "🟠 подтверди первое число": "🟠 confirm the first number",
    "✅ собирается": "✅ collected",
    "⏳ первый сбор ещё не был": "⏳ no collection yet",
    # bot/callbacks.py — the rows under alerts and reports
    "🏠 Главная": "🏠 Home",
    "💬 Комментарии": "💬 Comments",
    "🔌 Подключения": "🔌 Connections",
    "🔕 Тихо 8 ч": "🔕 Quiet for 8 h",
    "⚙️ Не присылать такие": "⚙️ Stop sending these",
    # The three buttons under the input field (BOT_PRINCIPLES §2) and the greeting
    "📖 Что я умею": "📖 What I do",
    "❓ Значки": "❓ Icons",
    "✖️ Отмена": "✖️ Cancel",
    "Всё — кнопками ниже": "Everything is on the buttons below",
    "👋 Привет! Я слежу за подписчиками и безопасностью твоих аккаунтов.\n\n"
    "Пока всё в порядке, я молчу. О падении подписчиков, накрутке, смене названия, ссылок "
    "или админов и о письмах про новые входы пишу сразу, а сводку присылаю по расписанию.\n\n"
    "Под полем ввода — три кнопки: «{home}» — главный экран, «{about}» — что я делаю и все команды, "
    "«{icons}» — что значат значки и что звонит.":
        "👋 Hi! I keep an eye on your accounts' followers and security.\n\n"
        "While everything is fine, I stay quiet. A drop in followers, fake growth, a changed name, "
        "links or admins, and emails about new sign-ins I report right away; the summary comes on schedule.\n\n"
        "Three buttons under the input field: \"{home}\" — the home screen, \"{about}\" — what I do and every "
        "command, \"{icons}\" — what the icons mean and what rings.",
    "Это не похоже на число. Пришли только цифры, например 4520, или нажми «✖️ Отмена».":
        "That does not look like a number. Send digits only, e.g. 4520, or press \"✖️ Cancel\".",
    # «🔕 Помолчать…» on the home screen
    "🔕 Помолчать…": "🔕 Mute…",
    "<b>🔕 Помолчать</b>": "<b>🔕 Mute</b>",
    "Тихие часы на каждую ночь — ⚙️ Настройки → 🔔 Когда писать. Команда: /mute 8h, снять — /unmute.":
        "Quiet hours for every night — ⚙️ Settings → 🔔 When to write. Command: /mute 8h, lift it with /unmute.",
    # «📖 Что я умею»
    "<b>📖 Что я умею</b>": "<b>📖 What I do</b>",
    "Пока всё в порядке — молчу; о проблеме пишу сразу, а сводку присылаю по расписанию. "
    "Сети, ключи и расписание — кнопками, без правки файлов.":
        "While everything is fine, I stay quiet; I report a problem right away, and the summary comes on schedule. "
        "Networks, keys and the schedule are set with buttons — no files to edit.",
    "<b>Подписчики</b>": "<b>Followers</b>",
    "• Каждый день собираю подписчиков Telegram, YouTube, Instagram и LinkedIn — тех сетей, что подключены.":
        "• Every day I collect the followers of Telegram, YouTube, Instagram and LinkedIn — the networks connected.",
    "• Отчёт по расписанию: за день, неделю и месяц, график за 30 дней, лидер недели, прогноз до круглого "
    "числа; 1-го числа — итоги месяца.":
        "• A report on schedule: the day, the week and the month, a 30-day chart, the week's leader, a forecast "
        "to the next milestone; on the 1st — the month's results.",
    "• Сразу пишу о падении подписчиков, наплыве ботов, круглом числе и о том, что сбор не работает.":
        "• I write at once about a drop in followers, a bot influx, a milestone and a collection that fails.",
    "• 📣 Канал — подписки и отписки, откуда пришли, посты и реакции.":
        "• 📣 Channel — joins and leaves, where they came from, posts and reactions.",
    "<b>Безопасность</b>": "<b>Security</b>",
    "• Каждые 30 минут сверяю профиль: название, описание и ссылки, аватарку, админов и владельца, "
    "число видео и публикаций.":
        "• Every 30 minutes I compare the profile: the title, the description and its links, the avatar, "
        "the admins and the owner, the number of videos and posts.",
    "• Комментарии канала, если есть ключ Claude: карточка с кнопками на то, за что блокируют группу. "
    "Сам ничего не удаляю.":
        "• The channel's comments, with a Claude key: a card with buttons for what gets a group blocked. "
        "I delete nothing myself.",
    "• Чек-лист 2FA и паролей — балл в отчёте. Пароли не спрашиваю и не храню.":
        "• A 2FA and password checklist — a score in the report. I never ask for or keep a password.",
    "<b>Сам за собой</b>": "<b>Looking after myself</b>",
    "• По воскресеньям присылаю бэкап базы (и по кнопке «📦 Бэкап сейчас» в настройках). Пришли файл "
    "обратно — верну историю, уже собранное не перезапишется.":
        "• On Sundays I send a database backup (and on \"📦 Backup now\" in the settings). Send the file "
        "back — I bring the history back without overwriting what is already collected.",
    "• После обновления пишу «🔄 Бот обновился», по воскресеньям — об уязвимостях в своих пакетах.":
        "• After an update I write \"🔄 The bot has been updated\", on Sundays — about vulnerabilities in my packages.",
    "• Если обновление поменяло, когда и как я пишу, а ты — нет, скажу об этом один раз, с кнопкой на настройку.":
        "• If an update changed when and how I write while you didn't, I say so once, with a button to the setting.",
    "<b>Где что</b>": "<b>Where things are</b>",
    "🏠 Главная — отчёт, «🔄 Обновить данные», 📈 Динамика, 🛡 Безопасность, 📣 Канал, 🔌 Подключения, "
    "«🔕 Помолчать…», ⚙️ Настройки.":
        "🏠 Home — the report, \"🔄 Refresh data\", 📈 Trends, 🛡 Security, 📣 Channel, 🔌 Connections, "
        "\"🔕 Mute…\", ⚙️ Settings.",
    "❓ Значки — что значат значки и что звонит. Под тревогами — кнопки туда, где разбираться.":
        "❓ Icons — what the icons mean and what rings. Under the alerts — buttons to where to look into them.",
    "<b>Команды</b> — короткие пути к тому же, что на кнопках:": "<b>Commands</b> — shortcuts to what the buttons do:",
    "/start, /stats — главная": "/start, /stats — home",
    "/setday <дни> — дни отчёта: sat, mon-fri, mon,thu, daily": "/setday <days> — report days: sat, mon-fri, mon,thu, daily",
    "/settz <пояс> — часовой пояс, например Europe/Moscow": "/settz <zone> — time zone, e.g. Europe/Moscow",
    "/mute <время> — помолчать: 1h, 8h, 1d (по умолчанию 8h); /unmute — снять":
        "/mute <time> — pause notifications: 1h, 8h, 1d (default 8h); /unmute — resume",
    "/linkedin <число> — ввести LinkedIn вручную": "/linkedin <count> — enter LinkedIn by hand",
    "/setcookie [li_at] — cookie LinkedIn для автосбора; без значения — спрошу его следующим сообщением":
        "/setcookie [li_at] — the LinkedIn cookie for automatic collection; without the value I ask for it next",
    "/cookieage — сколько живёт cookie LinkedIn": "/cookieage — how old the LinkedIn cookie is",
    "/igtoken [токен] — токен Instagram для автосбора; без значения — спрошу его следующим сообщением":
        "/igtoken [token] — the Instagram token for automatic collection; without the value I ask for it next",
    "/restore — вернуть историю из бэкапа: ответом на файл или подписью к нему":
        "/restore — bring the history back from a backup: as a reply to the file or its caption",
    "/cancel — выйти из шага ввода": "/cancel — leave an input step",
    "/help — этот экран": "/help — this screen",
    # «❓ Значки»
    "<b>❓ Значки</b>": "<b>❓ Icons</b>",
    "Значок говорит, насколько срочно; слова — что случилось. Значки одни на тревогах, экранах и в отчётах.":
        "The icon says how urgent; the words say what happened. The icons are the same in alerts, screens and reports.",
    "<b>Что звонит</b>": "<b>What rings</b>",
    "Звонит только 🔴 — даже ночью, в тихие часы и в «🔕 Помолчать». Остальное приходит без звука, "
    "а в тихие часы и в тишине ждёт и приходит одной сводкой. Отчёт по расписанию — тоже без звука.":
        "Only 🔴 rings — even at night, in quiet hours and during \"🔕 Mute\". Everything else arrives silently, "
        "and in quiet hours or while muted it waits and comes as one digest. The scheduled report is silent too.",
    "Помолчать — «🔕 Помолчать…» на главной или /mute 8h; тихие часы — ⚙️ Настройки → 🔔 Когда писать. "
    "«⚙️ Не присылать такие» под тревогой выключает такие уведомления.":
        "To mute — \"🔕 Mute…\" on the home screen or /mute 8h; quiet hours — ⚙️ Settings → 🔔 When to write. "
        "\"⚙️ Stop sending these\" under an alert switches such notifications off.",
    "/icons — значки: что значат и что звонит": "/icons — the icons: what they mean and what rings",
    # ⏱ Сторож (bot/watchdog.py, bot/ui.py)
    "⏱ Сторож": "⏱ Watchdog",
    "{icon} ⏱ Сторож — не подключён: если я остановлюсь, никто не скажет":
        "{icon} ⏱ Watchdog — not connected: if I stop, nobody will tell you",
    "{icon} ⏱ Сторож — {who}: {reason}": "{icon} ⏱ Watchdog — {who}: {reason}",
    "{icon} ⏱ Сторож — {who}, отметка {when}": "{icon} ⏱ Watchdog — {who}, last ping {when}",
    "{icon} ⏱ Сторож — {who}, первая отметка после ежедневного сбора":
        "{icon} ⏱ Watchdog — {who}, the first ping after the daily collection",
    "<b>⏱ Сторож</b>": "<b>⏱ Watchdog</b>",
    "Ссылка задана здесь, в чате; адрес я не показываю — по нему можно отмечаться за меня.":
        "The link was set here, in the chat; I do not show the address — it lets anyone ping in my name.",
    "Если я остановлюсь — упадёт сервер, кончится место, отзовут токен бота — написать об этом я уже не смогу. "
    "Сторож — сервис, у которого я отмечаюсь после каждого ежедневного сбора; не отметился вовремя — он пишет тебе сам.":
        "If I stop — the server goes down, the disk fills up, the bot token is revoked — I can no longer tell you. "
        "A watchdog is a service I check in with after every daily collection; when I miss it, it writes to you itself.",
    "<b>Как подключить</b> (бесплатно, 2 минуты):": "<b>How to connect it</b> (free, 2 minutes):",
    "🔗 Прислать ссылку": "🔗 Send the link",
    "🔄 Проверить снова": "🔄 Check again",
    "⏏ Отключить": "⏏ Disconnect",
    "✅ Да, отключить": "✅ Yes, disconnect",
    "check не найден — удалён или ссылка скопирована не целиком": "check not found — deleted, or the link was copied in part",
    "отвечает ошибкой {status}": "answers with error {status}",
    "не ответил за 10 с": "did not answer within 10 s",
    "не удаётся подключиться — сеть или DNS": "cannot connect — network or DNS",
    "не отвечает": "does not answer",
    "TofsDevOps не принял отметку": "TofsDevOps did not take the ping",
    "С чего начать:\n1. 🔌 Подключения → «➕» у своей сети.\n2. 🌍 Часовой пояс — чтобы отчёт приходил в твоё утро.\n3. ⏱ Сторож — после первой сети я предложу его сам: он скажет, если я остановлюсь.":
        "Where to start:\n1. 🔌 Connections → «➕» next to your network.\n2. 🌍 Time zone — so the report comes in your morning.\n3. ⏱ Watchdog — I will offer it myself after the first network: it tells you if I stop.",
    "Начнём: выбери сеть, которую подключить первой. Проще всего — Telegram-канал: достаточно сделать меня его админом.":
        "Let's start: pick the network to connect first. The easiest is a Telegram channel: just make me its admin.",
    "сеть — пока ни одна не подключена":
        "a network — none is connected yet",
    "🔌 Подключить сеть":
        "🔌 Connect a network",
    "📸 Токен Instagram":
        "📸 Instagram token",
    "💼 Первое число LinkedIn":
        "💼 First LinkedIn count",
    "«➕» подключает сеть прямо здесь, «✏️» меняет или убирает её.":
        "«➕» connects a network right here, «✏️» changes or removes it.",
    "Ссылка задана в настройках хостинга (HEALTHCHECK_URL). Пришли другую — она её заменит.":
        "The link is set in the hosting settings (HEALTHCHECK_URL). Send another one and it replaces it.",
    "1. Зарегистрируйся на healthchecks.io и нажми «Add Check».":
        "1. Sign up at healthchecks.io and press «Add Check».",
    "2. В «Period» поставь 1 day, в «Grace Time» — 3 hours: сторож подождёт 3 часа после пропущенной отметки и только потом напишет тебе.":
        "2. Set «Period» to 1 day and «Grace Time» to 3 hours: the watchdog waits 3 hours after a missed check-in and only then writes to you.",
    "3. Скопируй ссылку вида https://hc-ping.com/… и нажми «🔗 Прислать ссылку» — я сразу отмечусь по ней и скажу, дошло ли.":
        "3. Copy the link that looks like https://hc-ping.com/… and press «🔗 Send the link» — I check in on it at once and tell you whether it got through.",
    "Ссылка из TofsDevOps (задача «раз в сутки») тоже подходит — тогда на его главном экране появятся строки по сетям.":
        "A link from TofsDevOps (a «once a day» job) works too — then its home screen gets a line per network.",
    "Пошагово: {guide}":
        "Step by step: {guide}",
    "Cloudflare — сколько раз ChatGPT, Claude, Perplexity и другие ассистенты открывали твои страницы":
        "Cloudflare — how many times ChatGPT, Claude, Perplexity and other assistants opened your pages",
    "Нужна, только если у тебя есть свой сайт — в Google Search Console, Яндекс.Вебмастере или Cloudflare. Без сайта этот раздел можно пропустить.":
        "Only for a site of your own — in Google Search Console, Yandex Webmaster or Cloudflare. Without a site you can skip this section.",
    "<b>⏏ Отключить сторожа?</b>\n\nЯ перестану отмечаться по ссылке из чата. Саму проверку на healthchecks.io поставь на паузу, иначе она напишет, что я пропал.":
        "<b>⏏ Disconnect the watchdog?</b>\n\nI will stop checking in with the link from the chat. Pause the check itself on healthchecks.io, or it will write that I am gone.",
    "Буду отмечаться по ссылке из настроек хостинга.":
        "I will check in with the link from the hosting settings.",
    " · сборка {commit}":
        " · build {commit}",
    "Версия {version}":
        "Version {version}",
    "<b>Автосбор</b>: нажми «🔑 Прислать cookie» и пришли cookie li_at — строку, по которой LinkedIn узнаёт, что ты вошёл. Я проверю её и сразу удалю сообщение.":
        "<b>Automatic collection</b>: press «🔑 Send the cookie» and send the li_at cookie — the string by which LinkedIn knows you are signed in. I will check it and delete the message right away.",
    "Нужно: профессиональный аккаунт (Автор или Бизнес) и около 15 минут в кабинете Meta для разработчиков. Пошагово: {guide}":
        "You need a professional account (Creator or Business) and about 15 minutes in Meta's developer dashboard. Step by step: {guide}",
    "✅ Число собирается само по токену из настроек хостинга.":
        "✅ The number is collected by itself with the token from the hosting settings.",
    "Когда токен готов, нажми «🔑 Прислать токен» и пришли его одним сообщением (то же — командой /igtoken). Я проверю его и сразу удалю сообщение.":
        "When the token is ready, press «🔑 Send the token» and send it in one message (the /igtoken command does the same). I will check it and delete the message right away.",
    "🔑 Ключ Google для Search Console, только на чтение: в Google Cloud заводится служебный аккаунт с файлом ключа, а в Search Console ему открывают доступ к сайту. Пошагово: {guide}\nПришли файл или его текст одним сообщением — я проверю ключ и сразу удалю сообщение.":
        "🔑 A Google key for Search Console, read-only: Google Cloud gets a service account with a key file, and Search Console gives it access to your site. Step by step: {guide}\nSend the file or its text in one message — I will check the key and delete the message right away.",
    "🔑 Токен Яндекс.Вебмастера, только на чтение: делается за пару минут на oauth.yandex.ru и живёт полгода — когда истечёт, отчёт скажет. Пошагово: {guide}\nПришли его одним сообщением — я проверю и сразу удалю.":
        "🔑 A Yandex Webmaster token, read-only: made in a couple of minutes at oauth.yandex.ru, it lives half a year — the report says when it expires. Step by step: {guide}\nSend it in one message — I will check it and delete it right away.",
    "🔑 Токен Cloudflare, только на чтение: dash.cloudflare.com → My Profile → API Tokens → Create Token, права «Zone Read» и «Analytics Read». Пошагово: {guide}\nПришли токен одним сообщением — я проверю его и сразу удалю сообщение.":
        "🔑 A Cloudflare token, read-only: dash.cloudflare.com → My Profile → API Tokens → Create Token, permissions «Zone Read» and «Analytics Read». Step by step: {guide}\nSend the token in one message — I will check it and delete the message right away.",
    "🔑 Шаг 2 из 2. Ключ YouTube бесплатный, делается за 5 минут в Google Cloud: {guide}\nПришли его одним сообщением — я проверю его на твоём канале и сразу удалю сообщение.":
        "🔑 Step 2 of 2. A YouTube key is free and takes 5 minutes in Google Cloud: {guide}\nSend it in one message — I will check it on your channel and delete the message right away.",
    "🔑 Пришли cookie li_at одним сообщением. Это длинная строка, по которой LinkedIn узнаёт, что ты вошёл. На компьютере в Chrome: linkedin.com → правый клик → «Просмотреть код» → Application → Cookies → linkedin.com → li_at → Value. Пошагово: {guide}\nЯ проверю его и сразу удалю сообщение.":
        "🔑 Send the li_at cookie in one message. It is a long string by which LinkedIn knows you are signed in. On a computer, in Chrome: linkedin.com → right click → «Inspect» → Application → Cookies → linkedin.com → li_at → Value. Step by step: {guide}\nI will check it and delete the message right away.",
    "🔑 Пришли токен Instagram одним сообщением: его выдаёт кабинет Meta для разработчиков, кнопка «Generate token». Пошагово: {guide}\nЯ проверю его и сразу удалю сообщение.":
        "🔑 Send the Instagram token in one message: Meta's developer dashboard issues it, the «Generate token» button. Step by step: {guide}\nI will check it and delete the message right away.",
    "🌍 Пришли город или название пояса одним сообщением: Ташкент, Berlin, Asia/Tashkent.":
        "🌍 Send a city or a zone name in one message: Tashkent, Berlin, Asia/Tashkent.",
    "🔗 Пришли ссылку сторожа одним сообщением: https://hc-ping.com/… из healthchecks.io или ссылку из TofsDevOps. Я сразу отмечусь по ней, скажу, дошло ли, и удалю сообщение.":
        "🔗 Send the watchdog link in one message: https://hc-ping.com/… from healthchecks.io or a link from TofsDevOps. I will check in on it at once, tell you whether it got through and delete the message.",
    "Не знаю такой пояс. Пришли город по-английски (Berlin) или название вида Europe/Berlin — или нажми «✖️ Отмена».":
        "I do not know that zone. Send a city in English (Berlin) or a name like Europe/Berlin — or press «✖️ Cancel».",
    "🔴 у меня — это: похоже на взлом (новый админ или владелец, ссылка в описании, пропавшие видео или публикации, новый вход, смена пароля, почты или 2FA), профиль не читается, проверка писем молчит, комментарий, за который блокируют группу. 🟠 — истёкший cookie, отклонённый токен, сбои сбора, падение подписчиков, смена названия или аватарки.":
        "🔴 here means: looks like a hijack (a new admin or owner, a link in the description, vanished videos or posts, a new sign-in, a changed password, email or 2FA), an unreadable profile, a silent email check, a comment the group gets blocked for. 🟠 — an expired cookie, a rejected token, collection failures, a drop in followers, a new title or avatar.",
    "• Письма безопасности, если они подключены: новый вход, смена пароля, почты или 2FA, код входа.":
        "• Security emails, if they are connected: a new sign-in, a changed password, email or 2FA, a login code.",
    "Платно: каждый комментарий — запрос к Claude по твоему ключу.":
        "Paid: every comment is a request to Claude on your key.",
    "Цену модели {model} я не знаю — после первых проверок покажу израсходованные токены.":
        "I don't know the price of {model} — after the first checks I will show the tokens spent.",
    "Около {usd} за комментарий на {model}.":
        "About {usd} per comment on {model}.",
    "За {days} дней: {checks}, ≈ {usd} ({models}).":
        "Last {days} days: {checks}, ≈ {usd} ({models}).",
    "За {days} дней: {checks}.":
        "Last {days} days: {checks}.",
    "{model}: {tokens_in} токенов на входе, {tokens_out} на выходе — цену этой модели я не знаю.":
        "{model}: {tokens_in} input tokens, {tokens_out} output — I don't know this model's price.",
    "<i>По ценам Anthropic на {date}; точный счёт — на console.anthropic.com.</i>":
        "<i>At Anthropic's prices of {date}; the exact bill is on console.anthropic.com.</i>",
    "Не подключено: нужен ключ Claude API и Telegram-канал с группой обсуждения. Тогда я буду смотреть каждый комментарий в группе обсуждения и присылать карточку с кнопками на запрещённый контент.":
        "Not connected: it needs a Claude API key and a Telegram channel with a discussion group. Then I look at every comment in the discussion group and send a card with buttons for prohibited content.",
    "Ключ Claude есть; осталось подключить Telegram-канал с группой обсуждения: 🔌 Подключения → «➕ Telegram».":
        "The Claude key is there; what is left is a Telegram channel with a discussion group: 🔌 Connections → «➕ Telegram».",
    "задан в чате":
        "set in the chat",
    "из настроек хостинга":
        "from the hosting settings",
    "🔑 Ключ Claude: {source}":
        "🔑 Claude key: {source}",
    "✏️ Ключ Claude":
        "✏️ Claude key",
    "🔑 Прислать ключ Claude":
        "🔑 Send the Claude key",
    "Лимит: {n} {checks} в сутки — волна спама не станет счётом.":
        "Limit: {n} {checks} a day — a spam wave will not become a bill.",
    "Лимит: нет — каждая проверка оплачивается, сколько бы их ни было.":
        "Limit: none — every check is paid for, however many there are.",
    "без лимита":
        "no limit",
    "{icon} 💬 Комментарии — ключ Claude задан":
        "{icon} 💬 Comments — the Claude key is set",
    "{icon} 💬 Комментарии — нужен ключ Claude (платный)":
        "{icon} 💬 Comments — needs a Claude key (paid)",
    "🔑 Пришли ключ Claude API одним сообщением. Где взять: console.anthropic.com → API Keys → Create Key. Совет: заведи для бота отдельное рабочее пространство (Workspace) с лимитом расходов — тогда волна спама не станет счётом. Пошагово: {guide}\nЯ проверю ключ и сразу удалю сообщение. Убрать ключ, заданный здесь, — пришли «-».":
        "🔑 Send the Claude API key in one message. Where to get it: console.anthropic.com → API Keys → Create Key. Tip: give the bot a Workspace of its own with a spend limit — then a spam wave will not become a bill. Step by step: {guide}\nI will check the key and delete the message right away. To remove a key set here, send «-».",
    "• После обновления пишу «🔄 Бот обновился». Упавший деплой и уязвимости в пакетах — проверка «Для разработчика» в 🧩 Мониторингах: она для того, кто ведёт код бота.":
        "• After an update I say «🔄 The bot has been updated». A failed deploy and vulnerabilities in the packages are the check «For the developer» in 🧩 Monitors: it is for whoever maintains the bot's code.",
    "{icon} ✉️ Письма безопасности — подключены":
        "{icon} ✉️ Security emails — connected",
    "{icon} ✉️ Письма безопасности — не подключены":
        "{icon} ✉️ Security emails — not connected",
    "✉️ Письма безопасности":
        "✉️ Security emails",
    "{icon} не принимает пароль приложения":
        "{icon} does not take the app password",
    "{icon} не смог проверить ({when})":
        "{icon} could not check ({when})",
    "{icon} проверен {when}":
        "{icon} checked {when}",
    "{icon} первая проверка — в течение 5 минут":
        "{icon} first check within 5 minutes",
    "{icon} не отвечает":
        "{icon} not answering",
    "{icon} не ответил на последний опрос":
        "{icon} did not answer the last poll",
    "{icon} отвечает":
        "{icon} answering",
    "<b>✉️ Письма безопасности</b>":
        "<b>✉️ Security emails</b>",
    "Письма «новый вход», «пароль изменён», «добавлен ключ» от соцсетей, GitHub, Microsoft и Яндекса — сюда, в течение 5 минут. Тревожные звонят даже ночью.":
        "«New sign-in», «password changed», «key added» emails from the social networks, GitHub, Microsoft and Yandex — here, within 5 minutes. The alarming ones ring even at night.",
    "📮 Ящик: {address} — {state}":
        "📮 Mailbox: {address} — {state}",
    "✏️ Ящик":
        "✏️ Mailbox",
    "{icon} 📮 Отдельный ящик — не подключён":
        "{icon} 📮 A separate mailbox — not connected",
    "📮 Отдельный ящик (просто)":
        "📮 A separate mailbox (simple)",
    "☁️ Воркер: {host} — {state}":
        "☁️ Worker: {host} — {state}",
    "✏️ Воркер":
        "✏️ Worker",
    "{icon} ☁️ Свой воркер на Cloudflare — не подключён":
        "{icon} ☁️ Your own Cloudflare worker — not connected",
    "☁️ Свой воркер на Cloudflare (для продвинутых)":
        "☁️ Your own Cloudflare worker (advanced)",
    "⬜ Проверка писем выключена: ⚙️ Настройки → 🧩 Мониторинги.":
        "⬜ The email check is switched off: ⚙️ Settings → 🧩 Monitors.",
    "Как это устроено: заведи отдельный ящик только для бота, в основном ящике настрой фильтр, который пересылает туда уведомления безопасности, а мне дай пароль приложения от отдельного ящика. Пошагово: {guide}":
        "How it works: make a separate mailbox just for the bot, set a filter in your main mailbox that forwards the security notifications there, and give me an app password of the separate one. Step by step: {guide}",
    "⏏ Отключить ящик":
        "⏏ Disconnect the mailbox",
    "⏏ Отключить воркер":
        "⏏ Disconnect the worker",
    "<b>⏏ Отключить ящик?</b>\n\nЯ перестану читать отдельный ящик и забуду пароль приложения. Сам пароль удали в настройках аккаунта (Gmail: myaccount.google.com/apppasswords; Яндекс: id.yandex.ru → Безопасность → Пароли приложений), а фильтр пересылки — в основном ящике.":
        "<b>⏏ Disconnect the mailbox?</b>\n\nI will stop reading the separate mailbox and forget the app password. Delete the password itself in the account's settings (Gmail: myaccount.google.com/apppasswords; Yandex: id.yandex.ru → Security → App passwords), and the forwarding filter in your main mailbox.",
    "<b>⏏ Отключить воркер?</b>\n\nЯ перестану забирать письма у воркера, заданного в чате. Если воркер задан в настройках хостинга — буду забирать у него.":
        "<b>⏏ Disconnect the worker?</b>\n\nI will stop fetching mail from the worker set in the chat. If a worker is set in the hosting settings, I will fetch from that one.",
    "📮 Шаг 1 из 2. Пришли адрес отдельного ящика для бота — Gmail или Яндекс, например my.alerts.bot@gmail.com. Заведи новый, не основной: пароль приложения даёт доступ ко всему ящику. Пошагово: {guide}\nУбрать ящик, заданный здесь, — пришли «-».":
        "📮 Step 1 of 2. Send the address of a separate mailbox for the bot — Gmail or Yandex, for example my.alerts.bot@gmail.com. Make a new one, not your main one: an app password opens the whole mailbox. Step by step: {guide}\nTo remove a mailbox set here, send «-».",
    "📮 Шаг 2 из 2. Пришли пароль приложения от этого ящика одним сообщением.\nGmail: включи двухэтапную проверку → myaccount.google.com/apppasswords → создай пароль.\nЯндекс: id.yandex.ru → Безопасность → Пароли приложений → Почта, и в настройках почты разреши почтовые программы (IMAP).\nЯ проверю вход и сразу удалю сообщение.":
        "📮 Step 2 of 2. Send an app password of this mailbox in one message.\nGmail: turn on 2-Step Verification → myaccount.google.com/apppasswords → create a password.\nYandex: id.yandex.ru → Security → App passwords → Mail, and allow email clients (IMAP) in the mail settings.\nI will check the sign-in and delete the message right away.",
    "☁️ Шаг 1 из 2. Пришли адрес своего почтового воркера на Cloudflare, вида https://socialbot-mail.<аккаунт>.workers.dev. Это путь для продвинутых: нужен свой домен в Cloudflare. Пошагово: {guide}\nУбрать воркер, заданный здесь, — пришли «-».":
        "☁️ Step 1 of 2. Send the address of your own mail worker on Cloudflare, like https://socialbot-mail.<account>.workers.dev. This is the advanced way: it needs a domain of your own on Cloudflare. Step by step: {guide}\nTo remove a worker set here, send «-».",
    "🔑 Шаг 2 из 2. Пришли токен, который ты задал воркеру при установке, одним сообщением — я проверю его запросом к воркеру и сразу удалю сообщение.":
        "🔑 Step 2 of 2. Send the token you gave the worker when you set it up, in one message — I will check it with a request to the worker and delete the message right away.",
}

# Russian singular → (English singular, English plural).
PLURALS: dict[str, tuple[str, str]] = {
    "проверка": ("check", "checks"),
    "дн.": ("day", "days"),
    "день": ("day", "days"),
    "час": ("hour", "hours"),
    "минута": ("minute", "minutes"),
}

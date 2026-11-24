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
    "🟠 Токена нет: без него число не собирается.": "🟠 No token: without it the count is not collected.",
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
    (
        "🔴 у меня — это: похоже на взлом (новый админ или владелец, ссылка в описании, пропавшие видео "
        "или публикации, новый вход, смена пароля, почты или 2FA), профиль не читается, почтовый воркер "
        "молчит, комментарий, за который блокируют группу. 🟠 — истёкший cookie, отклонённый токен, сбои "
        "сбора, падение подписчиков, смена названия или аватарки."
    ): (
        "🔴 here means: looks like a hijack (a new admin or owner, a link in the description, vanished videos "
        "or posts, a new sign-in, a changed password, email or 2FA), an unreadable profile, a silent mail "
        "worker, a comment the group gets blocked for. 🟠 — an expired cookie, a rejected token, collection "
        "failures, a drop in followers, a new title or avatar."
    ),
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
    '🔑 Ключ сервисного аккаунта Google, только на чтение:\n1. console.cloud.google.com → новый проект → APIs & Services → включи «Google Search Console API».\n2. IAM & Admin → Service Accounts → Create; роли не нужны. Keys → Add key → JSON — скачается файл.\n3. В Search Console у каждого ресурса: Настройки → Пользователи и разрешения → Добавить пользователя → e-mail сервисного аккаунта (client_email в файле), разрешение «Ограниченный»; если ключ не увидит ресурс — «Полный».\nПришли файл или его текст одним сообщением — я проверю ключ и сразу удалю сообщение.':
        "🔑 A Google service account key, read-only:\n1. console.cloud.google.com → a new project → APIs & Services → enable «Google Search Console API».\n2. IAM & Admin → Service Accounts → Create; no roles needed. Keys → Add key → JSON — a file is downloaded.\n3. In Search Console, for each property: Settings → Users and permissions → Add user → the service account's e-mail (client_email in the file), permission «Restricted»; if the key does not see the property — «Full».\nSend the file or its text in one message — I'll check the key and delete the message at once.",
    '🔑 OAuth-токен Яндекс.Вебмастера, только на чтение:\n1. oauth.yandex.ru/client/new → «Веб-сервисы», Redirect URI https://oauth.yandex.ru/verification_code, доступ «Яндекс.Вебмастер: получение информации о сайтах» (webmaster:hostinfo).\n2. Открой https://oauth.yandex.ru/authorize?response_type=token&client_id=<ClientID приложения> и скопируй токен.\nТокен живёт полгода — когда истечёт, отчёт скажет. Пришли его одним сообщением — я проверю и сразу удалю.':
        "🔑 A Yandex.Webmaster OAuth token, read-only:\n1. oauth.yandex.ru/client/new → «Web services», Redirect URI https://oauth.yandex.ru/verification_code, access «Yandex.Webmaster: getting site information» (webmaster:hostinfo).\n2. Open https://oauth.yandex.ru/authorize?response_type=token&client_id=<the app's ClientID> and copy the token.\nThe token lives six months — when it expires, the report says so. Send it in one message — I'll check it and delete it at once.",
    '🔑 API-токен Cloudflare, только на чтение:\ndash.cloudflare.com → My Profile → API Tokens → Create Token → Custom token. Права: Zone → Zone → Read и Zone → Analytics → Read; Zone Resources — твои зоны.\nПришли токен одним сообщением — я проверю его пробным запросом и сразу удалю сообщение.':
        "🔑 A Cloudflare API token, read-only:\ndash.cloudflare.com → My Profile → API Tokens → Create Token → Custom token. Permissions: Zone → Zone → Read and Zone → Analytics → Read; Zone Resources — your zones.\nSend the token in one message — I'll check it with a test query and delete the message at once.",
    "Search Console — брендовые запросы": "Search Console — brand queries",
    "Вебмастер — брендовые запросы": "Yandex.Webmaster — brand queries",
    "Cloudflare — запросы ИИ-ассистентов (по user-agent: ChatGPT-User, Claude-User, Perplexity-User…)":
        "Cloudflare — AI assistant requests (by user agent: ChatGPT-User, Claude-User, Perplexity-User…)",
    "Последний отчёт: {when}": "Last report: {when}",
    "Отчёта ещё не было.": "No report yet.",
    "📨 Отчёт сейчас": "📨 Report now",
    (
        "🏷 Пришли через запятую, как тебя и твои продукты ищут: имя и фамилию (обоими алфавитами, если так ищут), "
        "названия продуктов и сайтов — например: Семён Моргунов, Semyon Morgunov, FoundYou, Good Pass. "
        "Регистр не важен; пробел внутри слова находит и слитное написание."
    ): (
        "🏷 Send, comma-separated, how people search for you and your products: your name (in both alphabets if "
        "people search that way), the names of the products and sites — for example: Semyon Morgunov, FoundYou, "
        "Good Pass. Case does not matter; a space inside a word also finds it written as one."
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
    "{icon} {label} — не подключено: {needs} в .env": "{icon} {label} — not connected: {needs} in .env",
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
    "Не знаю такой часовой пояс. Нужно название из базы IANA, например Europe/Moscow, или нажми «✖️ Отмена».":
        "I do not know that time zone. It needs a name from the IANA database, e.g. Europe/Moscow, "
        "or press \"✖️ Cancel\".",
    # «🔕 Помолчать…» on the home screen
    "🔕 Помолчать…": "🔕 Mute…",
    "<b>🔕 Помолчать</b>": "<b>🔕 Mute</b>",
    "Тихие часы на каждую ночь — ⚙️ Настройки → 🔔 Когда писать. Команда: /mute 8h, снять — /unmute.":
        "Quiet hours for every night — ⚙️ Settings → 🔔 When to write. Command: /mute 8h, lift it with /unmute.",
    # «📖 Что я умею»
    "<b>📖 Что я умею</b>": "<b>📖 What I do</b>",
    "Пока всё в порядке — молчу; о проблеме пишу сразу, а сводку присылаю по расписанию. "
    "Сети подключаются в .env, остальное — кнопками.":
        "While everything is fine, I stay quiet; I report a problem right away, and the summary comes on schedule. "
        "Networks are connected in .env, everything else with buttons.",
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
    "• Письма безопасности, если подключён почтовый воркер: новый вход, смена пароля, почты или 2FA, код входа.":
        "• Security emails, with the mail worker connected: a new sign-in, a changed password, email or 2FA, "
        "a login code.",
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
    "Сети включаются в .env и перезапуском бота; токен Instagram, cookie LinkedIn и сторож — кнопками здесь.":
        "Networks are switched on in .env and by restarting the bot; the Instagram token, the LinkedIn cookie "
        "and the watchdog — with the buttons here.",
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
    "Ссылка — из HEALTHCHECK_URL в .env. Пришли другую — она заменит переменную.":
        "The link comes from HEALTHCHECK_URL in .env. Send another one — it takes the variable's place.",
    "Если я остановлюсь — упадёт сервер, кончится место, отзовут токен бота — написать об этом я уже не смогу. "
    "Сторож — сервис, у которого я отмечаюсь после каждого ежедневного сбора; не отметился вовремя — он пишет тебе сам.":
        "If I stop — the server goes down, the disk fills up, the bot token is revoked — I can no longer tell you. "
        "A watchdog is a service I check in with after every daily collection; when I miss it, it writes to you itself.",
    "<b>Как подключить</b> (бесплатно, 2 минуты):": "<b>How to connect it</b> (free, 2 minutes):",
    "1. На healthchecks.io создай check: период — 1 день, grace — 3 часа.":
        "1. On healthchecks.io create a check: period — 1 day, grace — 3 hours.",
    "2. Скопируй его ссылку вида https://hc-ping.com/… и нажми «🔗 Прислать ссылку».":
        "2. Copy its link, https://hc-ping.com/…, and press \"🔗 Send the link\".",
    "3. Я сразу отмечусь пробным пингом и прочитаю ответ: если check не найден, скажу.":
        "3. I check in with a test ping at once and read the answer: if the check is not found, I say so.",
    "Адрес heartbeat из TofsDevOps тоже подходит — тогда на его главном экране появятся строки по сетям.":
        "A TofsDevOps heartbeat address works too — then its home screen gets a line per network.",
    "🔗 Прислать ссылку": "🔗 Send the link",
    "🔄 Проверить снова": "🔄 Check again",
    "⏏ Отключить": "⏏ Disconnect",
    "✅ Да, отключить": "✅ Yes, disconnect",
    "<b>⏏ Отключить сторожа?</b>\n\nЯ перестану отмечаться по ссылке из чата; если задан HEALTHCHECK_URL — "
    "буду отмечаться по нему. Сам check на healthchecks.io поставь на паузу, иначе он напишет, что я пропал.":
        "<b>⏏ Disconnect the watchdog?</b>\n\nI will stop checking in with the link from the chat; if HEALTHCHECK_URL "
        "is set, I will use it. Pause the check on healthchecks.io itself, or it will write that I am gone.",
    (
        "🔗 Пришли ссылку сторожа одним сообщением: https://hc-ping.com/… из healthchecks.io или адрес heartbeat "
        "из TofsDevOps. Я отмечусь по ней пробным пингом и сразу удалю сообщение."
    ): (
        "🔗 Send the watchdog link in one message: https://hc-ping.com/… from healthchecks.io or a TofsDevOps "
        "heartbeat address. I check in with a test ping and delete the message at once."
    ),
    "check не найден — удалён или ссылка скопирована не целиком": "check not found — deleted, or the link was copied in part",
    "отвечает ошибкой {status}": "answers with error {status}",
    "не ответил за 10 с": "did not answer within 10 s",
    "не удаётся подключиться — сеть или DNS": "cannot connect — network or DNS",
    "не отвечает": "does not answer",
    "TofsDevOps не принял отметку": "TofsDevOps did not take the ping",
}

# Russian singular → (English singular, English plural).
PLURALS: dict[str, tuple[str, str]] = {
    "дн.": ("day", "days"),
    "день": ("day", "days"),
    "час": ("hour", "hours"),
    "минута": ("minute", "minutes"),
}

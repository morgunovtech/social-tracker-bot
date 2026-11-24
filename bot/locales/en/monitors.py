"""English for bot/monitors (see bot/i18n.py)."""

from __future__ import annotations

STRINGS: dict[str, str] = {
    # bot/monitors/__init__.py — the monitors in /modules
    "Подписчики": "Followers",
    "падения, наплыв ботов, круглые числа": "drops, bot waves, round numbers",
    "Сбор данных": "Data collection",
    "сбои несколько дней подряд, истёкший cookie LinkedIn или токен Instagram": (
        "failures several days in a row, an expired LinkedIn cookie or Instagram token"
    ),
    "Профиль": "Profile",
    "смена названия, описания и ссылок, аватарки; новые админы; пропавшие видео": (
        "changed name, description, links or avatar; new admins; missing videos"
    ),
    "Telegram-канал, YouTube или Instagram": "a Telegram channel, YouTube or Instagram",
    "Чек-лист безопасности": "Security checklist",
    "2FA и пароли: балл в отчёте, напоминание раз в месяц": "2FA and passwords: a score in the report, a monthly reminder",
    "Письма безопасности": "Security emails",
    "новые входы, смена пароля, коды входа — из пересланных писем": (
        "new sign-ins, password changes, login codes — from forwarded emails"
    ),
    "SECURITY_MAIL_URL и SECURITY_MAIL_TOKEN": "SECURITY_MAIL_URL and SECURITY_MAIL_TOKEN",
    "Комментарии": "Comments",
    "запрещённый контент в обсуждении канала: наркотики, порно, экстремизм, мошенничество — карточка с кнопками": (
        "prohibited content in the channel's discussion group: drugs, porn, extremism, fraud — a card with buttons"
    ),
    "ANTHROPIC_API_KEY и Telegram-канал с группой обсуждения": "ANTHROPIC_API_KEY and a Telegram channel with a discussion group",
    # bot/monitors/comments.py — the cards
    "наркотики": "drugs",
    "порнография": "pornography",
    "сексуализация детей": "sexualization of minors",
    "экстремизм или терроризм": "extremism or terrorism",
    "мошенничество": "fraud",
    "спам или реклама": "spam or advertising",
    "модель отказалась оценивать": "the model declined to judge it",
    "📷 фото": "📷 photo",
    "🎬 видео": "🎬 video",
    "🎬 GIF": "🎬 GIF",
    "🩵 стикер": "🩵 sticker",
    "📎 файл": "📎 file",
    "🗑 Удалено": "🗑 Deleted",
    "🔨 Удалено, автор забанен": "🔨 Deleted, author banned",
    "↩️ Бан снят, сообщение удалено": "↩️ Ban lifted, the message stays deleted",
    "🗑 Удалить": "🗑 Delete",
    "🔨 Удалить и забанить": "🔨 Delete and ban",
    "✅ Всё в порядке": "✅ All fine",
    "↩️ Разбанить": "↩️ Unban",
    "🔨 Забанить автора": "🔨 Ban the author",
    "{icon} Комментарии: {label}": "{icon} Comments: {label}",
    "{icon} Комментарии: {label} — уверенность {confidence}%": "{icon} Comments: {label} — confidence {confidence}%",
    "первое сообщение в группе": "first message in the group",
    "Почему: {reason}": "Why: {reason}",
    "Модель не стала оценивать это сообщение — обычно так бывает с самым тяжёлым контентом. Посмотри сам.": (
        "The model declined to judge this message — that usually happens with the worst content. Have a look yourself."
    ),
    "За такой контент Telegram блокирует всю группу. Я только сообщаю — удалить или забанить можно кнопкой.": (
        "Telegram blocks the whole group for content like this. I only report — delete or ban with a button."
    ),
    "Группе это не грозит, но и не нужно. Удалить или забанить можно кнопкой.": (
        "No threat to the group, but unwanted. Delete or ban with a button."
    ),
    "✅ Отмечено: ложная тревога — учту в статистике": "✅ Marked: false alarm — counted in the statistics",
    "🟠 Комментарии: проверка не работает {n} раза подряд ({error}) — комментарии сейчас никто не смотрит. "
    "Проверь ANTHROPIC_API_KEY и баланс API.": (
        "🟠 Comments: the check has failed {n} times in a row ({error}) — nobody is looking at the comments right now. "
        "Check ANTHROPIC_API_KEY and the API balance."
    ),
    "✅ Комментарии: проверка снова работает": "✅ Comments: the check works again",
    "🟠 Комментарии: дневной лимит проверок ({limit}) исчерпан — до конца суток (UTC) новые "
    "комментарии не проверяю. Лимит задаёт COMMENTS_DAILY_LIMIT в .env.": (
        "🟠 Comments: the daily limit of checks ({limit}) is reached — no new comment is checked until "
        "the end of the day (UTC). COMMENTS_DAILY_LIMIT in .env sets the limit."
    ),
    "Нет прав: сделай бота админом группы с правом удалять сообщения и блокировать участников.": (
        "No rights: make the bot a group admin with the rights to delete messages and ban members."
    ),
    "Сообщение уже удалено.": "The message is already deleted.",
    "Автор — админ группы, его нельзя забанить.": "The author is a group admin and cannot be banned.",
    "Telegram не нашёл этого пользователя.": "Telegram could not find this user.",
    "Telegram ответил ошибкой: {error}": "Telegram answered with an error: {error}",
    "Эта карточка устарела": "This card is out of date",
    "Отмечено как ложная тревога": "Marked as a false alarm",
    "Удалено": "Deleted",
    "Автор неизвестен": "The author is unknown",
    "Удалено, автор забанен": "Deleted, author banned",
    "Бан снят": "Ban lifted",
    # bot/monitors/hygiene.py — the checklist
    "да": "yes",
    "нет": "no",
    "2FA": "2FA",
    "Как включена двухфакторная защита?": "How is two-factor authentication set up?",
    "приложение/ключ": "app/key",
    "SMS": "SMS",
    "включи 2FA через приложение-аутентификатор или ключ доступа — SMS перехватывают перевыпуском SIM": (
        "turn on 2FA with an authenticator app or a passkey — SMS codes are intercepted by SIM swapping"
    ),
    "Резервные коды": "Backup codes",
    "Резервные коды 2FA сохранены?": "Are the 2FA backup codes saved?",
    "сохрани резервные коды 2FA в менеджере паролей — без них потеря телефона = потеря аккаунта": (
        "save the 2FA backup codes in your password manager — without them a lost phone means a lost account"
    ),
    "Почта и телефон актуальны": "Recovery email and phone up to date",
    "Почта и телефон для восстановления актуальны?": "Are the recovery email and phone number up to date?",
    "проверь почту и телефон для восстановления — через них аккаунт возвращают после взлома": (
        "check the recovery email and phone number — they are how you get the account back after a hijack"
    ),
    "Уникальный пароль": "Unique password",
    "Пароль уникальный и хранится в менеджере паролей?": "Is the password unique and stored in a password manager?",
    "поставь уникальный пароль из менеджера паролей — повторённый пароль утекает вместе с чужим сайтом": (
        "set a unique password from your password manager — a reused password leaks with someone else's site"
    ),
    "Облачный пароль": "Cloud password",
    "Облачный пароль включён? Настройки → Конфиденциальность → Облачный пароль": (
        "Is the cloud password on? Settings → Privacy and Security → Two-Step Verification"
    ),
    "включён": "on",
    "включи облачный пароль (Настройки → Конфиденциальность) — без него для входа хватает одного кода": (
        "turn on the cloud password (Settings → Privacy and Security) — without it a single code is enough to sign in"
    ),
    "Почта восстановления": "Recovery email",
    "К облачному паролю привязана почта для восстановления?": "Is a recovery email attached to the cloud password?",
    "укажи почту для восстановления облачного пароля — без неё забытый пароль не вернуть": (
        "set a recovery email for the cloud password — without it a forgotten password cannot be recovered"
    ),
    "Только свои сеансы": "Only your own sessions",
    "Все сеансы в Настройки → Устройства — твои?": "Are all sessions in Settings → Devices yours?",
    "открой Настройки → Устройства и заверши незнакомые сеансы — через них читают чаты и управляют каналом": (
        "open Settings → Devices and terminate unfamiliar sessions — they read your chats and control your channel"
    ),
    "Облачный пароль уникальный, больше нигде не используется?": "Is the cloud password unique, used nowhere else?",
    "сделай облачный пароль уникальным, из менеджера паролей": "make the cloud password unique, from your password manager",
    "Смена пароля": "Password change",
    "Когда пароль менялся последний раз?": "When was the password last changed?",
    "уникальный пароль не нужно менять по расписанию, но если он старше года или мог утечь — смени": (
        "a unique password needs no scheduled changes, but change it if it is over a year old or may have leaked"
    ),
    "сегодня": "today",
    "около месяца назад": "about a month ago",
    "около полугода назад": "about six months ago",
    "больше года / не помню": "over a year ago / don't remember",
    "не отмечено": "not marked",
    "{age} дн. назад": "{age} days ago",
    "{label}: отметь пункты чек-листа — это пара минут": "{label}: fill in the checklist — it takes a couple of minutes",
    "{label}: отметь, когда пароль менялся последний раз": "{label}: mark when the password was last changed",
    "{label}: пароль не менялся {age} дн. — смени, если он не уникальный или где-то светился": (
        "{label}: the password has not changed in {age} days — change it if it is not unique or may have been exposed"
    ),
    "🛡 Безопасность: {score} из {max} — /security": "🛡 Security: {score} of {max} — /security",
    "🛡 Безопасность: {score} из {max}": "🛡 Security: {score} of {max}",
    (
        "Пройди короткий чек-лист по своим аккаунтам: 2FA, резервные коды, пароли. "
        "Пароль вводить не нужно — только отметки."
    ): (
        "Go through a short checklist for your accounts: 2FA, backup codes, passwords. "
        "No password is entered — only your marks."
    ),
    "Отметки не пересматривались {age} дн. — проверь, всё ли ещё так.": (
        "The marks have not been reviewed in {age} days — check whether they still hold."
    ),
    "Открыть чек-лист: /security": "Open the checklist: /security",
    # bot/monitors/profile.py — profile integrity alerts
    "(пусто)": "(empty)",
    "похоже на взлом": "looks like a hijack",
    "🔴 {label}: {hijack} — новый админ {name}": "🔴 {label}: {hijack} — new admin {name}",
    "🟠 {label}: админ удалён — {name}": "🟠 {label}: admin removed — {name}",
    "🔴 {label}: {hijack} — сменился владелец: {before} → {after}": "🔴 {label}: {hijack} — owner changed: {before} → {after}",
    "{icon} {platform}: {hijack} — {field}: «{before}» → «{after}»": '{icon} {platform}: {hijack} — {field}: "{before}" → "{after}"',
    "{icon} {platform}: {field} — «{before}» → «{after}»": '{icon} {platform}: {field} — "{before}" → "{after}"',
    " и ещё {n}": " and {n} more",
    "новые ссылки: {links}{more}": "new links: {links}{more}",
    "🟠 {platform}: новая {field}": "🟠 {platform}: new {field}",
    "🔴 {platform}: {hijack} — {field}: было {was}, стало {now} (−{drop})":
        "🔴 {platform}: {hijack} — {field}: was {was}, now {now} (−{drop})",
    "✅ {label}: профиль снова доступен": "✅ {label}: the profile is reachable again",
    (
        "🔴 {label}: профиль не читается {n} {checks} подряд — "
        "канал удалён или скрыт, или у бота отобрали права?"
    ): (
        "🔴 {label}: the profile could not be read {n} {checks} in a row — "
        "was the channel deleted or hidden, or did the bot lose its rights?"
    ),
    "🛡 Профиль": "🛡 Profile",
    (
        "Если это сделал не ты — смени пароль, заверши чужие сеансы и проверь список админов. "
        "Если ты — всё в порядке."
    ): (
        "If this wasn't you — change the password, terminate other sessions and check the admin list. "
        "If it was you — all is well."
    ),
    # bot/monitors/mail.py — security emails
    "запрошен сброс пароля": "password reset requested",
    "Если сброс запросил кто-то другой — значит, пробуют войти. Пароль цел, проверь, что 2FA включена.": (
        "If someone else requested the reset, they are trying to get in. The password is intact; check that 2FA is on."
    ),
    "пароль изменён": "password changed",
    "Если это не ты — восстанавливай доступ немедленно и заверши все сеансы.": (
        "If this wasn't you — recover access immediately and terminate all sessions."
    ),
    "изменена почта аккаунта": "account email changed",
    "Если это не ты — аккаунт уводят: восстанавливай доступ немедленно.": (
        "If this wasn't you — the account is being taken over: recover access immediately."
    ),
    "изменена двухфакторная защита": "two-factor authentication changed",
    "Если это не ты — верни 2FA и смени пароль.": "If this wasn't you — restore 2FA and change the password.",
    "новый вход в аккаунт": "new sign-in to the account",
    "Если это не ты — смени пароль и заверши чужие сеансы.": (
        "If this wasn't you — change the password and terminate other sessions."
    ),
    "пришёл код входа": "a login code arrived",
    "Если код запрашивал не ты — кто-то знает твой пароль: смени его.": (
        "If you didn't request the code, someone knows your password: change it."
    ),
    "оповещение безопасности": "security alert",
    "Проверь недавнюю активность в аккаунте.": "Check the recent activity in the account.",
    "(без темы)": "(no subject)",
    "📬 Gmail просит подтвердить пересылку писем на адрес бота.": (
        "📬 Gmail asks you to confirm forwarding mail to the bot's address."
    ),
    "Код подтверждения: {code} — введи его в Gmail: Настройки → Пересылка.": (
        "Confirmation code: {code} — enter it in Gmail: Settings → Forwarding."
    ),
    "Кода в теме не нашёл: «{subject}»": 'No code found in the subject: "{subject}"',
    "Потом создай фильтр по отправителям уведомлений безопасности — см. mail-worker/README.md.": (
        "Then create a filter on the senders of security notifications — see mail-worker/README.md."
    ),
    "ℹ️ Письмо без признаков тревоги: {network} — «{subject}»": 'ℹ️ Email with no signs of trouble: {network} — "{subject}"',
    "{icon} {network}: {hijack} — {title}": "{icon} {network}: {hijack} — {title}",
    "{icon} {network}: {title}": "{icon} {network}: {title}",
    "{head}\n«{subject}»\n{advice}": '{head}\n"{subject}"\n{advice}',
    "Восстановление доступа: {url}": "Recover access: {url}",
    "✅ Почтовый воркер снова отвечает": "✅ The mail worker is responding again",
    (
        "🔴 Почтовый воркер не отвечает ~30 мин — письма безопасности не доходят. "
        "Проверь SECURITY_MAIL_URL, SECURITY_MAIL_TOKEN и деплой воркера."
    ): (
        "🔴 The mail worker has not responded for ~30 min — security emails are not getting through. "
        "Check SECURITY_MAIL_URL, SECURITY_MAIL_TOKEN and the worker's deployment."
    ),
    "✍️ Дата смены пароля отмечена в чек-листе /security.": (
        "✍️ The password change date has been recorded in the /security checklist."
    ),
    # bot/monitors/followers.py — follower anomalies
    "🟠 {label}: −{drop} подписчиков за день ({prev} → {new})": "🟠 {label}: −{drop} followers in a day ({prev} → {new})",
    "🟠 {label}: +{gain} за день ({prev} → {new}) — аномально резкий рост, возможен наплыв ботов": (
        "🟠 {label}: +{gain} in a day ({prev} → {new}) — abnormally sharp growth, possibly a bot wave"
    ),
    "🎯 {label} перешагнул {milestone}!": "🎯 {label} passed {milestone}!",
    # bot/monitors/collection.py — collection health
    "🟠 LinkedIn cookie истёк или отклонён — обнови через /setcookie": (
        "🟠 The LinkedIn cookie has expired or was rejected — update it with /setcookie"
    ),
    "🟠 Instagram отклонил токен: истёк или отозван — пришли новый через /igtoken": (
        "🟠 Instagram rejected the token: expired or revoked — send a new one with /igtoken"
    ),
    "🟠 {label}: не удаётся собрать данные {streak} дн. подряд": "🟠 {label}: data collection has failed {streak} days in a row",
    "🟠 LinkedIn: по cookie получено {count} — первое число подтверди командой /linkedin {raw}, "
    "дальше буду собирать сам": (
        "🟠 LinkedIn: the cookie read {count} — confirm the first number with /linkedin {raw}, "
        "I collect it myself from then on"
    ),
    "🟠 Ежедневный сбор не выполнился {streak} дн. подряд — подробности в логах бота": (
        "🟠 The daily collection has failed {streak} days in a row — the details are in the bot's logs"
    ),
    # bot/monitors/channel.py — life of the channel
    "Жизнь канала": "Life of the channel",
    "подписки и отписки, откуда пришли, посты и реакции — экран 📣 Канал и строка в отчёте": (
        "joins and leaves, where they came from, posts and reactions — the 📣 Channel screen and a line in the report"
    ),
    "Telegram-канал, бот в его админах": "a Telegram channel with the bot among its admins",
    "по ссылке без имени": "by an unnamed link",
    "по заявке": "by join request",
    "через папку": "via a chat folder",
    "напрямую": "directly",
    "по ссылке «{name}»": 'by the link "{name}"',
    "📣 Канал за {days} дн.: {parts}": "📣 Channel, last {days} days: {parts}",
    "Пока пусто. Подписки, отписки, посты и реакции приходят, когда бот — админ канала; "
    "первые цифры появятся с первым событием.": (
        "Nothing yet. Joins, leaves, posts and reactions arrive while the bot is an admin of the channel; "
        "the first numbers come with the first event."
    ),
    "За 24 часа": "Last 24 hours",
    "За {days} дней": "Last {days} days",
    "Подписки · отписки · посты · реакции на посты за период": "Joins · leaves · posts · reactions on the period's posts",
    "<b>Откуда приходят</b> · {days} дней": "<b>Where they come from</b> · {days} days",
    "<b>Больше всего реакций</b> · {days} дней": "<b>Most reactions</b> · {days} days",
    "пост": "post",
    "<b>Последние</b>": "<b>Latest</b>",
}

PLURALS: dict[str, tuple[str, str]] = {
    "проверку": ("check", "checks"),
    "пост": ("post", "posts"),
    "реакция": ("reaction", "reactions"),
    "подписка": ("join", "joins"),
    "отписка": ("leave", "leaves"),
}

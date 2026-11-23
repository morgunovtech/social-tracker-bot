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
    "🚨 {label}: новый админ — {name}": "🚨 {label}: new admin — {name}",
    "🟠 {label}: админ удалён — {name}": "🟠 {label}: admin removed — {name}",
    "🚨 {label}: сменился владелец — {before} → {after}": "🚨 {label}: owner changed — {before} → {after}",
    "{icon} {platform}: {field} — «{before}» → «{after}»": '{icon} {platform}: {field} — "{before}" → "{after}"',
    " и ещё {n}": " and {n} more",
    "новые ссылки: {links}{more}": "new links: {links}{more}",
    "🟠 {platform}: новая {field}": "🟠 {platform}: new {field}",
    "🚨 {platform}: {field} — было {was}, стало {now} (−{drop})": "🚨 {platform}: {field} — was {was}, now {now} (−{drop})",
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
    "📨 Письмо без признаков тревоги: {network} — «{subject}»": '📨 Email with no signs of trouble: {network} — "{subject}"',
    "{icon} {network}: {title}\n«{subject}»\n{advice}": '{icon} {network}: {title}\n"{subject}"\n{advice}',
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
    "🚨 {label}: +{gain} за день ({prev} → {new}) — аномально резкий рост, возможен наплыв ботов": (
        "🚨 {label}: +{gain} in a day ({prev} → {new}) — abnormally sharp growth, possibly a bot wave"
    ),
    "🎯 {label} перешагнул {milestone}!": "🎯 {label} passed {milestone}!",
    # bot/monitors/collection.py — collection health
    "🔴 LinkedIn cookie истёк или отклонён — обнови через /setcookie": (
        "🔴 The LinkedIn cookie has expired or was rejected — update it with /setcookie"
    ),
    "🔴 Instagram отклонил токен: истёк или отозван — пришли новый через /igtoken": (
        "🔴 Instagram rejected the token: expired or revoked — send a new one with /igtoken"
    ),
    "⚠️ Instagram подключён, но токена нет — пришли его через /igtoken": (
        "⚠️ Instagram is connected but there is no token — send it with /igtoken"
    ),
    "🔴 {label}: не удаётся собрать данные {streak} дн. подряд": "🔴 {label}: data collection has failed {streak} days in a row",
}

PLURALS: dict[str, tuple[str, str]] = {
    "проверку": ("check", "checks"),
}

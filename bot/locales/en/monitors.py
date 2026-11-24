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
    "Отправки наружу": "Outgoing deliveries",
    "цифры на сайт, строки в TofsDevOps, отметки сторожу: сутки не доходят — скажу, где и почему":
        "the counts to your site, the lines to TofsDevOps, the watchdog's marks: a day without one landing — I say where and why",
    "Ссылки в профилях": "Profile links",
    "Поиски в Google": "Searches on Google",
    "раз в неделю: сколько раз тебя и твои продукты искали в Google — показы и клики по брендовым запросам":
        "weekly: how often you and your products were searched for on Google — impressions and clicks of brand queries",
    "Поиски в Яндексе": "Searches on Yandex",
    "раз в неделю: брендовые запросы в Яндексе — показы и клики": "weekly: brand queries on Yandex — impressions and clicks",
    "ИИ-ассистенты": "AI assistants",
    "раз в неделю: сколько раз ChatGPT, Perplexity и другие открывали твои страницы по запросам людей":
        "weekly: how often ChatGPT, Perplexity and others opened your pages for people's questions",
    "раз в неделю — куда ведут ссылки в описаниях: не открывается, переадресация, технический адрес":
        "weekly — where the links in the descriptions lead: does not open, a redirect, a technical host",
    # bot/monitors/links.py
    "адрес {host} не находится": "the address {host} does not resolve",
    "сертификат сайта не принимается": "the site's certificate is not accepted",
    "защищённое соединение не устанавливается": "a secure connection cannot be set up",
    "сайт не принимает соединение": "the site refuses the connection",
    "сайт не ответил за 15 с": "the site did not answer in 15 s",
    "страница не найдена ({status})": "page not found ({status})",
    "сайт отвечает ошибкой {status}": "the site answers with error {status}",
    "переадресаций больше {n}": "more than {n} redirects",
    "{platform}, {field}": "{platform}, {field}",
    "🟠 {where}: ссылка не открывается — {why}": "🟠 {where}: a link does not open — {why}",
    "проверка ссылок раз в неделю": "links are checked weekly",
    "✅ {where}: ссылка снова открывается — {link}": "✅ {where}: the link opens again — {link}",
    "Не открывалась": "Did not open for",
    "• {where}: {link} → {final} — ведёт через переадресацию, лучше поставить конечный адрес":
        "• {where}: {link} → {final} — goes through a redirect; the final address is better",
    (
        "• {where}: {link} — ведёт на технический адрес {final}; если у сайта есть свой домен, "
        "лучше он"
    ): "• {where}: {link} — lands on the technical host {final}; if the site has a domain of its own, that one is better",
    "ℹ️ Ссылки в профилях — можно лучше:": "ℹ️ Profile links — could be better:",
    "Поправить можно в самом профиле; я проверю снова через неделю.":
        "Fix them in the profile itself; I'll check again in a week.",
    "Кто нажмёт эту ссылку в профиле, попадёт на ошибку, а не к тебе.":
        "Whoever taps this link in the profile gets an error instead of you.",
    "страницу удалили или переименовали, домен переехал или истёк, сайт лежит":
        "the page was deleted or renamed, the domain moved or expired, the site is down",
    "Открыть ссылку самому: может, сайт лежит прямо сейчас.": "Open the link yourself: the site may be down right now.",
    "Если адрес сменился — поправить описание в профиле.": "If the address changed, fix the description in the profile.",
    # bot/monitors/outgoing.py
    "Цифры на сайт": "Counts to the site",
    "Строки в TofsDevOps": "Lines to TofsDevOps",
    "Отметки сторожу": "Marks to the watchdog",
    "🟠 {where} не принимает цифры подписчиков уже {how_long}: {reason}":
        "🟠 {where} has not accepted the follower counts for {how_long}: {reason}",
    "✅ {where} снова принимает цифры подписчиков": "✅ {where} accepts the follower counts again",
    "🟠 TofsDevOps не принимает строки состояния уже {how_long}: {reason}":
        "🟠 TofsDevOps has not accepted the status lines for {how_long}: {reason}",
    "✅ TofsDevOps снова принимает строки состояния": "✅ TofsDevOps accepts the status lines again",
    "🟠 Сторож {where} не принимает отметки уже {how_long}: {reason}":
        "🟠 The watchdog {where} has not accepted the marks for {how_long}: {reason}",
    "✅ Сторож {where} снова принимает отметки": "✅ The watchdog {where} accepts the marks again",
    "Не принимал": "Did not accept them for",
    "последняя удачная {when}": "the last one that landed {when}",
    "удачных ещё не было": "none has landed yet",
    ", последняя удачная {when}": ", the last one that landed {when}",
    "{icon} {what}: не доходят с {since} — {reason}{last}": "{icon} {what}: not landing since {since} — {reason}{last}",
    "{icon} {what}: последняя удачная {when}": "{icon} {what}: the last one landed {when}",
    "{icon} {what}: ещё не отправлялись": "{icon} {what}: not sent yet",
    "На сайте застыли последние принятые цифры — посетители видят старое число.":
        "The site shows the last counts it accepted — visitors see an old number.",
    (
        "сменился SOCIALBOT_INGEST_TOKEN у бота или секрет у сайта, переехал адрес приёма, сайт лежит или не "
        "задеплоился"
    ): "SOCIALBOT_INGEST_TOKEN changed on the bot or the secret on the site, the ingest address moved, the site is down or was not deployed",
    (
        "Сверить SOCIALBOT_INGEST_TOKEN у бота и секрет сайта — они должны совпадать; новый секрет сайт на "
        "Cloudflare Pages подхватывает только после нового деплоя (Retry deployment)."
    ): (
        "Compare SOCIALBOT_INGEST_TOKEN on the bot with the site's secret — they must match; a site on Cloudflare "
        "Pages picks up a new secret only after a new deploy (Retry deployment)."
    ),
    "Проверить SITE_INGEST_URL: после переезда домена адрес приёма мог смениться.":
        "Check SITE_INGEST_URL: after a domain move the ingest address may have changed.",
    "На главном экране TofsDevOps застыли строки по сетям: он показывает прошлое состояние.":
        "The network lines on TofsDevOps's main screen are frozen: it shows a past state.",
    "TofsDevOps обновился и не принимает формат, адрес heartbeat удалён или сменился, TofsDevOps не работает":
        "TofsDevOps was updated and rejects the format, the heartbeat address was deleted or changed, TofsDevOps is down",
    "Открыть ⏱ Сторож и нажать «🔄 Проверить снова».": "Open ⏱ Watchdog and tap «🔄 Check again».",
    "Если heartbeat в TofsDevOps удалён — создать новый и прислать ссылку здесь.":
        "If the heartbeat was deleted in TofsDevOps, create a new one and send its link here.",
    (
        "Сторож не слышит меня: скоро он напишет, что я пропал, хотя я работаю, — а если check удалён, не напишет "
        "ничего, когда я правда остановлюсь."
    ): (
        "The watchdog does not hear me: soon it will write that I am gone although I work — and if the check was "
        "deleted, it will write nothing when I really stop."
    ),
    "check удалён или поставлен на паузу, ссылка скопирована не целиком, сбой у сервиса сторожа":
        "the check was deleted or paused, the link was copied incompletely, the watchdog service has a failure",
    "Если check удалён — создать новый на healthchecks.io и прислать ссылку.":
        "If the check was deleted, create a new one on healthchecks.io and send its link.",
    "Письма безопасности": "Security emails",
    (
        "новые входы, смена пароля, телефона и 2FA, новые ключи и токены, новый владелец сайта в поиске, коды входа — "
        "из пересланных писем соцсетей, GitHub, Microsoft, Яндекса"
    ): (
        "new sign-ins, password, phone and 2FA changes, new keys and tokens, a new owner of the site in search, login "
        "codes — from forwarded emails of the networks, GitHub, Microsoft, Yandex"
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
    "✏️ отредактирован после публикации": "✏️ edited after posting",
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
    "✅ Комментарии: проверка снова работает": "✅ Comments: the check works again",
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
    "изменён телефон аккаунта": "the account's phone number changed",
    "Сменили номер телефона, на который приходят коды входа и восстановления.":
        "The phone number that gets the sign-in and recovery codes was changed.",
    "ты сам — новый номер; если нет — угонщик забирает восстановление себе":
        "you — a new number; if not, a hijacker is taking the recovery for themselves",
    "Если это не ты — восстанавливай доступ немедленно: с чужим номером пароль сбросят без тебя.":
        "If it wasn't you, recover access right away: with someone else's number the password is reset without you.",
    "добавлен ключ, токен или приложение": "a key, token or app was added",
    "у сайта новый владелец в поиске": "the site has a new owner in search",
    (
        "У сайта появился ещё один подтверждённый владелец в панели поисковика: он может убрать страницы из "
        "поиска, поменять настройки и видеть статистику."
    ): "The site has one more verified owner in a search engine's console: they can remove pages from search, change the settings and see the statistics.",
    (
        "ты сам — подтвердил сайт заново или другим способом, подключил сервис; если нет — у кого-то есть доступ "
        "к DNS или файлам сайта"
    ): "you — you verified the site again or another way, or connected a service; if not, someone has access to the site's DNS or files",
    (
        "Если это не ты — удали чужого владельца в настройках ресурса (Search Console: Настройки → Пользователи "
        "и разрешения) и убери его код подтверждения — запись DNS или файл, иначе права вернутся."
    ): "If it wasn't you, remove the stranger in the property's settings (Search Console: Settings → Users and permissions) and delete their verification token — the DNS record or the file — or the rights come back.",
    (
        "В аккаунт добавили новый способ входить без пароля: токен, ключ, пароль приложения или стороннее "
        "приложение с доступом."
    ): "A new way into the account without the password was added: a token, a key, an app password or a third-party app with access.",
    (
        "ты сам — для бота, деплоя или нового сервиса; если нет — угонщик закрепляется: такой ключ переживёт "
        "смену пароля"
    ): "you — for a bot, a deploy or a new service; if not, a hijacker is digging in: such a key survives a password change",
    "Если это не ты — отзови ключ или приложение в настройках безопасности аккаунта, потом смени пароль.":
        "If it wasn't you, revoke the key or the app in the account's security settings, then change the password.",
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
    "Восстановление доступа: {url}": "Recover access: {url}",
    "✅ Почтовый воркер снова отвечает": "✅ The mail worker is responding again",
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
    # The one alert shape (bot/humanize.py)
    "{meaning} Обычно это {cause}.": "{meaning} Usually it is {cause}.",
    "Что делать:": "What to do:",
    "Тех.: {details}": "Tech: {details}",
    "{m} мин": "{m} min",
    "{h} ч {m} мин": "{h} h {m} min",
    "{h} ч": "{h} h",
    "{d} дн. {h} ч": "{d} d {h} h",
    "{d} дн.": "{d} d",
    "не меньше {span}; когда именно наладилось — не знаю: с {from_} до {to} я не проверял":
        "at least {span}; when exactly it came back I do not know: I did not check from {from_} to {to}",
    "{verb} {how_long}.": "{verb} {how_long}.",
    "Ничего делать не нужно.": "Nothing to do.",
    "Не работал": "Was down for",
    "Не работала": "Was down for",
    "Не читался": "Was unreadable for",
    "Молчал": "Was silent for",
    "Не собирались": "Not collected for",
    "Не выполнялся": "Did not run for",
    "Подписчиков стало заметно меньше за сутки — больше, чем обычные отписки.":
        "Noticeably fewer followers within a day — more than the usual unfollows.",
    "отписки после поста или рекламы, чистка удалённых аккаунтов самой сетью, реже — уход ботов после накрутки":
        "unfollows after a post or an ad, the network clearing out deleted accounts, less often bots leaving after fake growth",
    "Посмотреть 📈 Динамику: разовое это падение или тренд.": "Look at 📈 Trends: a one-off drop or a trend.",
    "Сравнить с последними постами — после чего ушли.": "Compare with the latest posts — what they left after.",
    "Подписчиков пришло во много раз больше обычного.": "Many times more followers came than usual.",
    "репост в большом канале или удачный пост; реже — нагнанные боты: накрутку, которой ты не заказывал, "
    "сеть может наказать":
        "a repost in a big channel or a lucky post; less often bots pumped in: the network may punish fake growth "
        "you never ordered",
    "Если был репост или реклама — всё в порядке.": "If there was a repost or an ad — all is well.",
    "Если нет — посмотреть, через какую ссылку пришли (📣 Канал) и похожи ли имена на ботов.":
        "If not — see which link they came through (📣 Channel) and whether the names look like bots.",
    "Числа за эти дни не записаны: не было ни отчёта, ни проверок, которые идут вместе со сбором.":
        "No numbers were recorded for these days: no report, and none of the checks that run with the collection.",
    "сбой базы или диска на сервере, ошибка в новой версии бота, нет сети у сервера":
        "a database or disk failure on the server, a bug in a new version of the bot, no network on the server",
    "Посмотреть логи бота (на Railway — Deployments → View logs).": "Look at the bot's logs (on Railway — Deployments → View logs).",
    "Если бот недавно обновлялся — откатить деплой и написать в issues.":
        "If the bot was updated recently — roll the deploy back and open an issue.",
    "Автосбор LinkedIn работает, но первое число нужно сверить: на странице профиля есть и счётчики других "
    "профилей.":
        "Automatic LinkedIn collection works, but the first number needs checking: the profile page carries other "
        "profiles' counters too.",
    "так всегда бывает с первым числом по cookie": "how it always goes with the first number read by cookie",
    "Открыть свой профиль LinkedIn и сверить число подписчиков.": "Open your LinkedIn profile and compare the follower count.",
    "Совпадает — подтвердить командой из заголовка; нет — ввести верное: /linkedin <число>.":
        "It matches — confirm with the command in the headline; it does not — enter the right one: /linkedin <count>.",
    "Число LinkedIn больше не собирается само — в отчёте останется последнее.":
        "The LinkedIn number is no longer collected by itself — the report keeps the last one.",
    "cookie живёт около года, а выход из LinkedIn в браузере или смена пароля обрывает его раньше":
        "a cookie lives about a year, and signing out of LinkedIn in the browser or changing the password ends it sooner",
    "Войти на linkedin.com и скопировать cookie li_at (DevTools → Application → Cookies).":
        "Sign in to linkedin.com and copy the li_at cookie (DevTools → Application → Cookies).",
    "Прислать его: 🔌 Подключения → 💼 LinkedIn → «🔑 Прислать cookie» или /setcookie. "
    "Или вводить число вручную.":
        "Send it: 🔌 Connections → 💼 LinkedIn → \"🔑 Send the cookie\" or /setcookie. Or enter the number by hand.",
    "Число Instagram и проверка профиля остановились.": "The Instagram number and the profile check have stopped.",
    "Meta отозвала токен: сменили пароль, удалили приложение или тестировщика; реже — сбой у Meta":
        "Meta revoked the token: the password was changed, the app or the tester removed; less often a failure at Meta",
    "developers.facebook.com → приложение → API setup with Unified login → Generate token.":
        "developers.facebook.com → the app → API setup with Unified login → Generate token.",
    "Прислать его: 🔌 Подключения → 📸 Instagram → «🔑 Прислать токен» или /igtoken.":
        "Send it: 🔌 Connections → 📸 Instagram → \"🔑 Send the token\" or /igtoken.",
    "Instagram подключён в .env, но число не собирается: токена нет.":
        "Instagram is connected in .env, but the number is not collected: there is no token.",
    "токен ещё не присылали или он не пережил восстановление из бэкапа — бэкап делается без секретов":
        "the token was never sent, or it did not survive a restore from a backup — backups are made without secrets",
    "В отчёте — последнее собранное число, свежих нет.": "The report has the last collected number, nothing fresh.",
    "сеть отвечает ошибкой или поменяла страницу или API; у YouTube — кончилась квота ключа или ключ отключён":
        "the network answers with an error or changed its page or API; for YouTube — the key's quota ran out or the key is disabled",
    "Открыть 🔌 Подключения — там видно, чего ждёт сеть.": "Open 🔌 Connections — it shows what the network waits for.",
    "Не прошло само за пару дней — посмотреть логи бота.": "Not gone by itself in a couple of days — look at the bot's logs.",
    "Так выглядит угон: новый хозяин меняет админов и ссылки, удаляет видео. Если это сделал ты — всё в порядке.":
        "This is what a hijack looks like: a new owner changes the admins and the links, deletes videos. "
        "If it was you — all is well.",
    "ты сам или другой админ; угон — после фишинговой ссылки, утёкшего пароля или чужого сеанса":
        "you or another admin; a hijack — after a phishing link, a leaked password or someone else's session",
    "Если это не ты — сменить пароль и завершить чужие сеансы.": "If it was not you — change the password and end other sessions.",
    "Проверить список админов и убрать лишних; включить 2FA (🛡 Безопасность).":
        "Check the list of admins and remove strangers; turn on 2FA (🛡 Security).",
    "Профиль изменился. С такой правки начинается и обычное обновление, и угон.":
        "The profile changed. An ordinary update and a hijack both start with an edit like this.",
    "ты сам или другой админ": "you or another admin",
    "Если это ты — ничего делать не нужно.": "If it was you — nothing to do.",
    "Если нет — сменить пароль, завершить чужие сеансы и проверить админов.":
        "If not — change the password, end other sessions and check the admins.",
    "Я не вижу профиль — ни числа, ни его изменений. Угонщик первым делом убирает чужих админов, и меня тоже.":
        "I cannot see the profile — neither the number nor its changes. A hijacker removes other admins first, me included.",
    "канал удалили, скрыли или сделали приватным, бота убрали из админов или отключили ключ; реже — сбой сети":
        "the channel was deleted, hidden or made private, the bot removed from the admins or the key disabled; "
        "less often a network failure",
    "Открыть канал: на месте ли он и его админы.": "Open the channel: is it there, and are its admins.",
    "Если бота убрали из админов — вернуть его (особые права не нужны).":
        "If the bot was removed from the admins — add it back (no special rights needed).",
    "Пока воркер молчит, о новом входе или смене пароля я не узнаю.":
        "While the worker is silent, I will not hear about a new sign-in or a changed password.",
    "сменился SECURITY_MAIL_TOKEN, воркер удалён или не задеплоен, сбой Cloudflare":
        "SECURITY_MAIL_TOKEN changed, the worker was deleted or not deployed, a Cloudflare failure",
    "Проверить SECURITY_MAIL_URL и SECURITY_MAIL_TOKEN — у бота и у воркера они одни.":
        "Check SECURITY_MAIL_URL and SECURITY_MAIL_TOKEN — the bot and the worker share them.",
    "Задеплоить воркер заново: cd mail-worker && npx wrangler deploy.":
        "Deploy the worker again: cd mail-worker && npx wrangler deploy.",
    "Новые комментарии сейчас никто не смотрит — опасный я пропущу.":
        "Nobody is looking at new comments right now — I will miss a dangerous one.",
    "кончился баланс API, ключ отозван, или сбой у Anthropic": "the API balance ran out, the key was revoked, or a failure at Anthropic",
    "Проверить баланс и ключ на console.anthropic.com.": "Check the balance and the key on console.anthropic.com.",
    "Если всё в порядке — подождать: я напишу, когда проверка снова заработает.":
        "If all is well — wait: I will write when the check works again.",
    "До конца суток (UTC) новые комментарии не проверяю.": "Until the end of the day (UTC) I do not check new comments.",
    "волна спама или очень живое обсуждение": "a spam wave or a very lively discussion",
    "Посмотреть группу обсуждения: нет ли волны спама.": "Look at the discussion group: is there a spam wave.",
    "Поднять лимит — COMMENTS_DAILY_LIMIT в .env (0 — без лимита).": "Raise the limit — COMMENTS_DAILY_LIMIT in .env (0 — no limit).",
    # The monitors' own lines in that shape
    "порог — {abs} подписчиков или {pct}% за день": "threshold — {abs} followers or {pct}% a day",
    "порог — в {factor} раз больше обычного дневного прироста и не меньше {abs}":
        "threshold — {factor} times the usual daily gain and at least {abs}",
    "🟠 Ежедневный сбор не выполнился {streak} дн. подряд": "🟠 The daily collection has not run {streak} days in a row",
    "сбор падает целиком; повтор через час, подробности в логах": "the whole collection fails; retried in an hour, details in the logs",
    "✅ Ежедневный сбор снова выполняется": "✅ The daily collection runs again",
    "LinkedIn отправил на вход вместо профиля": "LinkedIn sent the sign-in page instead of the profile",
    "Graph API: ошибка авторизации": "Graph API: authorization error",
    "раз в день и два повтора через час; подробности в логах": "once a day and two retries an hour apart; details in the logs",
    "✅ {label}: данные снова собираются": "✅ {label}: data is collected again",
    "проверка профиля раз в {minutes} мин": "the profile is checked every {minutes} min",
    "Кто-то попросил сбросить пароль аккаунта.": "Someone asked to reset the account's password.",
    "ты сам; если нет — кто-то знает твою почту или логин и пробует войти":
        "you; if not — someone knows your email or login and tries to get in",
    "Пароль аккаунта сменили.": "The account's password was changed.",
    "ты сам; если нет — аккаунт уже уводят": "you; if not — the account is being taken over",
    "Сменили почту, на которую приходят входы и сброс пароля.": "The email for sign-ins and password resets was changed.",
    "ты сам; если нет — это главный шаг угона: дальше пароль сбросят на чужую почту":
        "you; if not — it is the main step of a hijack: next the password is reset to someone else's email",
    "Двухфакторную защиту выключили или сменили.": "Two-factor protection was turned off or changed.",
    "ты сам; если нет — угонщик убирает второй ключ": "you; if not — a hijacker removes the second key",
    "В аккаунт вошли с нового устройства или из нового места.": "Someone signed in from a new device or a new place.",
    "ты сам — новый телефон, браузер или VPN": "you — a new phone, browser or VPN",
    "Сервис прислал код для входа.": "The service sent a sign-in code.",
    "ты сам входишь; если нет — кто-то знает пароль и упёрся в код":
        "you signing in; if not — someone knows the password and hit the code",
    "Сервис заметил в аккаунте что-то необычное.": "The service noticed something unusual in the account.",
    "новый вход, смена настроек или подозрительная активность": "a new sign-in, changed settings or suspicious activity",
    "письмо от {domain}": "email from {domain}",
    "🔴 Почтовый воркер не отвечает ~30 мин — письма безопасности не доходят":
        "🔴 The mail worker has not responded for ~30 min — security emails are not getting through",
    "{n} опросов подряд, раз в 5 мин": "{n} polls in a row, every 5 min",
    "🟠 Комментарии: проверка не работает {n} раза подряд": "🟠 Comments: the check has failed {n} times in a row",
    "🟠 Комментарии: дневной лимит проверок ({limit}) исчерпан": "🟠 Comments: the daily check limit ({limit}) is used up",
    "«{subject}»": '"{subject}"',
}

PLURALS: dict[str, tuple[str, str]] = {
    "проверку": ("check", "checks"),
    "пост": ("post", "posts"),
    "реакция": ("reaction", "reactions"),
    "подписка": ("join", "joins"),
    "отписка": ("leave", "leaves"),
}

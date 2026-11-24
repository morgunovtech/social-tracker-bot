"""English for bot/reporter, bot/tofs_status, bot/updates and the platform
labels (see bot/i18n.py)."""

from __future__ import annotations

STRINGS: dict[str, str] = {
    # --- bot/reporter.py: the daily report
    "{delta} за день": "{delta} today",
    "{delta} за неделю": "{delta} this week",
    "{delta} за месяц": "{delta} this month",
    "📊 Подписчики · {date}": "📊 Followers · {date}",
    "🟠 LinkedIn cookie истёк — обнови через /setcookie": "🟠 The LinkedIn cookie has expired — renew it via /setcookie",
    "🟠 LinkedIn cookie живёт уже {age} дн. — пора обновить: /setcookie":
        "🟠 The LinkedIn cookie is {age} days old — time to renew it: /setcookie",
    "🟠 Instagram подключён, но токена нет — пришли его через /igtoken":
        "🟠 Instagram is connected but there is no token — send it with /igtoken",
    "🟠 Instagram отклонил токен — пришли новый через /igtoken":
        "🟠 Instagram rejected the token — send a new one via /igtoken",
    "{label} — пока нет данных: число вводится вручную": "{label} — no data yet: the number is entered by hand",
    "{label} — по cookie получено {count}: первое значение подтверди вручную — /linkedin {raw}": (
        "{label} — the cookie read {count}: confirm the first value by hand — /linkedin {raw}"
    ),
    "{label} — пока нет данных: нужен токен, см. /igtoken": "{label} — no data yet: a token is needed, see /igtoken",
    "{label} — ⚠️ собрать не удалось": "{label} — ⚠️ collection failed",
    "🔮 {label}: {goal} примерно через {weeks} нед. (+{rate} в неделю)":
        "🔮 {label}: {goal} in about {weeks} wk. (+{rate} a week)",
    "⚡ {label}: растёт в {ratio} раза быстрее, чем обычно за месяц":
        "⚡ {label}: growing {ratio}× faster than its monthly average",
    "🐌 {label}: рост замедлился — {rate} в неделю против обычных ~{avg:.0f}":
        "🐌 {label}: growth has slowed — {rate} a week against the usual ~{avg:.0f}",
    "🟠 введено вручную {date} — пора обновить": "🟠 entered by hand on {date} — time to update it",
    "введено вручную {date}": "entered by hand on {date}",
    "🟠 данные от {date} — свежие собрать не удаётся": "🟠 data from {date} — fresh data cannot be collected",
    "⚠️ сегодня собрать не удалось": "⚠️ today's collection failed",
    "Данных пока нет — нажми «🔄 Обновить данные» или отправь /now.":
        'No data yet — tap "🔄 Refresh data" or send /now.',
    "📈 Всего — {total}": "📈 Total — {total}",
    "🎯 {label} перешагнул {milestone}!": "🎯 {label} passed {milestone}!",
    "🏆 Лидер недели: {label}, {pct}": "🏆 Leader of the week: {label}, {pct}",
    # --- the weekly report
    "📅 Неделя {start} — {end}": "📅 Week {start} — {end}",
    "В сравнении с концом прошлой недели": "Compared with the end of last week",
    "{label} — {count} ({delta}, было {prev})": "{label} — {count} ({delta}, was {prev})",
    "{label} — {count} (за прошлую неделю данных нет)": "{label} — {count} (no data for last week)",
    "📅 Неделя\n\nДанных пока нет — недельное сравнение появится после первых сборов.":
        "📅 Week\n\nNo data yet — the weekly comparison appears after the first collections.",
    " ({delta} за неделю)": " ({delta} this week)",
    # --- the month digest
    "январь": "January",
    "февраль": "February",
    "март": "March",
    "апрель": "April",
    "май": "May",
    "июнь": "June",
    "июль": "July",
    "август": "August",
    "сентябрь": "September",
    "октябрь": "October",
    "ноябрь": "November",
    "декабрь": "December",
    "🗓 Итоги месяца — {month} {year}": "🗓 Month in review — {month} {year}",
    "{label} — {count} (нет данных на начало месяца)": "{label} — {count} (no data for the start of the month)",
    "🏆 Лучшая платформа: {label}, {pct}": "🏆 Best platform: {label}, {pct}",
    "🐌 Слабее всех: {label}, {pct}": "🐌 Weakest: {label}, {pct}",
    "📈 Всего — {total} ({delta} за месяц)": "📈 Total — {total} ({delta} this month)",
    # --- history tables
    "<b>📋 Все платформы · {days} дн.</b>": "<b>📋 All platforms · {days} d.</b>",
    "За последние {days} дн. данных нет.": "No data for the last {days} days.",
    "Дата": "Date",
    " (поместились последние {n} дн.)": " (only the last {n} days fit)",
    "<b>📋 {label} · {days} дн.</b>": "<b>📋 {label} · {days} d.</b>",
    "Подписчики": "Followers",
    "Изменение": "Change",
    # --- bot/tofs_status.py: the lines on the TofsDevOps main screen
    "Соцсети": "Social networks",
    "профиль не читается — удалён, скрыт или у бота отобрали права?":
        "profile unreadable — deleted, hidden, or did the bot lose its rights?",
    "cookie истёк — обнови через /setcookie": "cookie expired — renew it via /setcookie",
    "по cookie получено {count} — подтверди: /linkedin {raw}": "the cookie read {count} — confirm: /linkedin {raw}",
    "токен истёк — пришли новый через /igtoken": "token expired — send a new one via /igtoken",
    "нет токена — пришли его через /igtoken": "no token — send it via /igtoken",
    "собрать не удалось": "collection failed",
    "пока нет данных": "no data yet",
    ", {delta} за сутки": ", {delta} today",
    "{head} — введено вручную {days} дн. назад": "{head} — entered by hand {days} days ago",
    "{head} — свежие данные собрать не удаётся": "{head} — fresh data cannot be collected",
    "{head} — сегодня собрать не удалось": "{head} — today's collection failed",
    "{head} — cookie живёт {days} дн., пора обновить": "{head} — the cookie is {days} days old, time to renew it",
    # --- bot/behavior.py: what an update moved in how the bot behaves
    "ℹ️ После обновления я работаю иначе — это поменяла новая версия, а не ты:":
        "ℹ️ Since the update I work differently — the new version changed this, not you:",
    "Если так не нужно — поменяй кнопкой ниже.": "If that is not what you want, change it with a button below.",
    "{days}, {time} по поясу {zone}": "{days}, {time} in the {zone} zone",
    "• Отчёт: {now} — было {before}": "• Report: {now} — was {before}",
    "• Тихие часы: {now} — было {before}": "• Quiet hours: {now} — were {before}",
    "• «Коротко без изменений»: {now} — было {before}": "• «Short when unchanged»: {now} — was {before}",
    "• Проверка «{label}»: {now} — была {before}": "• The «{label}» check: {now} — was {before}",
    "• Новая проверка включена: {label} — {what}": "• A new check is on: {label} — {what}",
    "• Письма «{title}» теперь распознаю: {level}": "• I now recognise «{title}» mails: {level}",
    "• Письма «{title}»: {now} — было {before}": "• «{title}» mails: {now} — were {before}",
    "• {label}: {now} — было {before}": "• {label}: {now} — was {before}",
    "🔴 звонит": "🔴 rings",
    "🟠 без звука": "🟠 silent",
    "включена": "on",
    "выключена": "off",
    "падение подписчиков — тревога от стольких за сутки": "a drop in followers — an alert from this many a day",
    "падение подписчиков — и от такой доли, %": "a drop in followers — and from this share, %",
    "сбор не удаётся — тревога на такой день подряд": "collection fails — an alert on this day in a row",
    "профиль не читается — тревога после стольких проверок подряд":
        "the profile can't be read — an alert after this many checks in a row",
    "почтовый воркер молчит — тревога после стольких опросов подряд":
        "the mail worker is silent — an alert after this many polls in a row",
    "опасный комментарий звонит при уверенности от, %": "a dangerous comment rings from this confidence, %",
    (
        "• Отчёт: {now}. До версии {version} это же время считалось по UTC — {then} по этому поясу: "
        "с {version} пояс, пока его не выбрали, следует языку бота. Я не знаю, где ты, — выбери свой пояс, "
        "отчёт останется в тот же момент, а время поправишь кнопкой «🕗 Время отчёта»."
    ): (
        "• Report: {now}. Before version {version} the same time was read in UTC — {then} in this zone: "
        "since {version} the zone follows the bot's language until one is chosen. I don't know where you are — "
        "pick your zone, the report stays at the same moment, and set the time with «🕗 Report time»."
    ),
    # --- bot/reputation/: the weekly reputation report
    "Яндекс": "Yandex",
    "🔍 {source}: {shows} {shows_word}, {clicks} {clicks_word} по брендовым запросам{change}":
        "🔍 {source}: {shows} {shows_word}, {clicks} {clicks_word} on brand queries{change}",
    "🤖 ИИ-ассистенты открывали твои страницы {n} {times}{change}": "🤖 AI assistants opened your pages {n} {times}{change}",
    "чаще всего — {host}": "most often — {host}",
    "👥 Подписчики: {total}, {delta} за неделю": "👥 Followers: {total}, {delta} this week",
    "это не тот ключ или он не читается": "it is not the right key, or it cannot be read",
    "у ключа нет доступа ни к одному сайту": "the key has access to no site",
    "не заданы брендовые слова": "no brand words are set",
    "на этом тарифе API этих данных не отдаёт": "the API does not give this data on this plan",
    "у ключа нет доступа ни к одному сайту — добавь {who} в пользователи ресурса":
        "the key has access to no site — add {who} as a user of the property",
    "⚠️ {source}: не смог получить данные — {reason}": "⚠️ {source}: could not get the data — {reason}",
    "🔎 <b>Репутация за неделю</b> · {start}–{end}": "🔎 <b>Reputation this week</b> · {start}–{end}",
    # --- bot/updates.py: the bot's own updates
    "  • сборка {old} → {new}": "  • build {old} → {new}",
    "🔄 Бот обновился:\n": "🔄 The bot has been updated:\n",
    "📄 Лог сборки": "📄 Build log",
    "🔗 Что в этой версии": "🔗 What is in this version",
    "🟠 Новая версия бота не запустилась\n"
    "Railway не смог выкатить «{title}» ({sha}). Я работаю на прежней "
    "версии ({running}), но и следующие обновления не встанут, пока сборка падает.\n\n"
    "Что делать: открой лог сборки — обычно там видно, какой пакет не поставился. "
    "Быстрый выход — откатить этот коммит в GitHub (Revert).":
        "🟠 The new version of the bot did not start\n"
        'Railway could not roll out "{title}" ({sha}). I am running the previous '
        "version ({running}), and the next updates will not land either while the build keeps failing.\n\n"
        "What to do: open the build log — it usually shows which package failed to install. "
        "The quick way out is to revert this commit on GitHub (Revert).",
    "🛡 В пакетах бота нашлись известные уязвимости:\n{listed}\n"
    "Dependabot откроет PR с исправлением; после мержа я напишу, что обновился.":
        "🛡 Known vulnerabilities were found in the bot's packages:\n{listed}\n"
        "Dependabot will open a PR with the fix; once it is merged I will say that I have updated.",
    "✅ Уязвимых зависимостей больше нет.": "✅ No vulnerable dependencies left.",
    "🔀 Ждёт твоего решения: {bump} — крупное обновление, само не вливается. "
    "Прочитай «что поменялось» и нажми Merge: {url}":
        "🔀 Waiting for your decision: {bump} — a major update, it does not merge on its own. "
        'Read "what changed" and press Merge: {url}',
    "🟠 Обновление не встало само — тесты не прошли: {bump} {url}":
        "🟠 An update did not land on its own — the tests failed: {bump} {url}",
    # --- bot/platforms/*: labels built at import time, translated where shown
    "аккаунт владельца канала": "channel owner's account",
    "название канала": "channel name",
    "@username канала": "channel @username",
    "описание канала": "channel description",
    "аватарка канала": "channel avatar",
    "доступ бота к списку админов": "bot's access to the admin list",
    "админы канала": "channel admins",
    # Stored values of the admin_access field; shown in a profile-change alert.
    "есть": "yes",
    "нет": "no",
    "Google-аккаунт канала": "the channel's Google account",
    "@handle канала": "channel @handle",
    "видео на канале": "videos on the channel",
    "аккаунт Instagram": "Instagram account",
    "имя профиля": "profile name",
    "описание профиля": "profile bio",
    "ссылка в профиле": "profile link",
    "публикаций": "posts",
    "аккаунт LinkedIn": "LinkedIn account",
}

# Russian singular → (English singular, English plural).
PLURALS: dict[str, tuple[str, str]] = {
    "подписчик": ("follower", "followers"),
    "показ": ("impression", "impressions"),
    "клик": ("click", "clicks"),
    "раз": ("time", "times"),
}

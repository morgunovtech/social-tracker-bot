# ⏱ Watchdog

Guide for people: https://github.com/morgunovtech/social-tracker-bot/blob/main/docs/connect/watchdog.en.md (Russian: watchdog.md). 2 minutes, free. The bot also offers it by itself after its first collection.

1. https://healthchecks.io — the user signs up / signs in.
2. «Add Check»: «Period» 1 day, «Grace Time» 3 hours. Check «Integrations» — email to the account by default.
3. Copy the ping URL `https://hc-ping.com/…`.
4. In the bot: «🔌 Подключения» → «⏱ Сторож» → «🔗 Прислать ссылку» (EN «⏱ Watchdog» → «🔗 Send the link») → the URL. The bot pings it at once and says whether it got through.

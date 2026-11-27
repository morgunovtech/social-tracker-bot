# 💬 Channel comments — paid

Guide for people: https://github.com/morgunovtech/social-tracker-bot/blob/main/docs/connect/comments.en.md (Russian: comments.md).

Say first: every comment is a paid Claude API request on the user's own key — about $0.01 per comment on Opus 5.5 (~$9/month at 30 comments a day). **You never enter card details or buy credits** — the user does that on console.anthropic.com.

1. https://console.anthropic.com — the user signs in. Recommend «Workspaces» → «Create Workspace» («Social Tracker») with a monthly spend limit (the user sets the amount).
2. «API Keys» → «Create Key» in that workspace. The key starts with `sk-ant-` and is shown once.
3. In the bot: «🛡 Безопасность» → «💬 Комментарии канала» → «🔑 Прислать ключ Claude» (EN «🛡 Security» → «💬 Channel comments» → «🔑 Send the Claude key»). Prefer that the user pastes it; the bot deletes the message and checks the key for free.
4. Telegram: add the bot to the channel's discussion group as an admin with «Delete messages» and «Ban users».
5. On the same screen pick the daily limit: 100 · 300 · 1000 · no limit.

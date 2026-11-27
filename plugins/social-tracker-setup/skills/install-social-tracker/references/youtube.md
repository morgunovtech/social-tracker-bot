# YouTube

Guide for people: https://github.com/morgunovtech/social-tracker-bot/blob/main/docs/connect/youtube.en.md (Russian: youtube.md). About 5 minutes; the key is free.

1. Channel id: https://studio.youtube.com → «Settings» → «Channel» → «Advanced settings» → «Channel ID» (24 characters, starts with `UC`). The user signs in to Google themselves.
2. https://console.cloud.google.com/ → project picker → «New project» (any name) → «Create». If Google asks to accept terms or add billing, stop: the user decides; the YouTube Data API needs no billing.
3. Search «YouTube Data API v3» → «Enable».
4. «APIs & Services» → «Credentials» → «Create credentials» → «API key». Then «Edit API key» → «API restrictions» → «Restrict key» → only «YouTube Data API v3» → «Save».
5. In the bot: «🔌 Подключения» → «➕ YouTube» (EN «🔌 Connections» → «➕ YouTube»): send the channel id, then the key. The bot checks the pair live and deletes the key's message. Ask before pasting the key yourself — it would be visible to you.

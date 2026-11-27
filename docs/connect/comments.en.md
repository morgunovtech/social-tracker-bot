# 💬 Channel comments

🇷🇺 [По-русски](comments.md) · [All connections](../SETUP.en.md#the-other-connections)

Telegram blocks a whole discussion group for drug sales, pornography, sexualization of minors, extremism and fraud in its comments. The bot looks at every new comment with a Claude model and sends you a card for such content with the buttons 🗑 delete, 🔨 delete and ban, ✅ all fine. **It never deletes or bans anything by itself** — only when you tap.

## What it costs and what you need

It is paid: every comment is a request to Claude on your key, and Anthropic bills you. About $0.01 per comment on the default model (Opus 5.5, at the prices of 27 Nov 2026): roughly $9 a month at 30 comments a day and up to $90 at 300. The bot shows the exact sum for the week on the «💬 Channel comments» screen.

You need an account at [console.anthropic.com](https://console.anthropic.com) with a card for API billing, and a Telegram channel with a discussion group already connected to the bot (🔌 Connections → «➕ Telegram»).

## Steps

1. **A Workspace of its own with a limit** (recommended). At console.anthropic.com → «Workspaces» → «Create Workspace», name it, for example, «Social Tracker». In its settings set a monthly spend limit — then a spam wave cannot become a big bill.
2. **The key.** «API Keys» → «Create Key», pick that workspace, copy the key — it starts with `sk-ant-`.
3. **In the bot:** 🛡 Security → 💬 Channel comments → «🔑 Send the Claude key» and send the key in one message. The bot deletes the message at once and checks the key with a free request: it says if the key was not accepted, has no access, or cannot use the model.
4. **Rights in the group.** Add the bot to the channel's discussion group as an admin with the rights «Delete messages» and «Ban users» — otherwise 🗑 and 🔨 won't work.
5. **The daily limit** is on the same screen: 100, 300 (the default), 1000 or no limit. When it is reached, the bot says so once and leaves the rest of the day's comments (UTC) unchecked.

Comments of the group's admins and your own are never checked.

## What the bot sends and where

Every new comment in the discussion group goes to the Claude API (`api.anthropic.com`): the text, the picture or a video / sticker thumbnail, the group's title, and whether it is the author's first message and whether it is a forward. The author's name, @username and id are not sent. At most three comments at a time and no more than the daily limit. Anthropic's API data retention applies to what is sent. The key is kept in the bot's database and never reaches the backup or the log.

## How to switch it off and remove it

Switch the check off with the button on «💬 Channel comments» or in ⚙️ Settings → 🧩 Monitors. To remove the key from the bot: «✏️ Claude key» → send «-». Revoke the key itself at console.anthropic.com → «API Keys»; the workspace can be archived.

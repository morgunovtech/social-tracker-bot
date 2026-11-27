# 📣 Telegram channel

🇷🇺 [По-русски](telegram.md) · [All connections](../SETUP.en.md#the-other-connections)

The simplest connection: the bot becomes an admin of your channel and sees the rest by itself — the subscriber count, who joined and left and through which link, every post and its reactions — and every half hour it compares the title, description, avatar and the list of admins. A stranger among the admins or a stranger's link in the description is a sign of a hijack; the bot tells you with a sound, even at night.

## How long it takes and what you need

Two minutes. You need a channel where you are the owner or an admin who can add admins.

## Steps

1. Open the channel → its name at the top → «Edit» (the pencil) → «Administrators» → «Add Admin».
2. Find your bot by its @username and add it. It needs no special rights — you can untick them all: the bot only reads.
3. In the bot: 🔌 Connections → «➕ Telegram» and send the channel's @username, a `t.me/…` link or an id like `-100…` (for a private channel).
4. The bot reads the subscriber count at once and says the channel is connected. The channel's report is the «📣 Channel» screen on the home screen.

## What the bot reads and where it goes

Everything comes through the Telegram Bot API, and only what Telegram shows any admin bot: the subscriber count, the title, description, avatar, the list of admins; joins and leaves — with the name and the invite link; posts and their reaction counts. Views, forwards and citations are not in the Bot API — they stay in Telegram's own statistics. None of it leaves your server. Joins and leaves with names are kept for 90 days.

## How to switch it off and remove it

🔌 Connections → «✏️ Telegram» → send «-». Then remove the bot from the channel's admins. To stop recording joins and posts without disconnecting the channel: ⚙️ Settings → 🧩 Monitors → «Life of the channel».

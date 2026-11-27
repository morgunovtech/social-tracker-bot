# Setup

🇷🇺 [По-русски](SETUP.md) · [Why](WHY.en.md) · [Every feature](FEATURES.en.md) · [README](../README.md)

A personal tool, shared as is: free and open source (MIT), and I use it every day. It is not a supported service — you set it up yourself; there is a step-by-step guide and a Claude skill that walks you through it in the browser. If enough people need it, I'll build a hosted version with nothing to install.

Below is the path in clicks: a bot in Telegram, Railway as the host, the first network. About ten minutes. Your own server instead of Railway is at the end.

## What it costs

The bot itself is free. It has to run around the clock somewhere:

- **Railway.** The first 30 days are a trial: $5 of credit, no card needed. To get the full trial (with unrestricted internet access), sign in to Railway with GitHub. After that, the Hobby plan: **$5 a month**, with $5 of usage included — enough for the bot. Hobby needs a regular (not prepaid) card that works for payments abroad.
- If you don't move to Hobby after the trial, the free plan ($1 a month) may not be enough for a bot that runs all day: it **stops without a word**, and Railway deletes a trial account's volume with the database 30 days after the trial ends.
- **Your own server** is free: any computer or VPS with Docker (the last section).
- **The comment check** (optional) is a paid Claude key on your own bill: about $0.01 per comment.

Railway's prices were checked against [docs.railway.com](https://docs.railway.com/reference/pricing/plans) on 27 Nov 2026 — check they haven't changed before you start.

## Step 1. A bot in Telegram

1. Open [@BotFather](https://t.me/BotFather) in Telegram and press «Start».
2. Send `/newbot`.
3. Send the bot's name — what it is called in the chat, for example «My tracker».
4. Send a username — Latin letters ending in `bot`, for example `my_tracker_bot`. If it is taken, BotFather asks for another.
5. BotFather sends the token: digits, a colon and about 35 letters, like `123456789:AAH…`. Copy it. It is the key to the bot — don't show it to anyone.

## Step 2. Railway

1. Press the button [![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/social-tracker-bot?referralCode=7hTMqE). The link carries my Railway referral code: Railway shares with me a part of what an account created through it pays; your price is the same. The same template without the code: <https://railway.com/deploy/social-tracker-bot>.
2. Sign in to Railway — preferably with GitHub (see «What it costs»).
3. Press **Configure** — the Deploy button stays grey until you do — and paste the token into the `BOT_TOKEN` field. It is the only field.
4. Press **Deploy** and wait a couple of minutes until the service is active.
5. To check that the bot started: in the project, open the service → **Deployments** → **View Logs** — there should be a line `Bot ready`.

## Step 3. The first /start

Open your bot (`t.me/<the bot's username>`) and press «Start». The bot answers «✅ This bot is yours now» — the first person to press `/start` becomes the owner, and the bot answers nobody else. So do it right after the setup.

The bot takes its language from your Telegram: Russian stays Russian (so do Uzbek, Kazakh, Kyrgyz, Tajik and Belarusian — then the zone is set by the country too), any other becomes English. To change it: ⚙️ Settings → «🗣 Language».

## Step 4. The first network

In its second message the bot opens 🔌 Connections. The easiest start is a Telegram channel: make the bot an admin of the channel and send its @username — step by step: [connect/telegram.en.md](connect/telegram.en.md). Then pick your time zone (home → «🌍 Choose the time zone») so the report comes in your morning. After the first collection the bot offers the watchdog by itself.

## The other connections

Each one is a button in 🔌 Connections; each has a step-by-step page:

| What | How long | Page |
|---|---|---|
| ▶️ YouTube | 5 minutes, a free Google key | [connect/youtube.en.md](connect/youtube.en.md) |
| 📸 Instagram | about 15 minutes in Meta's dashboard | [connect/instagram.en.md](connect/instagram.en.md) |
| 💼 LinkedIn | a minute: the number by hand | [connect/linkedin.en.md](connect/linkedin.en.md) |
| ⏱ Watchdog | 2 minutes, free | [connect/watchdog.en.md](connect/watchdog.en.md) |
| ✉️ Security emails | about 15 minutes, a separate mailbox | [connect/mail.en.md](connect/mail.en.md) |
| 💬 Channel comments | 5 minutes, a paid Claude key | [connect/comments.en.md](connect/comments.en.md) |
| 🔎 Reputation report | only for site owners | [connect/reputation.en.md](connect/reputation.en.md) |

## If something went wrong

- **The bot says «This is a personal bot».** Someone pressed `/start` before you. Get your id from [@userinfobot](https://t.me/userinfobot), then on Railway: the service → **Variables** → **New Variable**, name `ADMIN_CHAT_ID`, value — your id. Railway restarts the bot, and it answers only you. The bot then doesn't take the language from Telegram — pick it in ⚙️ Settings.
- **The bot is silent.** Railway → the service → **Deployments** → **View Logs**. No `Bot ready` line, but `Telegram refused BOT_TOKEN` or `BOT_TOKEN is not a bot token` — the token was copied in part or revoked: get it again from @BotFather and change it under **Variables**.
- **The bot stopped answering after a month.** Most likely Railway's trial ended: open Railway → **Usage** and move to Hobby. To hear about such a stop at once, connect the ⏱ Watchdog.
- **Updates.** When a new version is out, Railway offers to update the project right there — accept it, and after the restart the bot says «🔄 The bot has been updated».
- **How to remove it.** Delete the project on Railway (the project's settings → delete; the database goes with it) and the bot at @BotFather with `/deletebot`. Delete the keys you made for the connections where you made them — each `connect/` page says how.

## Your own server

On a computer or VPS with Docker the bot is set up with one command — it asks for the token, pulls the image and starts the bot:

```bash
curl -fsSL https://raw.githubusercontent.com/morgunovtech/social-tracker-bot/main/scripts/install.sh | sh
```

Or by hand with `docker compose` — see the [README](../README.md#setup). The rest is the same: `/start`, the first network.

<!-- The listing of the Railway template social-tracker-bot (railway.com/deploy/social-tracker-bot).
     Railway keeps its own copy: after editing this file, paste the part below
     the line into Workspace → Templates → Social Tracker Bot → Marketplace →
     Overview. Category: Bots. Icon: docs/images/template-icon.png
     (the listing); the service icon inside the template is
     docs/images/template-icon-transparent.svg.
     Description (25–75 characters):
     A personal tool, shared as is: followers + account security in Telegram
     The service has one variable, BOT_TOKEN, and a volume at /app/data. The
     variable's description:
     The token from @BotFather: digits, a colon and about 35 letters (123456789:AAH…). The only field you fill in — the networks are connected in the chat.
     DB_PATH is not a variable: the default, data/followers.db under WORKDIR
     /app, is already the volume. -->

---

# Deploy and Host Social Tracker Bot on Railway

Social Tracker Bot is a self-hosted Telegram bot for your own social accounts: followers on Telegram, YouTube, Instagram and LinkedIn, the life of your channel, and the accounts' security — hijack signs, security emails, risky comments — plus a weekly report on how people and AI assistants find you. It stays quiet while things are fine.

It is a personal tool, shared as is: free and open source (MIT), and its author uses it every day. It is not a supported service — you set it up yourself, and the repository has a step-by-step guide for that. If enough people need it, a hosted version with nothing to install may follow.

## About Hosting Social Tracker Bot

The template deploys one service built from the open-source repository, with a volume at `/app/data` for its SQLite database. You fill in one field: the bot token from @BotFather. Then you send the bot `/start` in Telegram — the first person to do so becomes its owner, and the bot answers nobody else. Every network is optional and is connected in the chat with buttons: the bot checks each value and starts collecting without a restart. The bot speaks English or Russian and picks the language from your Telegram at the first `/start`. It needs no public domain.

Two parts need more than the token: the comment check uses your own Claude API key, billed by Anthropic for every comment it checks, and the security-email alerts need a separate setup described in the guide.

What it costs: Railway's trial gives $5 for 30 days without a card; after that the Hobby plan is $5 a month with $5 of usage included and needs a payment card. The same bot runs for free on your own server from the Docker image below.

## Common Use Cases

- One daily collection and one weekly report of your follower counts across four networks, with deltas, a 30-day chart, milestones and a forecast
- An alert within half an hour when a profile is renamed, gets a new admin or a strange link — the first signs of a hijacked account
- The life of your Telegram channel: who joined and left, through which invite link, every post and its reactions
- A weekly reputation report: how often your name was searched for, and how often AI assistants opened your pages
- A security checklist per account with a score, and a weekly backup of the database sent to your chat without secrets

## Dependencies for Social Tracker Bot Hosting

- A Telegram bot token from [@BotFather](https://t.me/BotFather) — the only field you fill in
- A Railway volume at `/app/data` (already in the template) — without it the history is lost on every deploy

### Deployment Dependencies

- Source code, the setup guide, changelog, privacy and security notes: [github.com/morgunovtech/social-tracker-bot](https://github.com/morgunovtech/social-tracker-bot)
- Optional, connected later from the chat or explained in the [README](https://github.com/morgunovtech/social-tracker-bot#setup): a YouTube Data API key, an Instagram token of your own Meta app, the LinkedIn count typed in by hand, a Claude API key for the comment check (paid)
- Prefer your own server? The same bot runs from a published Docker image: `ghcr.io/morgunovtech/social-tracker-bot`

### Implementation Details

Updates: when a new version is merged, Railway offers the update inside your project — accept it and the bot redeploys, then tells you in the chat what changed. Removing it: delete the Railway project (the volume goes with it) and the bot at @BotFather.

## Why Deploy Social Tracker Bot on Railway?

<!-- Recommended: Keep this section as shown below -->
Railway is a singular platform to deploy your infrastructure stack. Railway will host your infrastructure so you don't have to deal with configuration, while allowing you to vertically and horizontally scale it.

By deploying Social Tracker Bot on Railway, you are one step closer to supporting a complete full-stack application with minimal burden. Host your servers, databases, AI agents, and more on Railway.
<!-- End recommended section -->

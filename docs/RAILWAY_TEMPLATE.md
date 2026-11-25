<!-- The listing of the Railway template cL4hpn (railway.com/deploy/cL4hpn).
     Railway keeps its own copy: after editing this file, paste the part below
     the line into Workspace → Templates → Social Tracker Bot → Marketplace →
     Overview. Category: Bots. Icon: docs/images/template-icon.png.
     Description (25–75 characters):
     Followers + account security for Telegram, YouTube, Instagram, LinkedIn. -->

---

# Deploy and Host Social Tracker Bot on Railway

Social Tracker Bot is a self-hosted Telegram bot for your own social accounts: followers on Telegram, YouTube, Instagram and LinkedIn, the life of your channel, and the accounts' security — hijack signs, security emails, risky comments — plus a weekly report on how people and AI assistants find you. It stays quiet while things are fine.

## About Hosting Social Tracker Bot

The template deploys one service built from the open-source repository, with a volume at `/app/data` for its SQLite database. You fill in one field: the bot token from @BotFather. Then you send the bot `/start` in Telegram — the first person to do so becomes its owner, and the bot answers nobody else. Every platform is optional: connect only the ones you have. The Instagram token, the LinkedIn cookie, the watchdog and the reputation report are set up in the chat; the Telegram channel, the YouTube key and the other identifiers are service variables you add later. The bot speaks English or Russian and picks the language from your Telegram at the first `/start`. It needs no public domain and no other services.

## Common Use Cases

- One daily collection and one weekly report of your follower counts across four networks, with deltas, a 30-day chart, milestones and a forecast
- An alert within minutes when a profile is renamed, gets a new admin or a strange link — the first signs of a hijacked account
- The life of your Telegram channel: who joined and left, through which invite link, every post and its reactions
- A weekly reputation report: how often your name was searched for, and how often AI crawlers read your site
- A security checklist per account with a score, and a weekly backup of the database sent to your chat without secrets

## Dependencies for Social Tracker Bot Hosting

- A Telegram bot token from [@BotFather](https://t.me/BotFather) — the only required variable
- A Railway volume at `/app/data` (already in the template) — without it the history is lost on every deploy

### Deployment Dependencies

- Source code, changelog, privacy and security notes: [github.com/morgunovtech/social-tracker-bot](https://github.com/morgunovtech/social-tracker-bot)
- Optional keys, each explained in the [README](https://github.com/morgunovtech/social-tracker-bot#setup): a YouTube Data API key, an Instagram token of your own Meta app, a LinkedIn cookie, an Anthropic API key for the comment check
- Prefer your own server? The same bot runs from a published Docker image: `ghcr.io/morgunovtech/social-tracker-bot`

### Implementation Details

Updates: when a new version is merged, Railway offers the update inside your project — accept it and the bot redeploys, then tells you in the chat what changed. Removing it: delete the Railway project (the volume goes with it) and the bot at @BotFather.

## Why Deploy Social Tracker Bot on Railway?

<!-- Recommended: Keep this section as shown below -->
Railway is a singular platform to deploy your infrastructure stack. Railway will host your infrastructure so you don't have to deal with configuration, while allowing you to vertically and horizontally scale it.

By deploying Social Tracker Bot on Railway, you are one step closer to supporting a complete full-stack application with minimal burden. Host your servers, databases, AI agents, and more on Railway.
<!-- End recommended section -->

# Every feature

🇷🇺 [По-русски](FEATURES.md) · [Setup](SETUP.en.md) · [Why](WHY.en.md) · [README](../README.md)

## What you get

The bot is modular: connect only the platforms you have, and switch monitors on or off in `/modules`.

**Followers**

- **Daily collection, weekly report**: deltas for the day / week / month, a 14-day sparkline, a 30-day PNG chart, the week's leader by growth, a monthly digest on the 1st. The report comes on the days and at the time you choose, in your time zone (Saturday, 08:00 by default, in the zone of the interface language: `Europe/Moscow` with `BOT_LANG=ru`, UTC with `en`). Every platform is optional — connect only the ones you have.
- **Life of the channel** (Telegram, the bot as a channel admin): who joined and who left for 24 hours, 7 and 30 days, through which invite link they came, every post and the reactions it gathered, the most reacted posts of the month, the latest events with names — the part of TGStat an admin bot can do by itself, on your own server. One line of it in every report. Views, forwards and the citation index are not in the Bot API: those stay in Telegram's own statistics.
- **Signals, not noise**: milestones (100, 250, 500, 1,000, 2,500, 5,000, 10,000…) on the day they're crossed, a forecast to the next one, growth speeding up or slowing down, a bot-influx detector (a day's gain of 30 or more that is ×5 the usual daily gain; with under three days of history, 30 or more and at least 3 %).
- **Problems arrive at once**: a revoked Instagram token or an expired LinkedIn cookie, collection failing 2+ days in a row, a drop in followers (20 or more, or at least 1%), data that has gone stale.
- **Self-recovering**: a failed platform is retried hourly, 3 attempts in all, a run missed while the bot was down is caught up on start, a dead man's switch tells you when the bot itself dies — set from the chat (🔌 Connections → ⏱ Watchdog) with a live test ping that reads the answer, or with `HEALTHCHECK_URL`. Point it at a [TofsDevOps](https://github.com/morgunovtech/Tofs_DevOps_bot) heartbeat address and the ping also carries a line per network («✅ Telegram · 12 340, +18 today», «🔴 LinkedIn · profile unreadable») to TofsDevOps's main screen, next to your sites; refreshed after every profile check.
- **Watches what it sends out, too**: the counts pushed to your site, the lines to TofsDevOps and the watchdog's mark. A day without one that landed is one 🟠 that says where and why («🟠 s.example.com has not accepted the follower counts for 1 d: answers with error 401»), the first one that lands after it one ✅ with how long it did not; the «📤 Deliveries» lines on ⚙️ Settings (there when a site push or a watchdog is set) say when each last landed. The push to your site waits until every connected network has its number for the day. A log line alone is not a notification (monitor «Outgoing deliveries» in `/modules`).
- **Your data stays yours**: SQLite on your volume, a weekly backup sent to your chat (on Sundays, without any stored secret — cookie, tokens, keys, the watchdog address), and `/restore` to merge a backup back without overwriting anything collected since.
- **Short when unchanged**: a one-liner instead of the full report when nothing changed.
- **Three buttons under the input field** — 🏠 Home, 📖 What I do, ❓ Icons — one tap from anywhere, however far up the menu has scrolled; «🔄 Refresh data» and «🔕 Mute…» are on the home screen. No ☰ command list: commands still work when typed, and «📖 What I do» lists them all. Every alert and report carries buttons to where to look into it (🛡 Security, 📈 Trends, 📣 Channel); every message that comes without a sound from a monitor also «⚙️ Stop sending these».
- **Rings only when it matters**: 🔴 — a likely hijack, a new sign-in, a changed password, a vanished profile, a silent mail worker — rings at once, even at night; everything else arrives silently, and during quiet hours or a `/mute` it waits and comes as one digest. One set of icons everywhere, the same as TofsDevOps's: see [Icons](#icons) and [When it writes](#when-it-writes).
- **Instagram** — through the official API, with a non-expiring token of your own Meta app (`/igtoken`); **LinkedIn** — by itself with the `li_at` cookie (`/setcookie`) or by hand with a button.

**Security**

- **Profile integrity**, every 30 minutes: a hijacked channel is renamed, gets a scam link in its description, a new admin or loses its videos long before the follower count moves. The bot alerts on a changed title or name, @username, description or bio, avatar, a new or removed Telegram admin, a changed owner, a mass drop in YouTube videos or Instagram posts, and a profile that stops being readable. A link that appears in a description is 🔴 with «looks like a hijack» in the headline: that is the classic hijack payload. The first look at a profile only records the baseline.
- **The weekly reputation report** (optional, each source connected in the chat with a read-only key of the bot's own — 🔌 Connections → 🔎 Reputation): how often you and your products were searched for on Google (Search Console) and Yandex (Webmaster) — impressions and clicks of the queries that match your brand words, with the top ones; how often AI assistants opened your pages (Cloudflare: requests by the user agents Cloudflare files under «AI Assistant» — ChatGPT-User, Claude-User, Perplexity-User, MistralAI-User, Meta-ExternalFetcher, DuckAssistBot; the API has no «AI Answer retrievals» metric, so this is a count by user agent and a spoofed one counts too); next to the follower growth. Each week against the one before, two whole weeks ending three days ago (Search Console fills a day in two or three). One message a week, nothing when there is nothing to say; a source that fails says so in the report. Each source is a monitor in `/modules`. The report says this under its AI line every week. The sites' clicks and impressions as a whole, indexing, robots and sitemaps are [TofsDevOps](https://github.com/morgunovtech/Tofs_DevOps_bot)'s — signs of breakage, not reputation; so is Bing (its API key is always full access, and that key lives in TofsDevOps only).
- **Where the profile links lead**, once a week: the links already in the descriptions (Telegram, YouTube, Instagram — the bio and the profile link under it, which the profile monitor now watches too) are followed hop by hop. 🟠 when one does not open — no such host, a refused certificate or connection, a missing page (404/410), a server error — checked again a minute later first (and when every link fails like a dead network, it is the bot's network, not the sites: nothing is said); ℹ️ in one note when one goes through a redirect to another host («morgunov.tech → s.morgunov.tech — the final address is better») or lands on a technical host (`*.pages.dev`, `*.workers.dev`). Each change once; a link that opens again gets one ✅. A site that refuses robots (401, 403, 429, LinkedIn's 999) is «could not check» and says nothing. Only public http(s) addresses are requested, never the bot's own network, and no page body is read. Monitor «Profile links» in `/modules`.
- **Security emails** (optional): forward your accounts' security notifications to a separate mailbox made for the bot (Gmail or Yandex, read over IMAP with an app password — 🔌 Connections → ✉️ Security emails), or to your own Cloudflare [mail-worker](../mail-worker/README.md) for the advanced, and the bot alerts within 5 minutes on a new sign-in, a password, email, phone or 2FA change, a new token, key or app, a password reset request or a login code you didn't ask for, with recovery links. Not only the social networks: the accounts that hold the products and the domain — GitHub, Microsoft, Yandex (Cloudflare's logins and tokens are TofsDevOps's, from the audit log) — and a new owner of your site in Search Console (🔴: a stranger there can remove the site from search). Which senders and subjects, and the filter to forward them: [docs/connect/mail.en.md](connect/mail.en.md). From the mailbox only mail the provider vouched for is read — its own Authentication-Results says `dkim=pass` for the sender's domain — and only from those senders; anything else stays unread in the box. Links quoted from a mail or a changed description are defanged (`hxxps://evil[.]example`), so nothing in an alert is a clickable scam link, and invisible direction marks are stripped from quoted text and names, so `evil.com` written backwards cannot pass for `google.com`. Gmail's forwarding confirmation is relayed to you — its code, or (Gmail's format since 2026) its own `mail.google.com/mail/vf-…` link and no other.
- **Comments of the channel** (optional, needs your own Claude API key — paid, sent in the chat on 💬 Channel comments, or `ANTHROPIC_API_KEY`): make the bot an admin of the channel's discussion group, and it looks at every comment with a Claude model and sends you a card for anything the whole group can be blocked for — drug sales, pornography, sexualization of minors, extremism, fraud — with the text, the author, why it was flagged and three buttons: 🗑 delete, 🔨 delete and ban, ✅ all fine. Spam is reported quietly (that is Defensy's job). **The bot only reports; nothing is deleted or banned without your tap.** Your taps are the marks the accuracy table in `/comments` is built from — the measurement any automatic action would have to be calibrated on first. A dangerous category at ≥ 70 % rings (🔴); the rest arrives at once, silently, and waits only during quiet hours or a mute. The group's admins and your own comments are never reviewed; a comment written under another channel's name (the usual face of a spam network) is reviewed like any other, and 🔨 bans that channel from the group — your own channel and anonymous admins are left alone. A comment edited after it was posted is looked at again — a card for what it says now, marked «✏️ edited after posting»; one you already deleted is not. A card Telegram does not take (a flood limit in a spam wave) waits in the queue and comes a minute later with its time, instead of being lost. When the API is down you hear once, and once when it is back; a failure is «could not check», never «fine».
- **Hygiene checklist** (`/security`): per account — 2FA and its kind, backup codes, recovery contacts, a unique password, the last password change; for Telegram, its own list — cloud password, its recovery email, only your own sessions, a unique password. A score out of 10 in every report, and a reminder at most once a month with what to fix. No network exposes this to third-party apps, so these are your own marks: **the checklist never asks for a password.**

## Privacy

What leaves your server and what does not, as the code does it:

| Where | What and why |
|---|---|
| Telegram Bot API | The bot's messages to you, and the public data of your channel (follower count, title, description, admins when the bot is a channel admin). As a channel admin the bot also receives what Telegram sends admins: every join and leave (who, and through which invite link), every post, and the reactions a post gathers. Nothing of that leaves your server. |
| YouTube Data API (`googleapis.com`) | Your channel's statistics with your own key, once a day. Only with a YouTube key — sent in the chat or `YOUTUBE_API_KEY`. |
| Instagram API (`graph.facebook.com`) | Your account's follower count and profile with your own token, once a day. Only with a token. |
| LinkedIn (`linkedin.com`) | Your profile page, opened with your `li_at` cookie once a day. Only with the cookie; without it you type the number in. |
| Watchdog (⏱ Watchdog or `HEALTHCHECK_URL`) | An empty ping after the daily run, and one test ping when you set the address — healthchecks.io or a TofsDevOps address; TofsDevOps also gets one status line per network (count, delta). Only when set; the address is kept out of the logs and the backup. |
| Your own site (`SITE_INGEST_URL`) | The final follower counts, POSTed with a Bearer token. Only when set. |
| OSV (`api.osv.dev`) | On Sundays, the names and versions of the bot's packages, to report known vulnerabilities. Only while «For the developer» is on in `/modules` (off on a new install); `UPDATE_WATCH=0` turns it off. |
| GitHub API (`api.github.com`) | The update watch (`bot/updates.py`): the newest commit on `main`, its deployments and their statuses — hourly, to tell a failed deploy — and the repository's open pull requests on Sundays, for the Dependabot PRs that wait for you. Only while «For the developer» is on in `/modules` (off on a new install), with `UPDATE_WATCH=1` and a repository name (Railway sets it by itself; elsewhere `GITHUB_REPOSITORY`). `GITHUB_TOKEN` is optional and only lifts the anonymous rate limit; the request carries the repository name and, if set, that token — nothing else. |
| Search Console API (`googleapis.com`) | Once a week, with the service account key you sent: the list of properties it was added to, and for each the queries that match your brand words (sent as one regular expression) for two weeks. Only when connected. |
| Yandex.Webmaster API (`api.webmaster.yandex.net`) | Once a week, with your OAuth token: your verified sites and their top queries for two weeks; the brand words never leave — they are matched here. Only when connected. |
| Cloudflare API (`api.cloudflare.com`) | Once a week, with your read-only token: your zones and, per zone, one request count per AI-assistant user agent per day for two weeks. Only when connected. |
| Your separate mailbox (`imap.gmail.com` / `imap.yandex.ru`) | Every 5 minutes, with its app password: the mails that arrived since the last poll, read without a mark, then the alerted ones marked read. Only when connected. |
| Your mail-worker | The bot fetches the security emails you forwarded yourself; the worker accepts only the senders in `ALLOWED_SENDERS`. Only when connected. |
| Claude API (`api.anthropic.com`) | Every new comment in the channel's discussion group — its text and picture (or a video / sticker thumbnail), the group's title, and whether it is the author's first message or a forward. No user id, name or @username. Only with a Claude key (sent in the chat or `ANTHROPIC_API_KEY`), and only for a group the bot is an admin of; comments are public to begin with; at most three at a time and the daily limit (300 by default; buttons on 💬 Channel comments or `COMMENTS_DAILY_LIMIT`). Anthropic's API data retention applies to what is sent. |
| The sites your profile descriptions link to | Once a week, every link found in the stored descriptions (Telegram, YouTube, Instagram) is requested hop by hop (`bot/monitors/links.py`): one GET per hop, redirects not followed blindly — the next host is checked to be a public address first, at most 10 hops — no page body read, under a User-Agent that names this repository. Those sites get the request itself and nothing of yours. Monitor «Profile links» in `/modules`. |

Everything else stays with you: follower history, the channel's joins, leaves, posts and reactions, profile baselines, checklist answers and security events live in SQLite on your volume. What names a person does not stay for ever: joins and leaves are dropped after 90 days, comments the model called fine (an author id and a verdict, no name or text) after 30, flagged ones with their card after 180. The Instagram token, the LinkedIn cookie, the watchdog address and the reputation report's three read-only keys — the Search Console service-account key, the Yandex OAuth token and the Cloudflare token — and the YouTube API key when it was sent in the chat are stored there too (`_SECRET_SETTINGS` in `bot/db.py`); the message carrying any of them is deleted from the chat at once, the Sunday backup is made without them, and none of them reaches a screen or a log line. Only the owner — the first `/start`, or `ADMIN_CHAT_ID` when set — can use the bot. Logs carry no Bot API URL with the token (the httpx logger stays at WARNING). Links quoted from mails and profile descriptions are defanged in alerts (`hxxps://evil[.]example`) and previews are off. Details: [SECURITY.md](../SECURITY.md).

## Setup

Every network is connected from the chat: 🔌 Connections → «➕ Telegram», «➕ YouTube», «➕ Instagram», «➕ LinkedIn». The bot asks for the value as the next message, checks it — with a live request where there is one — and starts collecting without a restart; «✏️» changes a network later, and «-» removes what was set in the chat — a value in `.env` then applies again. The variables named below still work and are the starting values: what is set in the chat wins over `.env`.

0. **Language.** Nothing to set: the first `/start` takes it from your Telegram, unless `ADMIN_CHAT_ID` is set (then `BOT_LANG`, Russian by default): Russian stays Russian; Uzbek, Kazakh, Kyrgyz, Tajik and Belarusian stay Russian too and set the report to Tashkent, Almaty, Bishkek, Dushanbe or Minsk time unless a zone was chosen; any other becomes English. A bot without a network answers the first `/start` with where to start and opens 🔌 Connections. `BOT_LANG=en` or `ru` fixes it beforehand, and ⚙️ Settings → «🗣 Language» switches it later — the choice made in the chat wins over `BOT_LANG`. It covers every screen, report and alert. The default time zone comes from `BOT_LANG` or the language the first `/start` took — UTC for English, Moscow for Russian (see [Schedule](#schedule)); switching the language later leaves the zone as it is. Switching is safe: the recent events on 🛡 Security are stored before translation and read in the new language too. The examples below show the Russian bot.
1. **Telegram (required).** Create a bot with [@BotFather](https://t.me/BotFather) (`/newbot`) → `BOT_TOKEN`, start it and send it `/start` right away: **the first person to do so becomes its owner**, and the bot answers nobody else. `ADMIN_CHAT_ID` (your user id, from [@userinfobot](https://t.me/userinfobot)) is optional: set it to pin the owner or to take the bot over; it wins over the stored one. To track a channel, make the bot an **admin** of it → `TELEGRAM_CHANNEL_ID`; as an admin it also sees who joins and leaves, every post and its reactions (the 📣 Channel screen).
2. **YouTube (optional).** In [Google Cloud Console](https://console.cloud.google.com/) enable YouTube Data API v3 and create an API key → `YOUTUBE_API_KEY`; your channel id (`UC…`) → `YOUTUBE_CHANNEL_ID`.
3. **Instagram (optional).** The account must be professional (Creator or Business: Settings → Account type in the app, free). On [developers.facebook.com](https://developers.facebook.com/) create an app with the Instagram use case (Meta also asks for a business portfolio: free, no verification needed for your own account), open «API setup with Unified login», create the configuration, give your account the **Instagram Tester** role, accept the invitation in Instagram (Settings → Website permissions → Tester invitations) and press **Generate token**. Your @username → `INSTAGRAM_USERNAME`, then send the bot `/igtoken <token>` — it checks that the token was granted for that account, deletes your message and keeps the token (or set `INSTAGRAM_ACCESS_TOKEN` in `.env`). How long the token lives depends on how Meta issued it (Instagram-login tokens live 60 days); when Meta rejects it, the bot says so once and in every report until a new one arrives. Step by step: [connect/instagram.en.md](connect/instagram.en.md). This is the official Instagram API: the bot reads only its own account's public data (followers, name, bio, post count) and watches those for a hijack.
4. **LinkedIn (optional).** Your profile URL → `LINKEDIN_PROFILE_URL`. Then either send the bot `/setcookie <li_at>` with the `li_at` cookie of a logged-in browser (DevTools → Application → Cookies → linkedin.com) — the bot checks it, deletes your message and watches the cookie's age: it lives about a year, after 330 days the bot reminds you to renew it, and a rejected cookie gets a message of its own — or set `LINKEDIN_LI_AT` in `.env`, or enter the number by hand with the «✏️ Enter LinkedIn count» button on the home screen (a number entered by hand is flagged 🟠 in the report as due for an update after `LINKEDIN_STALE_DAYS` days, 7 by default). The first number read by cookie is not stored by itself: the profile page carries other profiles' counters too, so the bot shows what it read and asks you to check it against your profile page and confirm with `/linkedin N`.
5. **Security emails (optional).** Make a separate Gmail or Yandex mailbox for the bot, create an app password for it, and set a filter in your main mailbox that forwards the security senders there; then 🔌 Connections → ✉️ Security emails → «📮 A separate mailbox (simple)»: the address, then the app password — the bot signs in to check it, deletes your message and reads only mail that arrives after that. Step by step: [docs/connect/mail.en.md](connect/mail.en.md). For the advanced: your own Cloudflare [mail-worker](../mail-worker/README.md) — «☁️ Your own Cloudflare worker», its address and token (checked live), or `SECURITY_MAIL_URL` and `SECURITY_MAIL_TOKEN`.
6. **Comments of the channel (optional, paid).** An API key from [console.anthropic.com](https://console.anthropic.com/) → API Keys → Create Key — best in a Workspace of its own with a spend limit — then 🛡 Security → 💬 Channel comments (or 🔌 Connections → 💬 Comments) → «🔑 Send the Claude key»: the bot checks it with a free request for the model, deletes your message and keeps the key out of the backup and the log (`ANTHROPIC_API_KEY` works too; the chat wins). The same screen says what the check cost over 7 days at Anthropic's list prices, or about what one comment costs before there is any data (≈ $0.01 on Opus 5.5), and sets the daily limit: 100, 300, 1000 or none. Step by step: [docs/connect/comments.en.md](connect/comments.en.md). Add the bot to the channel's discussion group as an **admin with the rights to delete messages and ban members** (the group is found through the channel; `COMMENTS_CHAT_ID` names one explicitly). The model is `claude-opus-5-5` unless `COMMENTS_MODEL` says otherwise. The daily limit (300 by default; `COMMENTS_DAILY_LIMIT`, 0 = none, is the starting value) caps the checks per day, so a spam wave cannot run up the bill — the bot says once when the day's limit is reached. Switch it off any time in `/modules`.
7. **Watchdog (optional, recommended).** Who tells you when the bot itself stops? Create a free [healthchecks.io](https://healthchecks.io) check (period 1 day, grace 3 hours), then in the bot: 🔌 Connections → ⏱ Watchdog → «🔗 Send the link». The bot pings it at once and reads the answer — a deleted check answers «OK (not found)» with HTTP 200, and the bot says so — then keeps the address in its database and deletes your message; after every daily run it checks in. A TofsDevOps heartbeat address works too. `HEALTHCHECK_URL` in `.env` is the fallback; an address set in the chat wins. The bot offers this once — as soon as the first network is connected or the first collection runs.
8. **Reputation report (optional).** 🔌 Connections → 🔎 Reputation: the brand words (your name and your products, the way people search for them), then a read-only key per source — a Google service account added to your Search Console property, a Yandex.Webmaster OAuth token, a Cloudflare API token with Zone Read and Analytics Read. Each «🔑» step says exactly where to get it and tests the key before keeping it; «📨 Report now» shows the week at once. Each source is a monitor in `/modules`.

Every variable, with a comment on what it does, is in [`.env.example`](../.env.example).

> ⚠️ **About LinkedIn.** There is no official API for a personal profile's follower count, so the bot opens your profile page with your cookie, once a day. LinkedIn's User Agreement prohibits automated access: use it at your own risk, LinkedIn may restrict the account. Leave the cookie out and type the number in by hand if you'd rather not take that risk.

### Docker Compose

**One command**, when Docker is already installed:

```bash
curl -fsSL https://raw.githubusercontent.com/morgunovtech/social-tracker-bot/main/scripts/install.sh | sh
```

It asks for the bot token, writes `.env` and `docker-compose.yml` into `~/social-tracker-bot` (another folder: `SOCIAL_TRACKER_DIR=…`) and starts the bot; run it again to update. Read it first if you like: [scripts/install.sh](../scripts/install.sh). The networks from [Setup](#setup) are connected in the chat afterwards.

**Or by hand.** Make a folder with two files — `.env` with one line, `BOT_TOKEN=<the token from @BotFather>` (every other variable is in [`.env.example`](../.env.example)), and `docker-compose.yml`:

```yaml
services:
  tracker-bot:
    image: ghcr.io/morgunovtech/social-tracker-bot:latest
    container_name: social-tracker-bot
    env_file: .env
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

Then `docker compose up -d`. With a clone of this repository the same is `cp .env.example .env`, the token into `BOT_TOKEN`, `docker compose up -d`.

`docker-compose.yml` pulls the image every green `main` publishes to `ghcr.io/morgunovtech/social-tracker-bot` (amd64 and arm64); to run your own changes, replace `image:` with `build: .` and add `--build`.

Logs: `docker compose logs -f`. Stop: `docker compose down`.

### Railway

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/social-tracker-bot?referralCode=7hTMqE)

The button carries my Railway referral code: Railway shares with me a part of what it bills an account created through it; your price stays the same. The same template without the code: <https://railway.com/deploy/social-tracker-bot>.

Press the button, then **Deploy Now** and **Configure** — the Deploy button stays grey until you do — paste the token into `BOT_TOKEN`, the only field, and press **Save Config**. The template creates the service from this repository with a volume at `/app/data`; the networks, the watchdog and the reputation report are connected in the chat afterwards (🔌 Connections). The comment check's Claude key and the security emails are connected in the chat too, so there is nothing more to fill in under **Variables**; the variables in `.env.example` still work as starting values.

**What it costs.** For the first 30 days Railway gives $5 and asks for no card. After that the account drops to the Free plan with $1 of usage a month, which a bot that runs around the clock can outgrow: when the credit ends the bot stops and nobody is told, and 30 days later Railway deletes the volume with the database. The Hobby plan is $5 a month and includes $5 of usage; it needs a card that works abroad. Railway's terms: [its docs](https://docs.railway.com/reference/pricing/free-trial). The free way is your own server, above.

**Updates.** Deployed with the button: Railway notices a new version and offers the update inside your project — accept it, and the bot says «🔄 The bot has been updated» after the restart.

By hand: create a service from this repository, set the variables from `.env.example`, and **attach a volume at `/app/data`** — without one the database is lost on every deploy.

The database lives in `./data` (on Railway, in the volume at `/app/data`). The container starts as root only to hand that directory to the unprivileged `appuser`, then drops root for good.

## Menu

Everything is a button away. Three buttons live under the input field: «🏠 Home» brings you home, «📖 What I do» says what the bot does and lists every command, «❓ Icons» explains the icons and what rings. A button of an older keyboard (📊 Menu or 🏠 Menu, 🔄 Refresh, 🔕 Quiet for 8 h) keeps doing what it did, and the first start after the update brings the new keyboard.

```
🏠 Home — the report, 🕒 the last collection, ⏭ the next report; on a fresh install «🧭 Left to set up»
├── 🔄 Refresh data — only once a network is connected
├── 📈 Trends · 🛡 Security
│   ├── 📈 → 🖼 30-day chart · 📋 By day (platform and period switched on the same screen)
│   └── 🛡 → a button per account → its checklist → one question at a time; 💬 Channel comments
│           💬 — mode and on/off (once there are a key and a channel), «🔑 Send the Claude key» / «✏️ Claude key»,
│              what the week cost, the limit 100 · 300 · 1000 · no limit, how many were checked, the accuracy
├── 📣 Channel (only with Telegram) · 🔌 Connections (while no network is connected, «🔌 Connect a network» instead)
│   ├── 📣 → the «Life of the channel» switch
│   └── 🔌 → «➕ <network>» for each one not connected
│           📸 Instagram (when connected) — «🔑 Send the token»
│           💼 LinkedIn (when connected) — «🔑 Send the cookie» · «✏️ Enter count by hand»
│           ⏱ Watchdog — «🔗 Send the link»; «🔄 Check again» once a watchdog is set; «⏏ Disconnect» when set in the chat
│           🔎 Reputation — «🏷 Brand words», «🔑 Google» · «🔑 Yandex» · «🔑 Cloudflare»; «📨 Report now» once a source is on
│           💬 Comments (the same screen) · ✉️ Security emails — «📮 A separate mailbox (simple)» / «✏️ Mailbox»,
│              «☁️ Your own Cloudflare worker (advanced)» / «✏️ Worker», «⏏ Disconnect the mailbox» / «⏏ Disconnect the worker»
│           «✏️ <network>» for each one connected
├── 🔌 Connect a network · 🌍 Choose the time zone · 📸 Instagram token · 💼 First LinkedIn count — a button per «Left to set up» item
├── ✏️ Enter LinkedIn count — while the number is typed in by hand
└── 🔕 Mute… (or 🔔 Unmute) · ⚙️ Settings
    └── ⚙️ — 📅 Report days · 🕗 Report time / 🌍 Time zone · 🗣 Language / Short when unchanged · 🔔 When to write /
           🧩 Monitors · 🔌 Connections / 📦 Backup now; in the text, the «📤 Deliveries» lines (when a site push or a watchdog is set), the version and the build
        ├── 🕗 → a grid of hours, minutes :00 :15 :30 :45, 🌍 Time zone;  🌍 → 13 presets, «✏️ Another zone…»
        ├── 🔔 → 🌙 23–08 · 🌙 00–09 · 🌙 off; 🔕 1 h · 4 h · 8 h · 1 day; 🔔 Unmute (while muted)
        └── 🧩 → a switch per check
📖 What I do · ❓ Icons — under the input field, as screens
```

The home screen also says when the data was last collected and, on a fresh install, what is left to set up — a first network, the time zone, the Instagram token, the first LinkedIn number — with a button for each; until a network is connected there is no «🔄 Refresh data», since there is nothing to collect. A tap answers right away with a short confirmation («Saved», «Short when unchanged: on»), a menu message is edited in place instead of piling up, and a button of an older version's menu opens the current one. A cookie, a token or a time zone that is not in the presets (a city — «Tashkent», «New York» — or a zone name) is asked for as the next message («🔑 Send the cookie» → paste it → the bot checks it and deletes the message), the same way the LinkedIn number is.

## Commands

No ☰ command list is published: the three buttons under the input field are the way in. Every command keeps working as a shortcut when typed, and «📖 What I do» (`/help`) lists them all; everything they do is also a button away.

| Command | What it does |
|---|---|
| `/start` | Greeting and the home screen; a bot without a network opens 🔌 Connections instead |
| `/now` | Collect now and show the report |
| `/week` | This week vs last week, with the chart |
| `/security` | Security score, the checklist per account, recent security events |
| `/settings` | Report schedule, time zone, 🗣 Language, short when unchanged, when to write, monitors, connections, backup now, the running build |
| `/connections` | Every network: connected or not, collected by itself or waiting for a token, a cookie, the first number; «➕»/«✏️» per network; the Instagram and LinkedIn screens |
| `/help` | What the bot does, where things are, every command — the «📖 What I do» screen |
| `/icons` | What each icon means and what rings — the «❓ Icons» screen |
| `/stats` | The home screen without the greeting |
| `/modules` | Connected platforms; switch monitors on and off |
| `/comments` | The channel's comments: mode, how many were checked, the accuracy table of your marks |
| `/channel` | Life of the channel: joins and leaves for 24 h / 7 / 30 days, where they came from, the most reacted posts, the latest events |
| `/history [platform] [days]` | Day-by-day table for one platform or `all`, up to 90 days (the combined table keeps the latest days that fit one message) |
| `/linkedin <number>` | Enter the LinkedIn number by hand; also how you confirm the first number read by cookie, which the bot shows but does not store on its own |
| `/settime HH:MM`, `/setday <days>` | Report time and day(s) in your time zone: `sat`, `mon,thu`, `mon-fri`, `daily`; without an argument, the hour buttons and the day checkboxes |
| `/settz <zone>` | Your time zone: a city (`/settz Berlin`, `/settz New York`) or a zone name such as `Europe/Moscow`; without an argument, a list of common ones |
| `/setquiet on\|off` | Short when unchanged: one line instead of the report when a week brought no change |
| `/mute <time>`, `/unmute` | Pause everything but the critical for `1h`, `8h` (the default), `30m`, `1d`, up to 7 days; what was held arrives as one digest when it ends. Also «🔕 Mute…» on the home screen and «🔕 Quiet for 8 h» under any alert |
| `/setcookie [li_at]`, `/cookieage` | Set the LinkedIn cookie (checked with a live request), check its age; without the value the bot asks for it as the next message, with «✖️ Cancel» |
| `/igtoken [token]` | Set the Instagram token (checked against the API, the message is deleted); without the value the bot asks for it as the next message |
| `/restore` | Merge the history back: send the `.db` file and confirm with the button, reply `/restore` to a backup message, or caption the file `/restore` |
| `/cancel` | Leave a text-input step (a number, a link, a key, a token, a time zone…) without saving — it works only inside a step; typed outside one, the bot answers that there is no such command |

All commands are owner-only — the first `/start`, or `ADMIN_CHAT_ID` when set.

## What a report looks like

```
📊 Followers · 23.11.2026

Telegram — 1 156  ▁▁▂▂▃▃▄▄▅▅▆▆▇█
+2 today · +14 this week · +60 this month

YouTube — 126  ▁▁▂▂▂▄▄▄▆▆▆███
0 today · +2 this week · +10 this month

Instagram — 180  ▁▁▂▂▃▃▄▄▅▅▆▆▇█
+1 today · +7 this week · +30 this month

LinkedIn — 4 981
entered by hand on 20.11

📈 Total — 6 443

🏆 Leader of the week: Instagram, +4.0%
🔮 Instagram: 250 in about 10 wk. (+7 a week)

📣 Channel, last 7 days: +14 joins · −3 leaves · 4 posts · 37 reactions

🛡 Security: 7 of 10 — /security
```

Problems come first («🟠 Instagram rejected the token — send a new one via /igtoken»), a milestone crossed that day gets its own line («🎯 Telegram passed 1 000!»), and with «Short when unchanged» on, a week without changes is one line.

## Schedule

Data is collected every day at the report time, and the report goes out on the report day(s). Time and days are in your time zone: pick it with the «🌍 Time zone» button in ⚙️ Settings or with `/settz`, and `/settime 09:00` means 09:00 on your clock, summer time included. Switching the zone keeps the report at the same moment and shows it on the new clock (08:00 UTC becomes 11:00 in Moscow).

`TIMEZONE`, `REPORT_HOUR`, `REPORT_MINUTE` and `REPORT_DOW` are the defaults until you change them in the bot: Saturday, 08:00. With `TIMEZONE` empty the zone follows the chat language — UTC for English, `Europe/Moscow` for Russian (`BOT_LANG`, or the language the first `/start` took from your Telegram). Older names still work: `REPORT_TZ` for `TIMEZONE` (read when `TIMEZONE` is empty), `REPORT_HOUR_UTC` for `REPORT_HOUR`. A schedule saved by a version without the zone setting stays in UTC until you pick a zone. Before 1.5.0 an empty zone meant UTC; a bot that kept its schedule that way (with `REPORT_HOUR_UTC`, say) hears once after the update that the same time is now read in the language's zone, with the buttons to pick yours. The date in the report's title, the 1st of the month for the digest and the Sunday of the backup follow your zone; the day-by-day follower history is kept on UTC days.

## When it writes

Every message to you goes through one door (`bot/notifier.py`) with three priorities, the same model as [TofsDevOps](https://github.com/morgunovtech/Tofs_DevOps_bot). The icon at the start of a line says how the message arrives:

| | Rings | Examples |
|---|---|---|
| **Critical** — 🔴 | yes, through quiet hours and `/mute` | looks like a hijack: a new admin or owner, a link in the description, a drop in videos or posts, a new sign-in, a changed or reset password, a changed email, phone or 2FA, a new token, key or app, a new owner of your site in Search Console; a profile that stopped being readable; the mail worker silent for ~30 min; a comment the group gets blocked for, at ≥ 70 % confidence; the ✅ after an unreadable profile or a silent mail worker |
| **Normal** — 🟠 ✅ ℹ️ 🎯 | no; waits during quiet hours and a mute | a changed title, description or avatar, an admin removed; a login code, an unrecognised mail (ℹ️); a drop in followers, a bot influx, a milestone; an expired cookie, a rejected or missing token, a failure streak; a spam comment or a low-confidence card, the comment check down or back; the ✅ after any of these; a profile link that does not open and its ✅; a failed deploy; a day of counts, status lines or watchdog marks that did not land, and its end; «🔄 The bot has been updated»; «ℹ️ Since the update I work differently» |
| **Digest** — 📊 | no; waits only during a mute | the weekly report, the ℹ️ note on profile links, the monthly digest, the weekly reputation report, the hygiene reminder, the one-time watchdog offer, the Sunday vulnerabilities notice. The backup file always comes at its time, even during a mute; the chart is skipped while the report it belongs to is held |

- **Quiet hours** are off by default: ⚙️ Settings → 🔔 When to write, presets 23:00–08:00 and 00:00–09:00 in your time zone. The weekly report is a digest itself, so it still comes at its time.
- **`/mute 8h`** (or «🔕 Mute…» on the home screen, or «🔕 Quiet for 8 h» under any alert) pauses everything but the critical; `/unmute` or the «🔔 Unmute» button on the home screen lifts it. The home screen says «🔕 Muted until 08:00» while it lasts.
- Under every alert and report: buttons to the screen where to look into it; under every silent message from a monitor (🟠, but also its ✅, a 🎯 milestone, an ℹ️ mail), «⚙️ Stop sending these» switches that monitor off. In a digest the items share one row.
- When the silence ends, what was held arrives as **one numbered digest of headlines** — one line per message, 🔴 first, then 🟠, then the rest, each with the time it happened. «ℹ️ N» under the digest sends item N whole, below it, with its own buttons («⚙️ Stop sending these» included); the full texts are kept for 7 days after the digest, never go into the Sunday backup, and a line with nothing more behind it gets no button. A card — a message whose buttons act on it, like a comment card or a failed deploy with its log — comes whole, after the digest. Nothing held is lost: a message leaves the queue only once Telegram took the digest with its line, and the queue lives in the database, so a restart changes nothing. More than eight «ℹ️» items, or a very long night, continue in a second message. Replies to your own taps and commands are not notifications and never wait.
- **Every alert has one shape**, the same as TofsDevOps's (`bot/humanize.py`): the headline (icon · what · what happened), what it means and what it usually is, what to do in two or three steps, the technical line last. One message per problem, each with its own «⚙️ Stop sending these».
- «Silent when healthy» stays: nothing repeats until it changes, and a recovery is told once, with how long it lasted from the first failed check: «✅ The mail worker is responding again. Was silent for 40 min (14:03–14:43). Nothing to do.» Messages that waited more than 10 minutes in Telegram while the bot was down are dropped on start, so old taps are not replayed; a dropped command that carried a secret (`/setcookie`, `/igtoken`) is deleted and asked for again. When the bot itself was down in between, it says the duration is a lower bound.

### Icons

One dictionary for alerts, screens, reports and the «❓ Icons» screen (`LEVEL_ICONS` in `bot/monitors/__init__.py`), the same as TofsDevOps's. The icon says how urgent; the words say what happened.

| Icon | Means | What the bot does |
|---|---|---|
| 🔴 | act now | rings, through quiet hours and `/mute` |
| 🟠 | act, but not today | silent; at night and while muted it waits for the digest |
| ✅ | fine · works again · on | |
| ⚠️ | could not check | tries again by itself, raises no alarm |
| ⏳ | waiting for the first check | |
| ℹ️ | a fact, not a problem | |
| ⬜ | off | a setting, a monitor |
| ➖ | not connected | a network or an integration without its key |
| ❓ | not marked | a checklist item without an answer |

A likely hijack has no icon of its own: it is 🔴 with «looks like a hijack» in the headline. 🔴 here is a hijack sign (a new admin or owner, a link in the description, vanished videos or posts, a new sign-in, a changed password, email or 2FA), an unreadable profile, a silent mail worker and a comment the group gets blocked for; an expired cookie, a rejected or missing token, collection failures and a drop in followers are 🟠.

## Updates

The bot keeps itself up to date without touching its own container:

1. **Dependabot** opens one grouped PR per week with every Python update and one for the base image (Saturday), and monthly PRs for the Actions and the mail-worker's npm packages (the worker is deployed by hand, so a merged bump reaches Cloudflare with the next `sh mail-worker/update.sh --deploy`).
2. **CI** tests each one: ruff, pytest on Python 3.12–3.15, `pip-audit`, a build of the production image that must start as `appuser`, and the mail-worker's tests and `npm audit`.
3. **Minor and patch updates and a new build of the same base image merge themselves** once CI is green (a new build brings Debian's fixes; its PR changes only the digest in `FROM`): the auto-merge job (`.github/workflows/dependabot-automerge.yml`) waits for the «lint · test · audit» and «mail-worker» check runs itself, so no branch rule is needed to hold it back; major ones, a new Python in the base image, the Actions and the npm packages wait for you. Branch protection on `main` requires the same five checks of every PR, yours included.
4. **Railway redeploys** from `main`.
5. **The bot tells you** what the pipeline can't: «🔄 The bot has been updated: aiohttp 3.14.3 → 3.14.4» after a deploy, always. Two more are for whoever maintains the code — the monitor «For the developer» in `/modules`: within an hour, if the newest commit failed to deploy and the bot is stuck on an older build; and on Sundays, known vulnerabilities (OSV) in its packages and Dependabot PRs waiting for a human. A bot deployed from the Railway template starts with it off — those are about someone else's repository; a bot that ran before 1.13.0 keeps it on. Silent when there's nothing to do.
6. **An update that changed how the bot behaves says so once** (`bot/behavior.py`). At every start the bot notes what it actually does — the report's days, time and zone, quiet hours, «Short when unchanged», which checks are on, which security mails ring, the thresholds of its alerts — next to what you set for it in the chat and in `.env`. When a value moved while nothing you set did, the new version moved it: one «ℹ️ Since the update I work differently…» with each change as «now — was before» and buttons to the settings (🌍 Time zone, 🕗 Report time, 🔔 When to write, 🧩 Monitors). A change you made yourself is not told back; a new check that starts on by default is named.

`UPDATE_WATCH=0` turns off the deploy watch and the Sunday message about vulnerabilities and waiting PRs; «🔄 The bot has been updated» after a deploy comes either way. On Railway the commit and the repository come from its own variables; elsewhere set `GITHUB_REPOSITORY` and build with `--build-arg APP_COMMIT=$(git rev-parse HEAD)`. `GITHUB_TOKEN` is optional and only lifts GitHub's anonymous rate limit (60 requests an hour per IP).

## Deleted accounts among the subscribers

Telegram says deleted accounts leave member lists by themselves; in practice they stay for months and pad the count. The Bot API cannot list members, so the cleanup is a separate script on MTProto, run by hand from your laptop, never by the bot:

```bash
pip install telethon
export TELEGRAM_API_ID=… TELEGRAM_API_HASH=…   # my.telegram.org → API development tools
export BOT_TOKEN=…                             # for --session bot
python scripts/clean_deleted.py @your_channel          # dry run: how many
python scripts/clean_deleted.py @your_channel --yes    # remove them
```

`--session bot` uses the bot's own account (it must be a channel admin); if Telegram refuses to list a channel's subscribers to a bot, `--session user` logs in with your own account once and keeps the session in `~/.social-tracker-clean-user.session`. One kick at a time with a pause; a long FloodWait stops the run, rerun later. The next day's report shows the drop — a true one — as a quiet 🟠 alert.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install --require-hashes --no-deps -r requirements-dev.txt   # ruff, pytest, pip-audit
.venv/bin/pip install --require-hashes --no-deps -r requirements.txt       # exactly what the image gets
.venv/bin/ruff check .
.venv/bin/pytest -q
```

The tests never touch the network: Telegram is a fake bot; LinkedIn, YouTube, the Instagram Graph API, the site push, TofsDevOps and the mail worker are local HTTP servers. The one exception is opt-in and never runs in CI: `LIVE_ANTHROPIC_API_KEY=sk-ant-… pytest -q tests/test_classifier_live.py` makes one real classification before a release, because a request shape the API refuses passes every fake. CI runs ruff, pytest on Python 3.12–3.15, `pip-audit`, a build of the production image and the mail-worker tests (`cd mail-worker && npm ci && npm test`).

A new network is one module in `bot/platforms/` (a `Platform` subclass: how to tell it's configured, how to read the follower count and, optionally, which public profile fields to watch) plus an entry in `PLATFORMS`. Monitors live in `bot/monitors/`. Every menu screen is a function in `bot/ui.py` (text and buttons, no Telegram calls); `bot/handlers.py` routes commands and button presses to them, and a test walks every button from the home screen.

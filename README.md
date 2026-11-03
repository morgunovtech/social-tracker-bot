# Social Tracker Bot

> A Telegram bot that watches your social accounts: followers on Telegram, YouTube and LinkedIn with weekly trends, and the account's security — profile changes a hijacker makes, new sign-ins and password changes from your security emails, and a 2FA/password checklist. It stays quiet while things are fine and speaks up the moment something breaks.

🇷🇺 [По-русски](README.ru.md)

The bot talks to you in Russian; the setup is the same in any language.

## What you get

The bot is modular: connect only the platforms you have, and switch monitors on or off in `/modules`.

**Followers**

- **Daily collection, weekly report**: deltas for the day / week / month, a 14-day sparkline, a 30-day PNG chart, the week's leader by growth, a monthly digest on the 1st. Every platform is optional.
- **Signals, not noise**: milestones (1k, 5k, 10k…) on the day they're crossed, a forecast to the next one, growth speeding up or slowing down, a bot-influx detector (a jump ×5 above the usual daily gain).
- **Problems arrive at once**: an expired LinkedIn cookie, collection failing 2+ days in a row, a drop in followers, data that has gone stale.
- **Self-recovering**: failed platforms are retried hourly (up to 3 times), a run missed while the bot was down is caught up on start, a dead man's switch (`HEALTHCHECK_URL`) tells you when the bot itself dies.
- **Your data stays yours**: SQLite on your volume, a weekly backup sent to your chat (without the LinkedIn cookie), and `/restore` to merge a backup back without overwriting anything collected since.
- **Quiet mode**: a one-liner instead of the full report when nothing changed.

**Security**

- **Profile integrity**, every 30 minutes: a hijacked channel is renamed, gets a scam link in its description, a new admin or loses its videos long before the follower count moves. The bot alerts on a changed title, @username, description, avatar, a new or removed Telegram admin, a changed owner, a mass drop in YouTube videos, and a profile that stops being readable.
- **Security emails** (optional, needs the [mail-worker](mail-worker/README.md)): forward your accounts' security notifications to a Cloudflare Email Worker, and the bot alerts within 2 minutes on a new sign-in, a password, email or 2FA change, a password reset request or a login code you didn't ask for, with recovery links. Gmail's forwarding confirmation is relayed to you.
- **Hygiene checklist** (`/security`): per account — 2FA and its kind, backup codes, recovery contacts, a unique password, the last password change. A score out of 10 in every report, and a reminder at most once a month with what to fix. No network exposes this to third-party apps, so these are your own marks: **the bot never asks for a password.**

## Setup

1. **Telegram (required).** Create a bot with [@BotFather](https://t.me/BotFather) → `BOT_TOKEN`. Get your user id from [@userinfobot](https://t.me/userinfobot) → `ADMIN_CHAT_ID`: only you can use the bot. To track a channel, make the bot an **admin** of it → `TELEGRAM_CHANNEL_ID`.
2. **YouTube (optional).** In [Google Cloud Console](https://console.cloud.google.com/) enable YouTube Data API v3 and create an API key → `YOUTUBE_API_KEY`; your channel id (`UC…`) → `YOUTUBE_CHANNEL_ID`.
3. **LinkedIn (optional).** Your profile URL → `LINKEDIN_PROFILE_URL`. Then either send the bot `/setcookie <li_at>` with the `li_at` cookie of a logged-in browser (DevTools → Application → Cookies → linkedin.com) — the bot checks it, deletes your message and watches the cookie's age — or enter the number by hand with the «✏️ LinkedIn» button.

4. **Security emails (optional).** Deploy the [mail-worker](mail-worker/README.md) → `SECURITY_MAIL_URL`, `SECURITY_MAIL_TOKEN`, and set up forwarding in your mailbox.

> ⚠️ **About LinkedIn.** There is no official API for a personal profile's follower count, so the bot opens your profile page with your cookie, once a day. LinkedIn's User Agreement prohibits automated access: use it at your own risk, LinkedIn may restrict the account. Leave the cookie out and type the number in by hand if you'd rather not take that risk.

### Docker Compose

```bash
cp .env.example .env    # fill it in
docker-compose up -d
```

### Railway

Create a service from this repository, set the variables from `.env.example`, and **attach a volume at `/app/data`** — without one the database is lost on every deploy.

The container starts as root only to hand the data directory to the unprivileged `appuser`, then drops root for good.

## Commands

| Command | What it does |
|---|---|
| `/start`, `/help` | Menu and help |
| `/stats` | Current summary |
| `/now` | Collect now and show the report |
| `/week` | This week vs last week, with the chart |
| `/security` | Security score, the checklist per account, recent security events |
| `/modules` | Connected platforms; switch monitors on and off |
| `/history [platform] [days]` | History table, up to 90 days |
| `/linkedin <number>` | Enter the LinkedIn number by hand |
| `/settime HH:MM`, `/setday <days>` | Report time (UTC) and day(s): `sat`, `mon,thu`, `mon-fri`, `daily` |
| `/setquiet on\|off` | Quiet mode |
| `/setcookie <li_at>`, `/cookieage` | Set the LinkedIn cookie, check its age |
| `/restore` | Reply it to a backup message (or send a `.db` captioned `/restore`) to merge the history back |

## Updates

The bot keeps itself up to date without touching its own container:

1. **Dependabot** opens one grouped PR per week with every Python update (Saturday), plus monthly PRs for the base image and the Actions.
2. **CI** tests each one: ruff, pytest on 3.12–3.14, `pip-audit`, and a build of the production image that must start as `appuser`.
3. **Minor and patch updates merge themselves** once CI is green (`.github/workflows/dependabot-automerge.yml`); major ones wait for you. Branch protection on `main` requires the three CI checks, otherwise auto-merge would not wait for them.
4. **Railway redeploys** from `main`.
5. **The bot tells you** what the pipeline can't: «🔄 Бот обновился: aiohttp 3.14.3 → 3.14.4» after a deploy; within an hour, if the newest commit failed to deploy and it's stuck on an older build; and on Sundays, known vulnerabilities (OSV) in its packages and Dependabot PRs waiting for a human. Silent when there's nothing to do.

`UPDATE_WATCH=0` turns the notices off. On Railway the commit and the repository come from its own variables; elsewhere set `GITHUB_REPOSITORY` and build with `--build-arg APP_COMMIT=$(git rev-parse HEAD)`.

## What it creates outside the repo

- A Telegram bot (@BotFather) and, if you use it, a YouTube Data API key in a Google Cloud project.
- Optionally a [healthchecks.io](https://healthchecks.io) check (`HEALTHCHECK_URL`) and your own site's ingest endpoint (`SITE_INGEST_URL`).
- Optionally, for security emails: a Cloudflare Worker, a KV namespace, an Email Routing rule with its DNS records, and a forwarding address + filter in your mailbox — listed with teardown steps in [mail-worker/README.md](mail-worker/README.md).

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/ruff check .
.venv/bin/pytest -q
```

The tests never touch the network: Telegram is a fake bot, LinkedIn, YouTube, the site push and the mail worker are local HTTP servers. CI runs ruff, pytest on Python 3.12–3.14, `pip-audit`, a build of the production image and the mail-worker tests (`cd mail-worker && npm ci && npm test`).

A new network is one module in `bot/platforms/` (a `Platform` subclass: how to tell it's configured, how to read the follower count and, optionally, which public profile fields to watch) plus an entry in `PLATFORMS`. Monitors live in `bot/monitors/`.

## License

[MIT](LICENSE). Not affiliated with Telegram, YouTube or LinkedIn. Security reports: see [SECURITY.md](SECURITY.md).

# Social Tracker Bot

> A self-hosted Telegram bot for your social accounts: followers on Telegram, YouTube, Instagram and LinkedIn, the life of your channel, and the accounts' security — hijack signs, security emails, comments that get a group blocked — plus a weekly report on how people and AI assistants find you. It stays quiet while things are fine and speaks up the moment something breaks.

🇷🇺 [По-русски](README.ru.md) · [![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/social-tracker-bot?referralCode=7hTMqE)

A personal tool, shared as is: free and open source (MIT), and I use it every day. It is not a supported service — you set it up yourself; there is a step-by-step guide and a Claude skill that walks you through it in the browser. If enough people need it, I'll build a hosted version with nothing to install.

<p align="center">
  <img src="docs/images/home.png" width="31%" alt="Home: the follower report, the security score, the next report">
  <img src="docs/images/security.png" width="31%" alt="Security: a score per account and what to do first">
  <img src="docs/images/week-chart.png" width="31%" alt="The week compared with the last one, and the 30-day chart">
</p>

## What you get

- **One report instead of four apps.** Followers on Telegram, YouTube, Instagram and LinkedIn for the day, the week and the month, a 30-day chart and a forecast to the next round number — on the days and at the hour you pick.
- **An early warning of a hijack.** A new admin or owner, a stranger's link in the description, a new title or avatar, vanished videos: the bot compares your profiles every half hour and tells you at once, with a sound even at night.
- **Security emails in Telegram.** «New sign-in», «password changed», «key added» from the social networks, GitHub, Microsoft and Yandex, within 5 minutes — forwarded to a separate mailbox the bot reads.
- **Comments that get a group blocked.** Drugs, scams, porn in your channel's discussion group: a card with «delete» and «ban» buttons. It never deletes anything by itself, and it shows what the check costs (your own Claude key).
- **The life of your channel.** Who joined and left and through which invite link, every post and its reactions.
- **A security checklist and a reputation report.** 2FA and password age per account; for site owners, how often people and AI assistants find you.
- **Quiet while all is well.** One message when something breaks, one when it is fixed; only what can't wait rings. Everything is a button; a message carrying a key is deleted at once.

The bot speaks English or Russian and picks the language from your Telegram at the first `/start`. Every feature, the menu and the commands: [docs/FEATURES.en.md](docs/FEATURES.en.md). Why it exists: [docs/WHY.en.md](docs/WHY.en.md).

## Setup

Step by step, in clicks: **[docs/SETUP.en.md](docs/SETUP.en.md)** — a bot at @BotFather, the Railway button (one field, `BOT_TOKEN`), `/start`, the first network. Every connection has a page of its own in [docs/connect/](docs/connect/).

**Railway**: [![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/social-tracker-bot?referralCode=7hTMqE) — the button carries my Railway referral code: Railway shares with me a part of what it bills an account created through it; your price stays the same. Without the code: <https://railway.com/deploy/social-tracker-bot>.

**Your own server**, with Docker, in one command — it asks for the token, writes `.env` and `docker-compose.yml` into `~/social-tracker-bot` (another folder: `SOCIAL_TRACKER_DIR=…`) and starts the bot; run it again to update:

```bash
curl -fsSL https://raw.githubusercontent.com/morgunovtech/social-tracker-bot/main/scripts/install.sh | sh
```

**Or by hand.** Make a folder with two files — `.env` with one line, `BOT_TOKEN=<the token from @BotFather>` (every other variable is in [`.env.example`](.env.example)), and `docker-compose.yml`:

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

## What it costs

The bot is free. Railway: a 30-day trial with $5 of credit and no card, then $5 a month on the Hobby plan (a regular, not prepaid, card). Your own server: free. The comment check: about $0.01 per comment on your own Claude key. Details: [docs/SETUP.en.md](docs/SETUP.en.md#what-it-costs).

## Privacy

- Everything stays on your server: the history, the channel's events, the security log — in SQLite on your volume. No analytics.
- The bot reads only public data of your own accounts, through official APIs where they exist; it never asks for a password.
- Keys and tokens sent in the chat are deleted from it at once, never shown or logged, and left out of the weekly backup the bot sends you.
- Comments go to the Claude API without the author's name or id, and only if you connect the check.
- What exactly goes where, request by request: [the full table](docs/FEATURES.en.md#privacy). Security notes: [SECURITY.md](SECURITY.md).

## Documents

| | |
|---|---|
| [docs/WHY.en.md](docs/WHY.en.md) | What it is for, what it doesn't do |
| [docs/SETUP.en.md](docs/SETUP.en.md) | Setup in clicks, costs, what to do when something goes wrong |
| [docs/connect/](docs/connect/) | One page per connection: Telegram, YouTube, Instagram, LinkedIn, watchdog, security emails, comments, reputation |
| [docs/FEATURES.en.md](docs/FEATURES.en.md) | Every feature, the menu, the commands, the report, the schedule, when it writes, the icons, updates, development |
| [mail-worker/README.md](mail-worker/README.md) | The Cloudflare mail worker — the advanced way to security emails |
| [SECURITY.md](SECURITY.md) · [CONTRIBUTING.md](CONTRIBUTING.md) · [CHANGELOG.md](CHANGELOG.md) | Security, contributing, what changed |

## What it creates outside the repo

- A Telegram bot (@BotFather) and, if you use it, a YouTube Data API key in a Google Cloud project.
- On Railway: a project with one service built from this repository and a volume at `/app/data` — the template (`social-tracker-bot`) creates them; delete the project to tear down.
- A public package on GitHub, `ghcr.io/morgunovtech/social-tracker-bot` — the image CI publishes on every green `main`; delete it under the repository's Packages.
- For Instagram: a Meta app with the Instagram API use case, a business portfolio it belongs to, a «Facebook Login for Business» configuration and the Instagram Tester role on your account. Teardown: remove the app on [developers.facebook.com](https://developers.facebook.com/apps/) (Settings → Basic → Remove app), the portfolio in Meta Business Suite → Business settings → Business info, and the app under Instagram → Settings → Website permissions.
- Optionally a [healthchecks.io](https://healthchecks.io) check or a TofsDevOps heartbeat task (set in ⏱ Watchdog or `HEALTHCHECK_URL`; delete it there to tear down) and your own site's ingest endpoint (`SITE_INGEST_URL`).
- On GitHub, for this repository itself: the SonarQube Cloud GitHub App installed on the repo and its project on [sonarcloud.io](https://sonarcloud.io) (automatic analysis of every push and pull request, no config in the repo) — teardown: delete the project on sonarcloud.io and remove the repo from the app (Settings → GitHub Apps); and the «Sponsor» button, `.github/FUNDING.yml`, which points at the owner's GitHub Sponsors listing — delete the file to remove the button.
- Optionally a GitHub personal access token (`GITHUB_TOKEN`), only to lift the anonymous rate limit of the update watch; revoke it under Settings → Developer settings.
- Optionally, for security emails: a separate mailbox with an app password (delete the password in the account's settings and the forwarding filter in your main mailbox to tear down), or a Cloudflare Worker, a KV namespace, an Email Routing rule with its DNS records, and a forwarding address + filter in your mailbox — listed with teardown steps in [mail-worker/README.md](mail-worker/README.md).
- Optionally, for the reputation report: a Google Cloud project with a service account and its JSON key, added as a user of your Search Console properties (remove the user and delete the key to tear down); a Yandex OAuth app at oauth.yandex.ru and its token (delete the app); a Cloudflare API token with Zone Read and Analytics Read (delete it under My Profile → API Tokens).
- Optionally, for the comments: an API key in an Anthropic Console organization (sent in the chat or `ANTHROPIC_API_KEY`), billed per comment checked; revoke it in the Console to tear down.
- For `scripts/clean_deleted.py`: an API id and hash of an application at [my.telegram.org](https://my.telegram.org) (API development tools) and a local session file on your laptop — `~/.social-tracker-clean-bot.session`, or with `--session user` `~/.social-tracker-clean-user.session`, a signed-in session of your own account. Teardown: delete the files and end that session under Telegram → Settings → Devices; the application stays at my.telegram.org.

## Development

`ruff check .`, `pytest -q` (offline: a fake Telegram, local HTTP servers for every API), `pip-audit -r requirements.txt --strict` — how to set up the venv and where things live: [docs/FEATURES.en.md](docs/FEATURES.en.md#development) and [CONTRIBUTING.md](CONTRIBUTING.md).

## Built with

Designed and built by [Semyon Morgunov](https://s.morgunov.tech) with Claude Code as pair programmer.

## License

[MIT](LICENSE). Not affiliated with Telegram, YouTube, Meta or LinkedIn. Security reports: see [SECURITY.md](SECURITY.md).

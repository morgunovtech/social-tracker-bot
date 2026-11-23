# CLAUDE.md

General rules for every project (branches and PRs, worktrees, no twins, repos in `~`, secrets) live in `~/CLAUDE.md`; the rules shared by the owner's Telegram bots are in `~/BOT_PRINCIPLES.md` (short form: [CONTRIBUTING.md](CONTRIBUTING.md), «Principles»). This file holds only what is specific to this project.

## Commands

- Run: `cp .env.example .env` (fill in `BOT_TOKEN` and `ADMIN_CHAT_ID`), then `docker compose up -d`, or `python -m bot.main` in a venv with `requirements.txt` installed.
- Test / lint (the same as CI): `ruff check .`, `pytest -q` (offline: a fake Telegram, local HTTP servers for every API), `pip-audit -r requirements.txt --strict`; the mail-worker: `cd mail-worker && npm test`.

## Deploy

Railway redeploys from `main` on every push (project «Social Tacker Bot», service `social-tracker-bot`, volume at `/app/data`); the Railway template `cL4hpn` is the one-click path for others. The mail-worker is a Cloudflare Email Worker deployed by hand (`npx wrangler deploy` in `mail-worker/`). Verify a deploy by the «🔄 Бот обновился» message or the build line in ⚙️ Settings.

## Conventions

- User-facing text is Russian in the code and the lookup key; English lives in `bot/locales/en/`. Wrap new strings in `t()` and add the English entry — `tests/test_i18n.py` renders every screen in English and fails on the first Cyrillic letter.
- Every menu screen is a function in `bot/ui.py` (text and buttons, no Telegram calls); `bot/handlers.py` routes to them. A new network is one module in `bot/platforms/`; a new alert goes through a monitor in `bot/monitors/` that the user can switch off in `/modules`.
- Every proactive message goes through `bot/notifier.py` (priorities, quiet hours, `/mute`, the digest); nothing else reasons about silence.
- Alerts are «silent when healthy»: one message when something breaks, one when it recovers, nothing in between.
- Keep README.md and README.ru.md in step with the code in the same PR.

## Outside the repo

Keep the «What it creates outside the repo» table in README.md current whenever the project gains a bot, key, server, DNS record or hosted project.

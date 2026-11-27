# CLAUDE.md

General rules for every project (branches and PRs, worktrees, no twins, repos in `~`, secrets) live in `~/CLAUDE.md`; the rules shared by the owner's Telegram bots are in `~/BOT_PRINCIPLES.md` (short form: [CONTRIBUTING.md](CONTRIBUTING.md), «Principles»). This file holds only what is specific to this project.

## Commands

- Run: `cp .env.example .env` (fill in `BOT_TOKEN`; `ADMIN_CHAT_ID` is optional, the first `/start` is the owner), then `docker compose up -d`, or `python -m bot.main` in a venv with `requirements.txt` installed (the dev tools: `pip install --require-hashes --no-deps -r requirements-dev.txt` first, then the same for `requirements.txt` — both are hashed locks compiled from their `.in` files, see CONTRIBUTING.md, «Dependencies»).
- Test / lint (the same as CI): `ruff check .`, `pytest -q` (offline: a fake Telegram, local HTTP servers for every API), `pip check`, `pip-audit -r requirements.txt --strict` and `pip-audit -r requirements-dev.txt --strict`; the mail-worker: `cd mail-worker && npm ci --ignore-scripts && npm test && npm audit --omit=dev`. CI also builds and runs the image (and builds arm64 on a PR).

## Deploy

Railway redeploys from `main` on every push (project «Social Tacker Bot», service `social-tracker-bot`, volume at `/app/data`); the Railway template `social-tracker-bot` is the one-click path for others. The mail-worker is a Cloudflare Email Worker deployed by hand, a merge never deploys it: the first time by `mail-worker/README.md`, «Setup»; an update with `sh mail-worker/update.sh` (a dry run) and then `--deploy`. Never run a plain `npx wrangler deploy` from a clean checkout: `wrangler.toml` is a template (placeholder KV id, empty `ALLOWED_SENDERS`), the real values live only on Cloudflare, and an empty `ALLOWED_SENDERS` makes the worker reject every mail. Verify a deploy by the «🔄 Бот обновился» message or the build line in ⚙️ Settings.

## Conventions

- User-facing text is Russian in the code and the lookup key; English lives in `bot/locales/en/`. Wrap new strings in `t()` and add the English entry — `tests/test_i18n.py` renders every screen in English and fails on the first Cyrillic letter.
- Text kept in the DB and shown later (the security log) is stored before translation: `humanize.phrase()` → `humanize.dump()`, drawn with `humanize.render()` — never as finished text, or a chat that changes `BOT_LANG` reads it in the old language. `tests/test_i18n.py` fills the log while Russian and draws it in English.
- Every menu screen is a function in `bot/ui.py` (text and buttons, no Telegram calls); `bot/handlers.py` routes to them; the callback ids live in `bot/callbacks.py`, which also builds the action rows under alerts (`notifier.send(actions=…, monitor=…)`), so a monitor can point at a screen without importing `ui`. A test walks every button from the home screen: a new button must answer once and lead back, or be a text-input entry listed in `CONVERSATION_ENTRIES`. A new network is one module in `bot/platforms/`; a new alert goes through a monitor in `bot/monitors/` that the user can switch off in `/modules`.
- Every proactive message goes through `bot/notifier.py` (priorities, quiet hours, `/mute`, the digest); nothing else reasons about silence.
- The comment monitor (`bot/monitors/comments.py`, the Claude call in `bot/classifier.py`) only reports: a card with delete / ban / «all fine» buttons, never an action of its own. The owner's taps are the labels (`comment_reviews.label`) that `/comments` turns into the accuracy table; any automatic action must be calibrated on that table first. The classifier never receives the author's id, name or @username. `handlers.on_group_update` (group −2, a handler group of its own: python-telegram-bot runs one handler per group) stops every non-private update, so the owner-only handlers never answer in a group; a channel update goes to the channel monitor from there.
- The channel monitor (`bot/monitors/channel.py`) records what Telegram sends an admin bot — joins and leaves with the invite link, posts, reaction counts — for the 📣 Канал screen and one report line; it alerts nothing, and switched off it records nothing (a join names a person). `chat_member` and `message_reaction_count` arrive only because `handlers.ALLOWED_UPDATES` asks for them: add a new update type there. Views, forwards and citations are not in the Bot API — don't promise them.
- `scripts/clean_deleted.py` (Telethon, not in the bot's requirements) removes deleted accounts from the channel's subscribers; it runs from the owner's laptop, dry run by default. The Bot API cannot list members, so this never moves into the bot.
- Alerts are «silent when healthy»: one message when something breaks, one when it recovers, nothing in between.
- Keep README.md and README.ru.md in step with the code in the same PR.

## Outside the repo

Keep the «What it creates outside the repo» section in README.md current whenever the project gains a bot, key, server, DNS record or hosted project.

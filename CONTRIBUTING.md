# Contributing

Thanks for looking. This is a small self-hosted bot; issues and pull requests are welcome.

## Before you open an issue

- **A bug**: say what you did, what the bot answered (or didn't), and the relevant log lines (`docker-compose logs -f` or the Railway log). Never paste tokens, cookies or your `.env`.
- **A network you'd like**: the bot reads only public data of your own account through an official API where one exists, and never asks for a password. A proposal that needs a cookie or a password of another person is out of scope.
- **A security problem**: don't open an issue, see [SECURITY.md](SECURITY.md).

## Working on the code

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/ruff check .
.venv/bin/pytest -q
```

Direct dependencies are pinned in `requirements.in`; `requirements.txt` is the lock compiled from it with hashes, and the image installs exactly that (`--require-hashes --no-deps`). Changed a pin? Recompile the lock with `uv pip compile requirements.in --universal --python-version 3.12 --generate-hashes --no-header -o requirements.txt` (Dependabot does it in its own PRs).

The tests never touch the network: Telegram is a fake bot, every API is a local HTTP server. CI runs the same on Python 3.12–3.14, plus `pip-audit`, a build of the production image and the mail-worker tests.

- A new network is one module in `bot/platforms/` (a `Platform` subclass) plus an entry in `PLATFORMS`.
- Monitors live in `bot/monitors/`; every alert goes through a monitor the user can switch off in `/modules`.
- Every menu screen is a function in `bot/ui.py` (text and buttons, no Telegram calls); `bot/handlers.py` routes to them.
- User-facing text is Russian in the code and translated in `bot/locales/`: wrap new strings in `t()` and add the English entry (see `bot/i18n.py`).
- Alerts are «silent when healthy»: one message when something breaks, one when it recovers, no repeats in between.

## Principles

The bot follows the same rules as the owner's other Telegram bots ([TofsDevOps](https://github.com/morgunovtech/Tofs_DevOps_bot)). The short version, so a change fits in:

- **Silent when healthy.** An alert only when a state changes, once until it recovers; the recovery is one message with how long it was down. Nothing repeats while nothing changed.
- **Two problem levels.** 🔴 act now — rings, passes mute and quiet hours; 🟠 act later — silent, waits. ⚠️ means «could not check», not a problem. The icon says how urgent, the text says what.
- **One alert shape.** Headline (icon · what · what happened) → what it means for the person → what it usually is → what to do (steps or buttons) → the technical line last. Numbers, not adjectives: «0.12 s», not «fast».
- **Three buttons under the input field** — Home · What I can do · Icons — and no ☰ command list; commands keep working as shortcuts. The menu is the dashboard; screens are edited in place.
- **Chat beats `.env`.** Only the bot token is required; the owner is the first `/start`; everything else is set from the chat.
- **Self-service.** Sunday backup without secrets, restore by sending the file back, «🔄 Бот обновился» after a deploy, a watchdog ping only while the bot actually does its job.
- **Engineering.** Branch + PR, CI matrix with `pip-audit` and a run of the built image, grouped Dependabot with auto-merge of minor/patch, root dropped in `entrypoint.sh`, secrets never in logs, tests offline, README in English and Russian.

The source of truth is the owner's `BOT_PRINCIPLES.md`, kept with the playbook outside the repositories; it ends with the list of what this repository still has to change to match. A principle changes there first, then here.

Open the pull request against `main`; CI must be green. Keep the README (both languages) in step with what you change.

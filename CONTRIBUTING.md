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

Open the pull request against `main`; CI must be green. Keep the README (both languages) in step with what you change.

# AGENTS.md

Rules for coding agents working in this repository (Codex reads this file; Claude reads CLAUDE.md and `~/CLAUDE.md`, which say the same).

- Every change goes through a branch and a PR. Don't open several PRs for alternative attempts at the same task; close what will not be merged.
- No twins: when rewriting or porting code, delete the old version in the same PR.
- Never commit secrets (`.env`, credential files, `.wrangler/`). A secret that reached git history is revoked first; rewriting history comes second.
- User-facing text is Russian in the code with an English entry in `bot/locales/en/`; `pytest -q` and `ruff check .` must pass offline.
- When the project gains a bot, API key, server, DNS record or hosted project, add it to the «What it creates outside the repo» section in README.md.

# Security

Please report vulnerabilities privately: on GitHub open **Security → Report a vulnerability** in this repository. Don't open a public issue for them.

## What the bot holds and how it treats it

- **Bot token, API keys, the mail-worker token** live only in environment variables. Every log line passes a redacting formatter (`bot/redact.py`): the bot token, keys in a URL query, the `li_at` cookie, a password in a URL and every secret value the bot was started with are masked in the message and the traceback alike. The httpx logger is kept at WARNING on top: at INFO it prints every Bot API URL.
- **Instagram access token** (`/igtoken`) and **LinkedIn `li_at` cookie** (`/setcookie`) are stored in the SQLite DB on your volume. The message carrying either is deleted from the chat right away, the weekly backup the bot sends to the chat is made without them, and `/restore` never overwrites a live one with a stale copy. The Instagram token is a system-user token of your own Meta app: it does not expire, so revoke it there (remove the app's Instagram Tester role or the app itself) if it leaks.
- **Follower history, profile baselines, checklist answers, security events and alerts held back by quiet hours or `/mute`** are in the same DB; the held alerts are live state and are left out of the backup. Nothing leaves it except the counts you choose to push to your own site (`SITE_INGEST_URL`) and the status lines to your own TofsDevOps (`HEALTHCHECK_URL`).
- **Least privilege by design.** The bot reads only public data of your own accounts through official APIs where they exist (Telegram, YouTube, Instagram); it never asks for a password, and the hygiene checklist is your own marks. LinkedIn has no API for a personal profile's followers, so its number is scraped with your cookie or typed in by hand.
- **Security emails** reach the bot only through your own mail-worker, which accepts mail from the senders you list (`ALLOWED_SENDERS`) and drops the rest. Links quoted from a mail or a changed profile description are defanged (`hxxps://evil[.]example`) and link previews are off, so an alert never carries a clickable scam link.
- **Access**: every command and button checks that the user is `ADMIN_CHAT_ID`; everyone else is refused.
- **Supply chain**: dependencies are pinned, `pip-audit` and `npm audit` run in CI, Dependabot keeps them current, and the bot reports known vulnerabilities (OSV) in its packages on Sundays. The container drops root after handing the data directory to `appuser`.

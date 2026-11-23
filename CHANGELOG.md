# Changelog

The bot keeps itself updated (Dependabot, auto-merge, Railway); this file lists what changed for the person running it. Dates are merge dates.

## 1.2.1 — unreleased

- `scripts/clean_deleted.py`: remove deleted accounts from the channel's subscribers over MTProto (Telethon), by hand from a laptop, dry run by default; `--session bot` or `--session user`.

## 1.2.0 — 2026-11-23

Prohibited content in the channel's comments, reported with one-tap actions; the bot no longer talks to strangers in groups.

**Comments of the channel** — a new monitor, off without `ANTHROPIC_API_KEY`
- Made an admin of the channel's discussion group, the bot looks at every comment with a Claude model (`claude-opus-5-5`, `COMMENTS_MODEL` to change) and sends a card for anything the group can be blocked for — drug sales, pornography, sexualization of minors, extremism, fraud — and, quietly, for spam. The card: the text (links defanged), the author, first message or not, why it was flagged, a link to the message, and three buttons: 🗑 delete, 🔨 delete and ban (with ↩️ unban after), ✅ all fine.
- Report-only by design: nothing is deleted or banned without a tap. The taps are labels; `/comments` (also a button on 🛡 Security) shows how many comments were checked and, per category, flagged · confirmed · false, with the accuracy of the verdicts — the table any automatic action would be calibrated on.
- A dangerous category at ≥ 70 % rings; lower confidence, spam and a model refusal are quiet cards. The group's admins and the owner are never reviewed; a picture (or a video / sticker thumbnail) is judged together with the caption. The classifier gets the text, the picture, the group's title and two facts about the author — never an id, a name or a @username.
- Three failed checks in a row → one 🟠 notice; the first success after → ✅. A failure is never counted as «fine».
- Setup: `ANTHROPIC_API_KEY`, the bot as a group admin with the rights to delete messages and ban members; `COMMENTS_CHAT_ID` names the group when it is not the channel's linked one. Switch in `/modules`.

**Fixed**
- Added to a group, the bot used to answer «⛔ Доступ запрещён» to every message by a non-owner (every comment, once it was in the discussion group). Nothing from a group or a channel reaches the owner-only handlers any more.

**Under the hood**
- `anthropic` joins the hashed lock (with `httpx2`, `pydantic`, `jiter`, `opentelemetry-api`); `comment_reviews` table in the DB.

## 1.1.0 — 2026-11-23

Quiet hours and `/mute`, one required variable, and the supply chain hardened: hashed lock, pinned image and Actions, a public image on ghcr.io.

**When it writes** — the TofsDevOps notification model (#34)
- One door for every message to the owner (`bot/notifier.py`) with three priorities: 🚨 and 🔴 ring through everything (hijack signs, a new sign-in, a changed password, a vanished profile); 🟠 ⚠️ 🎯 messages are silent and wait during quiet hours or a mute; the weekly report, the monthly digest, the backup and the Sunday notices are silent and wait only during a mute.
- Quiet hours (off by default) with presets in ⚙️ Settings → 🔔 When to write, in your time zone; `/mute <time>` and `/unmute`, also as 🔕 buttons; «🔕 Тишина до …» on the home screen while a mute lasts.
- What was held arrives as one numbered digest with the time of each item when the silence ends.
- A rejected token or cookie, a failure streak, a bot influx and a mail worker that stopped answering are now 🟠 (they wait for the digest), so the icon and the way a message arrives agree.

**Setup** — one required variable (#40)
- The first `/start` after the deploy makes its sender the owner; `ADMIN_CHAT_ID` is optional and, when set, pins the owner or takes the bot over. Nothing is sent before an owner exists. The Railway template asks for `BOT_TOKEN` only.

**Running it**
- A public image on every green `main`: `ghcr.io/morgunovtech/social-tracker-bot` (`:latest`, `:sha-…`, amd64 and arm64); `docker-compose.yml` pulls it, building from source stays one line away (#36).
- Logs pass a redacting formatter: the bot token, keys in a URL, the LinkedIn cookie and every secret the bot was started with are masked, tracebacks included (#37).

**Under the hood** (#36)
- `requirements.txt` is a hashed lock compiled from `requirements.in`; the image and CI install exactly it. Base image pinned by digest, every Action by commit. Dependabot waits 7 days (30 for majors) before proposing a version; the auto-merge waits for the tests itself.

**Docs**
- README «Privacy»: every host the bot talks to and what stays on your volume; the English README quotes the English UI; `CONTRIBUTING.md` «Principles», `CLAUDE.md`, `AGENTS.md` (#33, #35).

## 1.0.0 — 2026-11-23

The first release worth a number: four networks, account protection, English, one-click deploy.

**Networks**
- Telegram channel, YouTube channel, LinkedIn profile (cookie or by hand) and, new, **Instagram** through the official Instagram API with Unified login: a non-expiring token of your own Meta app, pasted once with `/igtoken` (#27, #28).

**Account protection** (#9, #12, #16)
- Profile integrity every 30 minutes: name, @username, description and its links, avatar, Telegram admins and owner, a mass drop in videos or posts, a profile that stops being readable.
- Security emails through a Cloudflare Email Worker: new sign-ins, password and 2FA changes, login codes, within 5 minutes, with recovery links and defanged URLs.
- Hygiene checklist per account with a score out of 10 in every report and a reminder at most once a month.
- Every monitor can be switched off in `/modules`.

**Followers**
- Daily collection, a report on the days and at the time you pick in your own time zone (#18), 14-day sparklines, a 30-day chart, milestones, a forecast to the next one, the week's leader, a monthly digest.
- Alerts that need action: a drop, a bot influx, collection failing two days in a row, a revoked Instagram token or an expired LinkedIn cookie.
- A status line per network on the TofsDevOps main screen when the watchdog is a TofsDevOps heartbeat (#21–#24).

**Running it**
- `BOT_LANG=en` or `ru` for every screen, report and alert (#31).
- Deploy on Railway in one click from the template, or Docker Compose; the DB lives on a volume, the weekly backup lands in your chat without the secrets, `/restore` merges it back (#4).
- The bot updates itself and tells you about a deploy, a stuck deploy and known vulnerabilities in its packages (#6).
- Both READMEs and SECURITY.md describe exactly what the code does (#29).

## Before 1.0

- 2026-11-03: open-sourced under MIT with a test suite, CI (ruff, pytest, pip-audit, image build) and Dependabot (#3, #5, #6); the audit fixed a cookie leak into backups, lost `/now` alerts and missed runs (#2).
- 2026-07-29: proactive monitoring — instant alerts, watchdog, retries, forecasts, backups; the bot-influx detector; PTB 22.8 and Python 3.14.
- 2026-05-02: weekly schedule, LinkedIn cookie managed from the chat, the persistent menu button.
- 2026-03-30: the first version — Telegram, YouTube and LinkedIn counts with a weekly report.

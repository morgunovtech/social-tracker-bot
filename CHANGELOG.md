# Changelog

The bot keeps itself updated (Dependabot, auto-merge, Railway); this file lists what changed for the person running it. Dates are merge dates.

## Unreleased

**When it writes** — the TofsDevOps notification model
- One door for every message to the owner (`bot/notifier.py`) with three priorities: 🚨 and 🔴 ring through everything (hijack signs, a new sign-in, a changed password, a vanished profile); 🟠 ⚠️ 🎯 messages are silent and wait during quiet hours or a mute; the weekly report, the monthly digest, the backup and the Sunday notices are silent and wait only during a mute.
- Quiet hours (off by default) with presets in ⚙️ Settings → 🔔 When to write, in your time zone; `/mute <time>` and `/unmute`, also as 🔕 buttons; «🔕 Тишина до …» on the home screen while a mute lasts.
- What was held arrives as one numbered digest with the time of each item when the silence ends.
- A rejected token or cookie, a failure streak, a bot influx and a mail worker that stopped answering are now 🟠 (they wait for the digest), so the icon and the way a message arrives agree.

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

# Changelog

The bot keeps itself updated (Dependabot, auto-merge, Railway); this file lists what changed for the person running it. Dates are merge dates.

## 1.4.0 — 2026-11-23

A code review, fixed end to end: what could give a wrong answer, what could cost money or leave a secret in the chat, and the small things. Then a walk through the owner's journeys: everything a command did is a button away, and the alerts carry the next step.

**Buttons**
- Three buttons at the bottom of the chat: 🏠 Меню, 🔄 Обновить, 🔕 Тихо 8 ч — one tap from anywhere; «🔕 Помолчать» used to be three taps deep from a home screen that twenty alerts had scrolled away.
- Under every alert and report, a row to where to look into it (🛡 Безопасность, 📈 Динамика, 📣 Канал, 💬 Комментарии); «🔕 Тихо 8 ч» under anything that may wait; «⚙️ Не присылать такие» under a 🟠 one switches its monitor off. The buttons open the screen as a new message, so the alert stays; a digest gets one row for all its items. The error notice carries «🏠 Главная».
- 🔌 Подключения, on the home screen and in ⚙️ Настройки: every network with its state — not in .env, collected, waiting for a token, a cookie or the first number — and the Instagram and LinkedIn screens under it, shown whether or not they are set up yet (they used to appear in the settings only once the platform was in .env). `/connections` does the same.
- «🔑 Прислать cookie» and «🔑 Прислать токен» ask for the secret as the next message, the way the LinkedIn number is asked for; the commands stay. «✏️ Другой пояс…» asks for a zone by name; Ташкент joined the presets; a row of minutes (:00 :15 :30 :45) under the hour grid.
- A `.db` file sent without a caption is offered for a restore with one button (it used to be ignored in silence); «📦 Бэкап сейчас» in ⚙️ Настройки, not only on Sunday.
- The 📣 Канал and 💬 Комментарии screens carry their monitor's switch instead of «выключено в /modules».
- The home screen shows when the data was last collected, «🔔 Снять тишину» while a mute lasts, and on a fresh install what is left to set up — the time zone, the token, the cookie — with a button for each.
- «Тихий режим» is «Коротко без изменений»: three different things were called «тихо» (the short report, the quiet hours, the mute).
- The `/` menu lists `/mute`, `/channel` and `/connections` too.

**Comments of the channel**
- At most three comments are classified at once, and at most `COMMENTS_DAILY_LIMIT` a day (300 by default, 0 = no limit): a spam wave of two hundred messages used to be two hundred parallel API calls with pictures. When the day's limit is reached the bot says so once and leaves the rest unchecked — in as many words.
- A comment the model called fine keeps only the author's id and the verdict; the name is stored for a card alone, as SECURITY.md said all along.
- `tests/test_classifier_live.py`: one real classification, opt-in (`LIVE_ANTHROPIC_API_KEY`), for the release checklist — a request shape the API refuses passes every fake.

**Retention**
- Once a day the bot drops what no screen reads any more: joins and leaves after 90 days, fine comments after 30, flagged ones with their card after 180. Both named a person and stayed for ever, and the Sunday backup carried all of it to the chat.

**LinkedIn**
- The first number read by cookie is confirmed by hand, not stored: the profile page carries other profiles' counters too, and without a stored value the bot picked the largest and then defended it against every later value. The report, a one-time 🟠 alert and `/setcookie` all say «/linkedin N» to confirm; the manual-entry button stays on the home screen until a number exists.

**Fixed**
- Comments: the classifier's `max_tokens` was 512, sized for the JSON alone; the model's thinking counts toward it and cannot be switched off, so a reply could end before any text and the check failed as if the API were down. Now 4096, and a cut-off answer is reported as such.
- Every command and button waited while a collection ran: python-telegram-bot handled one update after another by default, and `/now` takes as long as four networks with their timeouts. Updates are handled concurrently now; the collection itself has one lock, shared with the scheduler, so the daily run and a manual one never overlap.
- «🔄 Бот обновился» and the Sunday OSV check watched a hand-kept list of seven packages — `anthropic` and everything it brought were not on it. Every installed package is watched.
- A `/setcookie` or `/igtoken` that waited out a deploy longer than ten minutes was dropped with the secret left in the chat; now the message is deleted and the owner asked to send it again.
- A collection that raised as a whole (the DB, the HTTP session) was neither retried nor counted; now it is retried an hour later like a failed network, and alerted on the second day in a row.
- `REPORT_MINUTE=` or `LINKEDIN_STALE_DAYS=` left empty crashed on `int("")`; `REPORT_HOUR=25` crashed later in the scheduler. Every whole-number variable now has a range and a plain error with its name.
- YouTube requests had no timeout of their own (aiohttp's is five minutes); 20 seconds now, like the other networks.
- A changed `INSTAGRAM_USERNAME` kept collecting the old account: the stored id is now tied to the username it was resolved for.
- Display names and invite-link names in cards, alerts and the 📣 Channel screen are defanged: Telegram links a bare domain in plain text too.
- One missed collection erased the whole weekly delta, the leader and the forecast from the report; the week and month baselines now take the newest row up to 3 and 7 days earlier.
- The date in the report's title, the 1st of the month for the digest and the Sunday of the backup follow the report's time zone (an early-morning report in Tashkent was dated yesterday; the «Sunday» backup came on Monday).
- The chart is drawn without pyplot, whose global state is not thread-safe when the scheduled report and the 🖼 button render at the same time; a digest can no longer go out twice when `/unmute` meets the minute job; the 🛡 Security screen survives an event without a text.
- `scripts/clean_deleted.py`: no blocking sleep inside the event loop, a second FloodWait right after the first stops the run, the session file is named as the README names it.

**Deleted accounts among the subscribers**
- `scripts/clean_deleted.py`: remove deleted accounts from the channel's subscribers over MTProto (Telethon), by hand from a laptop, dry run by default; `--session bot` or `--session user`. Not part of the bot: the Bot API cannot list members.

**Fixed earlier in this version**
- Comments were never classified: the output schema asked the Claude API for an integer with `minimum`/`maximum`, which the API refuses (HTTP 400), so every check failed and, after three, the owner got the «проверка не работает» notice. The range is clamped in the bot instead.

## 1.3.0 — 2026-11-23

Life of the channel without TGStat in the admins, and the group router that #43 left unreachable.

**Life of the channel** — a new monitor, on by itself for a Telegram channel the bot is an admin of
- What Telegram sends an admin bot is kept on your volume: every join and leave (who, and the invite link it came through — the link's name, a join request, a chat folder, or directly), every post, and the reactions a post gathers (a snapshot per post, custom emoji summed, paid reactions as ⭐).
- `/channel`, also the 📣 Channel button on the home screen: joins · leaves · posts · reactions for 24 hours, 7 and 30 days; where the joins came from; the three most reacted posts of the month with links; the latest five events with names. The report gets one line: «📣 Channel, last 7 days: +14 joins · −3 leaves · 4 posts · 37 reactions».
- Nothing new is alerted (a drop in followers is still the followers monitor's job). Switched off in `/modules`, nothing is recorded — a join names a person. The Sunday backup carries the history and `/restore` merges it back.
- Views, forwards and the citation index are not in the Bot API; the screen says so and points at Telegram's own statistics.
- The bot now asks Telegram for `chat_member` and `message_reaction_count` updates explicitly: they are not delivered unless requested.

**Fixed**
- The handler that keeps group and channel traffic away from the owner-only handlers (#43) shared a handler group with the stale-message filter; python-telegram-bot runs one handler per group, so it never ran: comments were not reviewed and every stranger's message in the group got «⛔ Access denied». Each early handler now has a group of its own, and a test checks what runs first.

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

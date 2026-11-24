# Changelog

The bot keeps itself updated (Dependabot, auto-merge, Railway); this file lists what changed for the person running it. Dates are merge dates.

## Unreleased

**An update that changed how the bot behaves says so once** (the owner's `BOT_PRINCIPLES.md`, §6)
- At every start the bot notes what it actually does — the report's days, time and zone, quiet hours, «Коротко без изменений», which checks are on, which security mails ring and the thresholds of its alerts — next to what the owner set for it: the chat settings and the `.env` values they are computed from (`bot/behavior.py`, kept in the setting `behavior_snapshot`; never a secret — a check's «configured» is a yes or no).
- At the next start a value that moved while everything the owner set stayed the same was moved by the new version: one «ℹ️ После обновления я работаю иначе…» lists each change as «now — was before», with buttons to the settings it concerns (🌍 Часовой пояс, 🕗 Время отчёта, 🔔 Когда писать, 🧩 Мониторинги, ⚙️ Настройки). A change made in the chat or in `.env` is the owner's and is not told back. A check that is new and on by default is named; a new kind of security mail and a changed level or threshold are told only while their monitor is on. The snapshot is kept only once the message went out, so a send that failed is told at the next start.
- The first case, 1.5.0's: an empty zone used to mean UTC and now follows the chat language, so `REPORT_HOUR_UTC=4` moved from 04:00 UTC to 04:00 Moscow without a word. A bot that ran before and still keeps its schedule in the language's zone — no `TIMEZONE`, no `REPORT_TZ`, nothing picked in the chat — hears it once with this update, with the time it used to be on today's clock and the buttons to pick its zone and time.
- Alerts may open the settings screens now: `open:rtz`, `open:rtime`, `open:when`, `open:mod`, `open:set`.

**What the bot sends out is watched too** (`BOT_PRINCIPLES.md`, §4)
- The counts pushed to the site (`SITE_INGEST_URL`), the status lines sent to TofsDevOps and the daily mark at any other watchdog used to fail into the log only: a changed token would have frozen the counts on the site, and nobody would have known. Every attempt is recorded now (`bot/monitors/outgoing.py`); a day without one that landed is one 🟠 that names where and why — «🟠 s.example.com не принимает цифры подписчиков уже 1 дн.: отвечает ошибкой 401», with what it means, the usual causes, what to do and the last delivery that landed — and the first one that lands after it is one ✅ with how long it did not. Nothing repeats in between.
- TofsDevOps refusing the lines (a format change, HTTP 400) is told too, even though the plain mark still lands by the GET fallback and the watchdog stays content: TofsDevOps's main screen would otherwise show frozen lines. The half-hourly refresh after the profile check counts as a delivery.
- ⚙️ Настройки → 📤 Отправки: when each delivery last landed, or since when it does not and why (only what is configured). The host only, never the path or the query.
- A new monitor in `/modules`, «Отправки наружу», on by default; switched off, it keeps count and says nothing.

**Fixed** (the code review of 2026-11-24)
- A comment edited after it was posted was never looked at again: the bot did not ask Telegram for edits, and one comment was one review for good. A harmless comment edited into a drug shop stayed. The bot now asks for `edited_message`; an edit in the discussion group is classified again, and a flagged one replaces the stored verdict (the owner's earlier action and mark go with the old text) and comes as a card of its own, «✏️ отредактирован после публикации». An edit the model calls fine leaves a flagged card as it was; an edit of a comment already deleted or banned is not sent to the model. Edits count toward `COMMENTS_DAILY_LIMIT`. A database of an older version gets the `edited_at` column at start.
- An edit in the owner's own chat (a typo fixed in an old `/settime`) is ignored: python-telegram-bot hands edits to command handlers too, and they would have run the command again.
- A comment card that Telegram did not take — a flood limit in a spam wave, a network error — was lost: the review was stored first, and Telegram does not send the comment again. Now it waits in the queue and comes with the next minute's flush, whole, with the time above it (`notifier.send(hold_on_error=True)`).
- A restored Sunday backup brought back the date the LinkedIn cookie (and the Instagram token) was set without the cookie itself, which the backup leaves out: the LinkedIn screen then aged a cookie from `.env` by the old one's date. A secret's dates now come back only together with the secret.
- `/history 7` showed eight days: «the last N days» counted today plus N days back. It is N days now, today included, in the tables, the chart and the bot-inflow check.
- An edit Telegram delivered twice (the bot restarted before it confirmed the update) was classified and carded twice. The time of the edit is kept with the review now, and an edit the bot has already looked at is skipped; a later edit is a new look. And an edit of an author's first comment still tells the model and the card «first message in the group»: the stored row of the comment itself no longer counts as an earlier message.

## 1.6.0 — 2026-11-24

The digest after a quiet night or a `/mute` reads like the principles say: one headline per held message, 🔴 and 🟠 first, and «ℹ️ N» for the rest of any of them. And 🛡 Security's recent events read in the chat language, whatever language they were recorded in.

**The digest after the silence: headlines, and the rest a tap away** (the owner's `BOT_PRINCIPLES.md`, §3)
- What waited out quiet hours or a `/mute` used to come back as every held alert in full, one after another in one long message. Now the digest is one line per message — its headline, icon first — 🔴 first, then 🟠, then the rest (a recovery, a fact, a report), each with the time it happened.
- «ℹ️ N» under the digest sends item N whole, below it, with the time above and the buttons it would have had — «⚙️ Не присылать такие» included, which the digest's shared row leaves out; the digest stays as it is. A line with nothing more behind it gets no button. More than eight such items, or a very long night, continue in «🌙 (продолжение)» with the numbers going on.
- The full texts are kept for 7 days after the digest (`HELD_KEEP_DAYS`, as long as the longest `/mute`), then the daily clean-up drops them; a tap after that says so. They never go into the Sunday backup, like the queue itself.
- A card — a message whose buttons act on it, a comment card or a failed deploy with its log — comes whole after the digest instead of splitting it.
- Nothing held is lost, as before: a message leaves the queue only once Telegram took the digest with its line, and the queue and the full texts live in the database, so a restart changes nothing. 🔴 never waits for a digest. A database of an older version gets the new column at start and keeps what it was holding.
- ⚙️ Настройки → 🔔 Когда писать says how the digest reads and how long the full texts are kept.

**Fixed**
- 🛡 Security's «Recent events» showed each row in the language it was recorded in: with `BOT_LANG=en`, a change recorded while the bot was Russian read «🟠 Telegram: доступ бота к списку админов — «нет» → «есть»». The security log now keeps a line before translation — the Russian template and its values as JSON; the bot's own words (a field's name, «есть», «нет», «(пусто)», a mail's kind) are translated when the screen is drawn, someone else's text (a title, a name, a subject) is shown as it was. Rows stored as finished Russian text by 1.5.0 and earlier are recognised by the lines those versions wrote and read the same way, an old 🚨 line as today's 🔴 with «похоже на взлом»; a row that matches none of them is shown as it is.
- The alert about the bot's access to the channel's admin list said «нет» → «есть» in an English chat too: the two words are the bot's own and are translated now.
- `tests/test_i18n.py` draws 🛡 Security with a log filled while the chat was Russian — by today's profile and mail monitors, plus the 1.5.0 row above — and the access alert in English; both failed before the fix.

## 1.5.0 — 2026-11-24

The bot now speaks the same language as the owner's other bot, TofsDevOps: one set of icons, three buttons under the input field, one shape for every alert, a recovery that says how long it lasted, and a watchdog connected from the chat — the open items of the shared bot principles for this bot, closed.

**One icon language** — the same as TofsDevOps's (the owner's `BOT_PRINCIPLES.md`, §1)
- One dictionary, `LEVEL_ICONS` in `bot/monitors/__init__.py`: 🔴 act now (rings), 🟠 act, but not today (silent), and the states that never ring — ✅ ⚠️ ⏳ ℹ️ ⬜ ➖ ❓. «❓ Значки» draws its legend from it and says in words what is 🔴 for this bot; the READMEs have the table.
- 🚨 is gone: a hijack sign is 🔴 with «похоже на взлом» in its headline — «🔴 Telegram: похоже на взлом — новый админ …», «🔴 Google: похоже на взлом — новый вход в аккаунт». What rang still rings, and a dangerous comment card is 🔴 as well.
- The mail worker silent for ~30 minutes is 🔴 and rings: while it is down, a new sign-in or a changed password reaches nobody. It used to be a quiet 🟠.
- ⚠️ means «could not check» and nothing else. A missing Instagram token, a first LinkedIn number to confirm, a cookie about to expire, a number typed in too long ago, data that has not been fresh for days, a checklist answer short of the best are 🟠: an action is needed, just not tonight. The report's ⏰ cookie line is 🟠 too, and an unrecognised mail is ℹ️.

**Three buttons** (§2)
- Under the input field: 🏠 Главная · 📖 Что я умею · ❓ Значки. «📖 Что я умею» (and `/help`) says what the bot does, where things are and lists every command; «❓ Значки» (and `/icons`) is the icon table and what rings. «🔄 Обновить данные» and the new «🔕 Помолчать…» (an hour, four, eight, a day) are on the home screen, one tap away as the 1.4.0 buttons were.
- The ☰ command list is not published any more (`delete_my_commands` at start): every command still works when typed. The first start after the update brings the new keyboard with one silent note; the buttons of the old one (🏠 Меню, 🔄 Обновить, 🔕 Тихо 8 ч) keep doing what they did.
- `/setcookie` and `/igtoken` without a value ask for it as the next message, with «✖️ Отмена», like their buttons; with the value they are shortcuts as before.
- One label per thing on every screen: «🏠 Главная» back home, «✖️ Отмена» out of a step. Text the bot does not understand gets «Не понял. Всё — кнопками под полем ввода…» and the keyboard again; a stale button says so and shows the home screen.

**Watchdog from the chat** (§6)
- 🔌 Подключения → ⏱ Сторож: who tells you when the bot itself stops — its state and the last ping, «🔗 Прислать ссылку», «🔄 Проверить снова», «⏏ Отключить» (asked first). A link is taken only after a live test ping lands, and the answer's body is read: healthchecks.io says «OK (not found)» with HTTP 200 for a deleted check, and the bot says so instead of keeping a dead address. The message with the link is deleted; the address lives in the DB, never on a screen, in a log line or in the Sunday backup.
- The daily ping uses the address from the chat first and `HEALTHCHECK_URL` as the fallback; it reads the body too, and its outcome shows on 🔌 Подключения (✅ last ping, 🟠 the watchdog refuses it, ⚠️ could not reach it).
- After the first collection that read a network, the bot offers the watchdog once, unless one is already set.

**One alert shape** (§3)
- Every alert reads top to bottom the same way, as in TofsDevOps: the headline, what it means and what it usually is, what to do in two or three steps, the technical line last («Тех.: HTTP 500 · 6 опросов подряд»). `bot/humanize.py` holds the words — one dictionary of explanations for the follower drop and the bot influx, the collection failures, the cookie and the token, the profile changes and the hijack signs, the unreadable profile, the security emails, the silent mail worker, the comment check down and its daily limit.
- One message per problem: a drop and an expired cookie of the same morning used to share one message and its buttons; now each has its own, with its own «⚙️ Не присылать такие». A milestone stays one line — it is a fact, not a problem. The profile's changes of one check stay one alert, the hijack signs first; «🛡 Профиль» above them and the fixed advice under them are gone.
- A recovery says how long it lasted, from the first failed check of the series: «✅ Почтовый воркер снова отвечает. Молчал 40 мин (14:03–14:43). Ничего делать не нужно.» — the mail worker, the profile («Не читался …»), a collection streak and the daily run («Не собирались …», «Не выполнялся …», told once, only after one that was alerted; they used to end in silence), the comment check. When the bot itself was not checking in between, it says the duration is a lower bound.
- The ✅ after a 🔴 outage — the profile readable again, the mail worker back — rings like the fall did (§1).

**Someone else's text** (§3)
- Direction overrides, zero-width marks and control characters are stripped from everything quoted — `clean()` runs inside `defang()` and inside every screen value: a display name or a mail subject with U+202E can no longer show `evil.com` as `google.com`. An unknown sender's domain in an alert is defanged too.

**Time zone** (§5)
- With no zone chosen, the schedule follows the chat language: `Europe/Moscow` for `BOT_LANG=ru`, UTC for `en`. `TIMEZONE` sets it in `.env`; `REPORT_TZ` keeps working as its older name. A zone chosen in the chat wins as before, and a schedule already stored keeps its zone; a Russian install that never picked one and has no `REPORT_TZ` now reports at 08:00 Moscow time instead of 08:00 UTC (`TIMEZONE=UTC` keeps the old time). The home screen's «осталось настроить» line names the zone in use.

**Docs**
- The first paragraph of both READMEs is short again: it is the product card on s.morgunov.tech; the details live in «What you get».

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

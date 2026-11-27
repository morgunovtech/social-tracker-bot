# LinkedIn

Guide for people: https://github.com/morgunovtech/social-tracker-bot/blob/main/docs/connect/linkedin.en.md (Russian: linkedin.md).

Default — **the number by hand**, no automation:
1. In the bot: «🔌 Подключения» → «➕ LinkedIn» → the profile link `https://www.linkedin.com/in/<name>/`.
2. The user reads their follower count on their LinkedIn profile; on the bot's home screen «✏️ Ввести число LinkedIn» (EN «✏️ Enter LinkedIn count») → the number.

The cookie path (automatic collection) **only if the user asks for it explicitly**, after you say: LinkedIn's User Agreement prohibits automated access, the account may be restricted, it is at their own risk. Then: in Chrome on linkedin.com → right click → «Inspect» → «Application» → «Cookies» → `https://www.linkedin.com` → `li_at` → Value; in the bot «💼 LinkedIn» → «🔑 Прислать cookie» (EN «🔑 Send the cookie»). Prefer that the user copies the cookie themselves — never read it out in the chat.

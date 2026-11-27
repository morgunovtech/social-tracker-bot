# Step 3 and the first network — /start and a Telegram channel

## /start (claim the bot)

1. Open `https://t.me/<bot username>` → «Open in Web» / open the chat in web.telegram.org.
2. Press «Start» (sends `/start`).
3. Expect «✅ Теперь этот бот твой» (Russian) or «✅ This bot is yours now» (English) and a second message with 🔌 Подключения / 🔌 Connections.
   - «Это личный бот…» / «This is a personal bot…» → someone else pressed /start first. Tell the user: get their id from @userinfobot, add a variable `ADMIN_CHAT_ID` with it under the Railway service's **Variables**, wait for the redeploy, press Start again. Don't do it without asking.
   - No answer within a minute → go back to Railway logs (railway.md, step 5).

## Telegram channel

Needs: a channel where the user is the owner or an admin allowed to add admins.

1. In Telegram Web open the channel → its name at the top → edit (pencil) → «Administrators» / «Администраторы» → «Add Admin» / «Добавить администратора».
2. Search the bot's @username, add it. It needs no special rights — the user may untick them all; confirm with the user before saving.
3. Back in the bot's chat: «🔌 Подключения» → «➕ Telegram» (English: «🔌 Connections» → «➕ Telegram»), then send the channel's @username, a `t.me/…` link, or the `-100…` id of a private channel.
4. Expect a ✅ line saying the channel is connected, with its subscriber count. If the bot says it can't see the channel — the bot isn't an admin yet: repeat 1–2.

Then suggest the time zone: on the home screen «🌍 Выбрать часовой пояс» / «🌍 Choose the time zone», or send a city name after «✏️ Другой пояс…» / «✏️ Another zone…».

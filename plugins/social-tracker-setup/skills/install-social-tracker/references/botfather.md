# Step 1 — a bot at @BotFather (Telegram Web)

Goal: a new Telegram bot and its token.

1. Open https://web.telegram.org/k/ in the browser. If Telegram asks to sign in (QR code or phone), **stop and let the user sign in themselves**; carry on when they say so.
2. Open the chat with @BotFather: search «BotFather», pick the one with the blue check mark, username exactly `@BotFather`. Never a look-alike.
3. Press «Start» if the chat is new, then send `/newbot`.
4. BotFather asks for a name: suggest one from the user's own words («My tracker», «Трекер Семёна»), confirm with them, send it.
5. BotFather asks for a username ending in `bot`. Suggest a free-looking one (`<name>_tracker_bot`); if BotFather answers that it is taken or invalid, propose another and ask before sending.
6. BotFather answers with the token: digits, a colon, ~35 letters (`123456789:AAH…`).
   - **Do not repeat the token in the chat with the user.** Say only «the token is in BotFather's last message».
   - Ask: «Shall I paste the token into Railway for you? It will be visible to me in this session.» Default: the user copies and pastes it themselves.
7. Write down the bot's username (`@…_bot`) — step 3 opens `t.me/<username>`.

Stop and describe what you see if BotFather's answers differ from the above (a limit on new bots, a ban, a different flow).

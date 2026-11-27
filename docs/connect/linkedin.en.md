# 💼 LinkedIn

🇷🇺 [По-русски](linkedin.md) · [All connections](../SETUP.en.md#the-other-connections)

LinkedIn has no official API for a personal profile's follower count. So by default you type the number in — once a week or whenever it suits you — and automatic collection with a cookie is a separate path at your own risk.

## How long it takes and what you need

A minute: the link to your profile and the follower count from its page.

## Steps

1. In the bot: 🔌 Connections → «➕ LinkedIn» → send the link to your profile, like `https://www.linkedin.com/in/name/`.
2. Open your profile on linkedin.com and find the follower count.
3. On the home screen press «✏️ Enter LinkedIn count» and send the number, for example `4520`.

A number typed in by hand is flagged 🟠 in the report as out of date after 7 days — the bot reminds you to update it. A number far from the previous one is asked to be confirmed, so a typo does not become the baseline.

## Automatic collection with a cookie — at your own risk

LinkedIn's User Agreement prohibits automated access: the account may be restricted. If you still want the number collected by itself:

1. On a computer, sign in to linkedin.com in Chrome.
2. Right click on the page → «Inspect» → the «Application» tab → «Cookies» → `https://www.linkedin.com`.
3. Find the `li_at` row and copy its «Value» — a long string.
4. In the bot: 🔌 Connections → «💼 LinkedIn» → «🔑 Send the cookie» and send it. The bot checks the cookie, deletes the message at once and shows the first number it read — check it against your profile page and confirm.

The cookie lives about a year; after 330 days the bot reminds you to renew it, and a rejected cookie gets a message of its own.

## What the bot reads and where it goes

By hand — nothing: you type the number. With the cookie — your profile page on `linkedin.com`, once a day. The cookie is kept in the bot's database and never reaches the backup or the log.

## How to switch it off and remove it

🔌 Connections → «✏️ LinkedIn» → send «-». To make the cookie stop working, sign out of LinkedIn on the computer you took it from.

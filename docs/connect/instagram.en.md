# 📸 Instagram

🇷🇺 [По-русски](instagram.md) · [All connections](../../README.md#setup)

Once a day the bot reads your follower count through the official Instagram API, and every half hour it compares the profile's name, bio, link and post count. This is the longest connection: the token comes from Meta's developer dashboard.

## How long it takes and what you need

About 15 minutes. The Instagram account must be professional — «Creator» or «Business»: in the app, «Settings» → «Account type», free. You need a Facebook account to sign in to developers.facebook.com; Meta asks you to create a business portfolio — free as well, no verification needed for your own account.

## Steps

1. Open [developers.facebook.com](https://developers.facebook.com/) → «My Apps» → «Create App».
2. Choose the **Instagram API** use case and finish the wizard.
3. In the app, open «API setup with Unified login» and create the configuration from the template.
4. Add your Instagram account as an **Instagram Tester**.
5. Accept the invitation in Instagram: «Settings» → «Website permissions» → «Tester invitations».
6. Back in the dashboard, press **Generate token** next to your account. Copy the token.
7. In the bot: 🔌 Connections → «➕ Instagram» → send your @username, then «📸 Instagram» → «🔑 Send the token» and send the token. The bot checks that the token was granted for that very account and deletes the message at once.

Meta's interface changes often: if a button's label differs, look for the closest one in meaning.

## What the bot reads and where it goes

Once a day, the follower count; every half hour, the @username, name, bio, profile link and post count (`graph.facebook.com`, with your token). Only your own account's public data. The token is kept in the bot's database and never reaches the backup or the log. If Meta rejects the token, the bot says so once and reminds you in the report until a new one arrives.

## How to switch it off and remove it

🔌 Connections → «✏️ Instagram» → send «-». Delete the app on developers.facebook.com: the app → «App settings» → «Advanced» → «Delete app».

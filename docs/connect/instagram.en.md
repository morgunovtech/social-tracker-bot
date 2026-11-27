# 📸 Instagram

🇷🇺 [По-русски](instagram.md) · [All connections](../SETUP.en.md#the-other-connections)

Once a day the bot reads your follower count through the official Instagram API, and every half hour it compares the profile's name, bio, link and post count. This is the longest connection: the token comes from Meta's developer dashboard.

## How long it takes and what you need

About 15 minutes. The Instagram account must be professional — «Creator» or «Business»: in the app, «Settings» → «Account type», free. You need a Facebook account to sign in to developers.facebook.com; Meta asks you to create a business portfolio — free as well, no verification needed for your own account.

## Steps

1. Open [developers.facebook.com](https://developers.facebook.com/) → «My Apps» → «Create App» and go through the wizard: a use case about Instagram (the dashboard calls it «Manage messaging & content on Instagram» now), type «Business».
2. In the app: «Use cases» → «Customize» on the Instagram use case → «API setup with Unified login» — this one, not «with Instagram login»: the bot reads through Facebook's Graph API. In step «1. Configure your app», create a configuration.
3. «App roles» → «Roles» → give your Instagram account the **Instagram Tester** role and accept the invitation in Instagram: «Settings» → «Website permissions» → «Tester invitations».
4. Back in «Customize» → step «2. Generate access tokens» → «Add account» if yours isn't there, and press **Generate token** next to it. Copy the token.
5. In the bot: 🔌 Connections → «➕ Instagram» → send your @username, then «📸 Instagram» → «🔑 Send the token» and send the token. The bot checks that the token was granted for that very account and deletes the message at once.

Meta's interface changes often (the labels above were checked against the dashboard on 27 Nov 2026): if a label differs, look for the closest one in meaning.

**How long the token lives.** It depends on how Meta issued it: Instagram-login tokens, by Meta's documentation, live 60 days. When Meta stops taking the token, the bot says «token rejected» once and reminds you in the report — press «Generate token» again and send the new one with «🔑 Send the token». To avoid the refusal, renew the token ahead of time, every month and a half or two.

## What the bot reads and where it goes

Once a day, the follower count; every half hour, the @username, name, bio, profile link and post count (Meta's Graph API, with your token). Only your own account's public data. The token is kept in the bot's database and never reaches the backup or the log. If Meta rejects the token, the bot says so once and reminds you in the report until a new one arrives.

## How to switch it off and remove it

🔌 Connections → «✏️ Instagram» → send «-». Delete the app on developers.facebook.com: the app → «App settings» → «Advanced» → «Delete app».

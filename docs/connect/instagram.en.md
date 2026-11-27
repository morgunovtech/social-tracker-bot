# 📸 Instagram

🇷🇺 [По-русски](instagram.md) · [All connections](../SETUP.en.md#the-other-connections)

Once a day the bot reads your follower count through the official Instagram API, and every half hour it compares the profile's name, bio, link and post count. This is the longest connection: the token comes from Meta's developer dashboard.

## How long it takes and what you need

About 15 minutes. The Instagram account must be professional — «Creator» or «Business»: in the app, «Settings» → «Account type», free. You need a Facebook account to sign in to developers.facebook.com; Meta asks you to create a business portfolio — free as well, no verification needed for your own account.

## Steps

1. Open [developers.facebook.com](https://developers.facebook.com/) → «My Apps» → «Create App» and go through the wizard: a use case about Instagram (the dashboard calls it «Manage messaging & content on Instagram» now), type «Business».
2. In the app: «Use cases» → «Customize» on the Instagram use case → «API setup with Unified login» — this one, not «with Instagram login»: the bot reads through Facebook's Graph API. In step «1. Configure your app», create a configuration. Meta shows the token type and how long it lives there: if you can pick the term, keep the token without one — Meta's default, and it will not need renewing.
3. «App roles» → «Roles» → give your Instagram account the **Instagram Tester** role and accept the invitation in Instagram: «Settings» → «Website permissions» → «Tester invitations».
4. Back in «Customize» → step «2. Generate access tokens» → «Add account» if yours isn't there, and press **Generate token** next to it. Copy the token.
5. In the bot: 🔌 Connections → «➕ Instagram» → send your @username, then «📸 Instagram» → «🔑 Send the token» and send the token. The bot checks that the token was granted for that very account and deletes the message at once.

Meta's interface changes often (the labels above were checked against the dashboard on 27 Nov 2026): if a label differs, look for the closest one in meaning.

**How long the token lives.** «Generate token» under «API setup with Unified login» issues a system token of your business portfolio (Meta's documentation calls it a Business Integration System User access token). The configuration sets its term: by default it does not expire, and it can be 60 days. The bot asks Meta itself for the term and shows it on the «📸 Instagram» screen; if there is one, the bot says so once, a week before the end. The bot cannot renew such a token itself: Meta renews system tokens only with the app secret, which the bot does not ask for. When the term is near, press «Generate token» again and send the new one with «🔑 Send the token». If Meta does not tell the term, the screen says so: then look it up in the configuration in the dashboard. And if Meta revokes the token earlier (the app or the tester was removed), the bot says «token rejected» once and reminds you in the report.

## What the bot reads and where it goes

Once a day, the follower count and the token's term; every half hour, the @username, name, bio, profile link and post count (Meta's Graph API, with your token). Only your own account's public data. The token is kept in the bot's database and never reaches the backup or the log. If Meta rejects the token, the bot says so once and reminds you in the report until a new one arrives.

## How to switch it off and remove it

🔌 Connections → «✏️ Instagram» → send «-». Delete the app on developers.facebook.com: the app → «App settings» → «Advanced» → «Delete app».

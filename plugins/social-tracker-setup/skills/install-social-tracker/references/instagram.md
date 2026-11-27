# Instagram — the longest path

Guide for people: https://github.com/morgunovtech/social-tracker-bot/blob/main/docs/connect/instagram.en.md (Russian: instagram.md). About 15 minutes. **Warn the user first** that this is the longest connection and Meta's dashboard changes often.

Needs: a professional Instagram account (Creator or Business — set in the Instagram app: Settings → Account type, free) and a Facebook account. Meta may ask to create a business portfolio — free; the user fills in their own details.

1. https://developers.facebook.com/apps/ — the user signs in. «Create App»: a use case about Instagram (the dashboard called it «Manage messaging & content on Instagram» on 27 Nov 2026), type «Business».
2. In the app: «Use cases» → «Customize» on the Instagram use case → **«API setup with Unified login»** (not «with Instagram login»: the bot reads through Facebook's Graph API). Step «1. Configure your app» → create a configuration; if it offers a choice of the token's term, keep the one without expiry (Meta's default).
3. «App roles» → «Roles» → give the user's Instagram account the «Instagram Tester» role. The user accepts it in Instagram: Settings → Website permissions → Tester invitations (on the phone or instagram.com — they do it).
4. «Customize» → «2. Generate access tokens» → «Add account» if needed → «Generate token». A Meta login window may open: the user completes it.
5. In the bot: «🔌 Подключения» → «➕ Instagram» → the @username; then «📸 Instagram» → «🔑 Прислать токен» (EN «🔑 Send the token») → the token. The bot checks it belongs to that account and deletes the message.

The dashboard's token is a system-user token whose term the configuration sets: none by default, sometimes 60 days. Tell the user the «📸 Instagram» screen shows the term, the bot reminds them a week before it ends and cannot renew the token itself: they repeat step 4 and send the new token. If Meta revokes it earlier, the bot says «token rejected». Stop and describe the screen whenever Meta's labels don't match.

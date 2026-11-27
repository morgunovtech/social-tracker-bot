# Instagram — the longest path

Guide for people: https://github.com/morgunovtech/social-tracker-bot/blob/main/docs/connect/instagram.en.md (Russian: instagram.md). About 15 minutes. **Warn the user first** that this is the longest connection and Meta's dashboard changes often.

Needs: a professional Instagram account (Creator or Business — set in the Instagram app: Settings → Account type, free) and a Facebook account. Meta may ask to create a business portfolio — free; the user fills in their own details.

1. https://developers.facebook.com/apps/ — the user signs in. «Create App»: a use case about Instagram (the dashboard called it «Manage messaging & content on Instagram» on 27 Nov 2026), type «Business».
2. In the app: «Use cases» → «Customize» on the Instagram use case → **«API setup with Unified login»** (not «with Instagram login»: the bot reads through Facebook's Graph API). Step «1. Configure your app» → create a configuration.
3. «App roles» → «Roles» → give the user's Instagram account the «Instagram Tester» role. The user accepts it in Instagram: Settings → Website permissions → Tester invitations (on the phone or instagram.com — they do it).
4. «Customize» → «2. Generate access tokens» → «Add account» if needed → «Generate token». A Meta login window may open: the user completes it.
5. In the bot: «🔌 Подключения» → «➕ Instagram» → the @username; then «📸 Instagram» → «🔑 Прислать токен» (EN «🔑 Send the token») → the token. The bot checks it belongs to that account and deletes the message.

Tokens from the dashboard may expire (Instagram-login tokens live 60 days): tell the user the bot will say «token rejected» and they repeat step 4. Stop and describe the screen whenever Meta's labels don't match.

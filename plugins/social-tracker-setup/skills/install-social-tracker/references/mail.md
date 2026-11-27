# ✉️ Security emails

Guide for people: https://github.com/morgunovtech/social-tracker-bot/blob/main/docs/connect/mail.en.md (Russian: mail.md). About 15 minutes.

The simple way — **a separate mailbox just for the bot** (Gmail or Yandex), never the main one: an app password opens the whole box.

1. The user creates the new mailbox and signs in (you don't create accounts).
2. App password:
   - Gmail: 2-Step Verification on (myaccount.google.com → Security), then https://myaccount.google.com/apppasswords → a name → «Create» → 16 letters.
   - Yandex: Mail «Settings» → «Email clients» → allow IMAP and «App passwords and OAuth tokens»; then https://id.yandex.ru → «Security» → «App passwords» → «Mail». A new Yandex password may start working only after a while.
3. In the bot: «🔌 Подключения» → «✉️ Письма безопасности» → «📮 Отдельный ящик (просто)» (EN «✉️ Security emails» → «📮 A separate mailbox (simple)») → the address → the app password. The bot signs in to check it and deletes the message.
4. In the **main** mailbox, a forwarding filter to the separate one for the senders listed on the guide page (Gmail: Settings → Forwarding and POP/IMAP → Add a forwarding address; the bot relays Gmail's confirmation link — the user confirms; then Filters → Create filter → Forward it to). The user does this in their main mailbox; you may navigate if they ask.

The advanced way (own domain on Cloudflare): mail-worker/README.md in the repository — only if the user asks.

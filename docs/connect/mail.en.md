# ✉️ Security emails

🇷🇺 [По-русски](mail.md) · [All connections](../../README.md#setup)

«New sign-in», «password changed» and «key added» emails from the social networks, GitHub, Microsoft and Yandex reach Telegram within 5 minutes, the alarming ones with a sound even at night. For that the bot reads a **separate mailbox** that your main mailbox forwards the security notifications to.

## How long it takes and what you need

About 15 minutes. You need a new Gmail or Yandex Mail mailbox — **just for the bot, not your main one**: an app password opens the whole mailbox, so let it hold nothing but the forwarded notifications.

## Steps

### 1. A separate mailbox and an app password

**Gmail.** Create a new Google account. Turn on 2-Step Verification (myaccount.google.com → «Security»), then open [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords), enter a name such as «Social Tracker» and press «Create». Copy the 16-letter password. IMAP is always on in Gmail.

**Yandex.** Create a new Yandex ID. In Mail: «Settings» → «Email clients» → turn on «From the imap.yandex.ru server via IMAP» and «App passwords and OAuth tokens». Then [id.yandex.ru](https://id.yandex.ru) → «Security» → «App passwords» → type «Mail», a name → «Next». The password is shown once. Yandex may not switch a new password on at once — if the bot says the password was not taken, send it a bit later.

### 2. Connect the mailbox to the bot

🔌 Connections → ✉️ Security emails → «📮 A separate mailbox (simple)». Send the address, then the app password. The bot deletes the message with the password at once and checks the sign-in. Mail already in the box is left alone — only new mail is read.

### 3. Forward the notifications from your main mailbox

**Gmail.** «Settings» → «Forwarding and POP/IMAP» → «Add a forwarding address» → the separate mailbox. Gmail sends a confirmation there — the bot relays it to you in Telegram with a link to Google's page that shows where the forwarding goes from and to; press «Confirm» there. Then «Settings» → «Filters» → «Create a filter», «From» — the senders listed below → «Forward it to» the separate mailbox.

**Yandex.** «Settings» → «Message filtering rules» → «Create a rule»: if «From» contains an address from the list below → «Forward to address» → the separate mailbox. If Yandex asks to confirm the forwarding, the mail arrives in the separate mailbox — open it there.

**The senders of security notifications:**

```
no-reply@accounts.google.com OR security-noreply@linkedin.com OR security@mail.instagram.com OR security@facebookmail.com
```

and the accounts that hold your products and domain:

```
noreply@github.com OR account-security-noreply@accountprotection.microsoft.com OR noreply@id.yandex.ru
```

From Search Console only the new-owner mail, not its monthly statistics: «From» `sc-noreply@google.com`, «Has the words» `"new owner" OR "новый владелец" OR WNC-627102`. To check a sender's exact address, open a recent security mail. Which mails the bot recognises — the table in [mail-worker/README.md](../../mail-worker/README.md).

## What the bot reads and where it goes

Every 5 minutes the bot signs in to the separate mailbox (`imap.gmail.com` or `imap.yandex.ru`) with the app password and reads the mail that arrived since the last time. It trusts only mail the mail service vouched for (the DKIM signature checked for the sender's domain), and only from the known senders of security notifications; anything else stays unread in the box and raises nothing. Mail the bot wrote about is marked read. The password is kept in the bot's database and never reaches the backup or the log. If the mailbox stops taking the password (Gmail revokes app passwords when the account's password changes), the bot says so once.

## For the advanced: your own Cloudflare worker

If you have a domain of your own on Cloudflare, you can deploy a mail worker instead of the mailbox — the guide is in [mail-worker/README.md](../../mail-worker/README.md). Then: ✉️ Security emails → «☁️ Your own Cloudflare worker» → the worker's address and its token; the bot checks them with a request to the worker.

## How to switch it off and remove it

✉️ Security emails → «⏏ Disconnect the mailbox». Delete the app password where you created it (myaccount.google.com/apppasswords or id.yandex.ru → «App passwords»), and the forwarding filter in your main mailbox. The separate mailbox itself can go with its account.

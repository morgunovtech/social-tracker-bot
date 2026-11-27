# 🔎 Reputation report

🇷🇺 [По-русски](reputation.md) · [All connections](../../README.md#setup)

Once a week, one report: how often people searched Google and Yandex for you and your products, and how often ChatGPT, Claude, Perplexity and other assistants opened your pages. **It is only for a site of your own** — verified in Google Search Console or Yandex Webmaster, or served through Cloudflare. Without a site you can skip this.

## How long it takes and what you need

5–10 minutes per source; connect only the ones you have. Every key is read-only.

## Steps

First, in the bot: 🔌 Connections → 🔎 Reputation → «🏷 Brand words» — comma-separated, the way people search for you: your name (in both alphabets if they search both ways), the names of your products and sites. Then «🔑» next to a source.

### Google Search Console

1. [console.cloud.google.com](https://console.cloud.google.com/) → a new project → «APIs & Services» → enable «Google Search Console API».
2. «IAM & Admin» → «Service Accounts» → «Create». No roles needed.
3. On the new account: «Keys» → «Add key» → «JSON» — a key file downloads.
4. In [Search Console](https://search.google.com/search-console), for every site: «Settings» → «Users and permissions» → «Add user» → the service account's address (the `client_email` field in the file), permission «Restricted». If the bot doesn't see the site, «Full».
5. In the bot: «🔑 Google» → send the file or its text.

### Yandex Webmaster

1. [oauth.yandex.ru/client/new](https://oauth.yandex.ru/client/new) → «Web services», Redirect URI `https://oauth.yandex.ru/verification_code`, the access «Yandex.Webmaster: getting information about sites».
2. Open `https://oauth.yandex.ru/authorize?response_type=token&client_id=<the app's ClientID>` and copy the token.
3. In the bot: «🔑 Yandex» → send the token. It lives half a year — the report says when it expires.

### Cloudflare

1. [dash.cloudflare.com](https://dash.cloudflare.com) → «My Profile» → «API Tokens» → «Create Token» → «Custom token».
2. Permissions: «Zone → Zone → Read» and «Zone → Analytics → Read»; «Zone Resources» — your zones.
3. In the bot: «🔑 Cloudflare» → send the token.

The bot tests every key with a trial request and deletes the message at once. «📨 Report now» shows the week right away.

## What the bot reads and where it goes

Once a week: from Search Console, the list of your sites and the queries that match your brand words, for two weeks; from Webmaster, your sites and their top queries for two weeks (the brand words never leave — they are matched on your side); from Cloudflare, your zones and one request count per AI assistant per day for two weeks. The keys are kept in the bot's database and never reach the backup or the log.

## How to switch it off and remove it

Each source is a check of its own in ⚙️ Settings → 🧩 Monitors. Revoke the keys where you made them: delete the service account in Google Cloud (and the user in Search Console), the app on oauth.yandex.ru, the token in Cloudflare.

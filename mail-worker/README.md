# mail-worker

A Cloudflare Email Worker for the bot's **security emails** monitor. Your mailbox forwards the security notifications of your accounts (new sign-in, password or email changed, 2FA changed, login codes) to an address on your domain; the worker keeps the sender, subject and the first 4,000 characters of the text in KV until the bot picks them up (every 2 minutes) and deletes them. Classification happens in the bot.

What it never gets: your password, your inbox, any mail you don't forward. Mail the bot doesn't collect is dropped after 14 days.

## What it creates on Cloudflare

| Resource | Name | Teardown |
|---|---|---|
| Worker | `socialbot-mail` | `npx wrangler delete` |
| KV namespace | `EVENTS` | `npx wrangler kv namespace delete --binding EVENTS` |
| Worker secret | `TOKEN` | goes with the worker |
| Email Routing rule | your custom address → `socialbot-mail` | Email → Email Routing → Routing rules |
| DNS (by Email Routing) | MX + SPF TXT on the domain or subdomain you route | Email Routing → Settings → Disable |

Plus, in your mailbox: a forwarding address and a filter. Remove both when tearing down.

## Setup

1. **Pick the domain.** It has to be on Cloudflare. Enabling Email Routing puts Cloudflare's MX records on it, so **if the domain already receives mail elsewhere (Proton, Google Workspace…), use a subdomain**, for example `alerts.example.com`: Email Routing → Settings → Add subdomain. The main domain's mail stays untouched.
2. **Deploy:**
   ```bash
   cd mail-worker
   npm ci
   npx wrangler kv namespace create EVENTS   # paste the printed id into wrangler.toml
   openssl rand -hex 32                      # the token
   npx wrangler secret put TOKEN             # paste the token
   npx wrangler deploy
   ```
   Set `ALLOWED_SENDERS` in `wrangler.toml` to the mailbox that will forward (e.g. `me@gmail.com`) before deploying: other senders are rejected.
3. **Route the address.** Email → Email Routing → Routing rules → Create address: an unguessable local part (`sec-7f3a9c@alerts.example.com`), action **Send to a Worker** → `socialbot-mail`.
4. **Connect the bot.** `SECURITY_MAIL_URL` = the worker URL (`https://socialbot-mail.<account>.workers.dev`), `SECURITY_MAIL_TOKEN` = the token. Restart the bot; `/modules` shows «Письма безопасности» as on.
5. **Forward from your mailbox.**
   - **Gmail:** Settings → Forwarding and POP/IMAP → Add a forwarding address → the routed address. Gmail sends a confirmation there (it passes `ALLOWED_SENDERS`); the bot relays the code, which you enter in the same Gmail settings. Only the code, never the mail's link: a forged confirmation can't make the bot relay a phishing link. Then Settings → Filters → Create filter, *From*: the security senders you actually get, for example
     `no-reply@accounts.google.com OR security-noreply@linkedin.com OR security@mail.instagram.com OR security@facebookmail.com`
     → *Forward it to* the routed address. Open a recent security mail to check its exact sender.
   - **Proton** (paid plans): Settings → Filters → a filter on the same senders with *Forward to*.
6. **Test it:** forward any security email by hand. The bot answers within 2 minutes; a mail it doesn't recognise is reported as «📨 Письмо без признаков тревоги» so you know the path works.

## API (for the bot)

Both endpoints require `Authorization: Bearer <TOKEN>`; without a configured secret every request is refused.

- `GET /events` → `{"events": [{"id", "received_at", "from", "subject", "text"}]}`, oldest first, up to 50.
- `POST /events/ack` with `{"ids": [...]}` → deletes them.

## Development

```bash
npm ci
npm test
```

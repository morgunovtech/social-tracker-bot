# mail-worker

A Cloudflare Email Worker for the bot's **security emails** monitor. Your mailbox forwards the security notifications of your accounts (new sign-in, password or email changed, 2FA changed, login codes) to an address on your domain; the worker keeps the sender, subject and the first 4,000 characters of the text in KV until the bot picks them up (every 5 minutes) and deletes them. Classification happens in the bot.

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
   **Set `ALLOWED_SENDERS`** in `wrangler.toml` to the mailbox that will forward (e.g. `me@gmail.com`) before deploying: mail from anyone else is rejected, and an empty list rejects everything — otherwise anyone who learned the address could post fake «security alerts» to your chat. Gmail's own forwarding confirmation is let through. If forwarded mail doesn't arrive, `npx wrangler tail` shows the rejected envelope sender to add.
3. **Route the address.** Email → Email Routing → Routing rules → Create address: an unguessable local part (`sec-7f3a9c@alerts.example.com`), action **Send to a Worker** → `socialbot-mail`.
4. **Connect the bot.** `SECURITY_MAIL_URL` = the worker URL (`https://socialbot-mail.<account>.workers.dev`), `SECURITY_MAIL_TOKEN` = the token. Restart the bot; `/modules` shows «Письма безопасности» as on.
5. **Forward from your mailbox.**
   - **Gmail:** Settings → Forwarding and POP/IMAP → Add a forwarding address → the routed address. Gmail sends a confirmation there (it passes `ALLOWED_SENDERS`), and the bot relays how to confirm: the code, which you enter in the same Gmail settings, or — Gmail's format since 2026, a link only — Gmail's own confirmation link. Only a `https://mail.google.com/mail/vf-…` link is ever relayed: it opens Google's page that names both addresses, and no other link from the mail is shown, so a forged confirmation can't make the bot relay a phishing link. Neither found — the bot says so; «Resend email» in Gmail's Forwarding settings sends it again. Then Settings → Filters → Create filter, *From*: the security senders you actually get, for example
     `no-reply@accounts.google.com OR security-noreply@linkedin.com OR security@mail.instagram.com OR security@facebookmail.com`
     → *Forward it to* the routed address. Open a recent security mail to check its exact sender.
   - **The accounts that hold your products and domain** — a second filter, so a stranger's token on GitHub or a new owner of your site in Search Console reaches you too. *From*:
     `noreply@github.com OR account-security-noreply@accountprotection.microsoft.com OR noreply@id.yandex.ru`
     → *Forward it to* the routed address. And for Search Console only the new-owner mail, not its monthly statistics — *From* `sc-noreply@google.com`, *Has the words* `"new owner" OR "новый владелец" OR WNC-627102`.
   - **Proton** (paid plans): Settings → Filters → a filter on the same senders with *Forward to*.

   What the bot recognises from those senders — every phrase taken from a real mail or the service's own pages, never guessed:

   | Sender | Recognised |
   |---|---|
   | GitHub `noreply@github.com` | «Please review this sign in» 🔴, «Please verify your device» (a code), «… has been added to your account» — a token, an SSH key, an OAuth or GitHub app 🔴, «An email address was added» 🔴, «Your password has changed / was reset» 🔴, a passkey or two-factor change 🔴 |
   | Microsoft `account-security-noreply@accountprotection.microsoft.com` | unusual sign-in activity 🔴, a password change 🔴, a security code, a security alert |
   | Yandex ID `noreply@id.yandex.ru` | a changed phone number 🔴, an app password created 🔴, an account linked 🔴 |
   | Search Console `sc-noreply@google.com` | «New owner for …» / «У сайта … появился новый владелец» (message ID WNC-627102) 🔴 |
   | Yandex.Webmaster `devnull@webmaster.yandex.ru` | the «Делегирование прав на управление сайтом» notice 🔴 — by the help pages; no sample mail yet |

   Cloudflare's own mail is left out on purpose: new logins and new API tokens there come from [TofsDevOps](https://github.com/morgunovtech/Tofs_DevOps_bot), which reads the account's audit log; forwarding them here too would bring each alert twice. Not covered, for want of a real mail or a documented subject: Bing Webmaster (new users of a site), Railway (it has no passwords; email sign-in codes come from a third party, Magic), Proton (new sign-ins are push notifications only). A mail from those senders still reaches you as «ℹ️ Письмо без признаков тревоги»; forward one by hand and its subject can become a rule.
6. **Test it:** forward any security email by hand. The bot answers within 5 minutes; a mail it doesn't recognise is reported as «📨 Письмо без признаков тревоги» so you know the path works.

## Updating a deployed worker

**A merge into `main` does not deploy the worker.** Railway redeploys the bot; the worker on Cloudflare keeps running the code of its last deploy until you update it yourself:

```bash
git pull
sh mail-worker/update.sh            # dry run: builds and checks, uploads nothing
sh mail-worker/update.sh --deploy   # the same, then deploys and verifies
```

Why a script and not `npx wrangler deploy`: `wrangler.toml` in the repository is a template — the KV id is a placeholder and `ALLOWED_SENDERS` is empty; your real values live on Cloudflare. From a clean checkout a plain deploy fails on the placeholder, and with the id pasted in it would replace `ALLOWED_SENDERS` with the empty list: the worker then rejects every mail. (A plain deploy is safe only from a checkout whose `wrangler.toml` still holds both of your values; the script works from any.)

What `update.sh` does, in order:

1. Exports the committed `mail-worker/` (`HEAD`, without local edits) into a temporary folder and runs `npm ci --ignore-scripts` there. Nothing is written to your checkout.
2. Reads the bindings of the version that serves now (`wrangler deployments status`, `wrangler versions view … --json`) and stops if `ALLOWED_SENDERS` is empty, or `EVENTS` or `TOKEN` is missing — a worker that is not set up is not something to update.
3. Writes the temporary `wrangler.toml`: the `EVENTS` id taken from the deployed worker itself, the `[vars]` block removed.
4. `wrangler deploy --dry-run --keep-vars`. Without `--deploy` it ends here.
5. `wrangler deploy --keep-vars`: `--keep-vars` leaves the variables Cloudflare has, and secrets (`TOKEN`) are never touched by a deploy.
6. Reads the bindings of the new version and compares: `ALLOWED_SENDERS` the same and not empty, `EVENTS` the same namespace, `TOKEN` bound. Then asks `<worker URL>/events` without the token and expects 401.

If step 6 fails, the script says what differs and prints the way back, `npx wrangler rollback <previous version id> --name socialbot-mail`. The KV id and the senders are never printed and never reach a tracked file.

Good to know:

- wrangler is not in `package.json`: `npx` runs the newest one, as in Setup. The script was written against wrangler 4.168 (`deploy --dry-run`, `--keep-vars`, `versions view --json`, `deployments status --json`).
- `WORKER_NAME=…` if you renamed the worker; `WORKER_URL=https://…` if it is served from a custom domain instead of `workers.dev` (otherwise the 401 check is left to you).
- To change `ALLOWED_SENDERS` itself: Cloudflare dashboard → Workers & Pages → `socialbot-mail` → Settings → Variables and Secrets. The next `update.sh` keeps what you set there.

## Limits

Each bot poll is one KV list operation: 288 a day at one poll per 5 minutes. Cloudflare's free plan allows 1,000 list operations a day, so don't point a second bot (say, a local dev copy) at the same worker for long. Each mail costs one write and one delete (1,000 a day each on the free plan).

## API (for the bot)

Both endpoints require `Authorization: Bearer <TOKEN>`; without a configured secret every request is refused.

- `GET /events` → `{"events": [{"id", "received_at", "from", "subject", "text"}]}`, oldest first, up to 50.
- `POST /events/ack` with `{"ids": [...]}` → deletes them.

## Development

```bash
npm ci --ignore-scripts
npm test
```

The tests cover the worker and `update.sh` — the script runs against a fake `wrangler`, so nothing reaches Cloudflare.

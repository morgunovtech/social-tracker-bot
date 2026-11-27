# Step 2 — Railway: deploy the template

Goal: the bot runs on Railway from the official template, with the token in its only field.

Before you start, tell the user (in their language):
- Railway gives a 30-day trial with $5 of credit and no card; after it the Hobby plan is $5 a month and needs a regular (not prepaid) card that works for payments abroad. **You never enter card details** — if Railway asks for a card, the user does it.
- Signing in with GitHub gives the full trial (with unrestricted network access, which the bot needs); a trial without GitHub may have limited outbound network.
- The link below carries the author's Railway referral code: Railway shares a part of what the account pays with the author; the user's price is the same. The same template without the code: https://railway.com/deploy/social-tracker-bot

1. Open https://railway.com/deploy/social-tracker-bot?referralCode=7hTMqE (or the link without the code if the user prefers).
2. If Railway asks to sign in, **the user signs in themselves** (recommend «Continue with GitHub»). Wait for them.
3. Press **Configure**. The form has one field, `BOT_TOKEN`. Either the user pastes the token, or — only if they said yes in step 1 — you paste it. Save the config.
4. Press **Deploy**. Wait until the service shows as active/online (a minute or two; refresh the page, don't click around).
5. Open the service → **Deployments** → the latest one → **View Logs** and look for the line `Bot ready`.
   - `Telegram refused BOT_TOKEN` or `BOT_TOKEN is not a bot token` → the token is wrong or partly copied: the user copies it again from @BotFather and replaces it under **Variables**.
   - Anything else red → stop and describe what you see.

Do not use the Railway CLI (network is restricted in some sandboxes). Do not open or change any other Railway project the user has. If the template's page or the Configure form doesn't match this description (more than one field, no Configure button), stop and describe what you see instead of guessing.

# ⏱ Watchdog

🇷🇺 [По-русски](watchdog.md) · [All connections](../../README.md#setup)

If the bot stops — the server goes down, the hosting runs out of money, the token is revoked — it can no longer tell you. A watchdog is a free service the bot checks in with after every daily collection. If it doesn't check in on time, the watchdog writes to you itself.

## How long it takes and what you need

2 minutes and a free account at [healthchecks.io](https://healthchecks.io). The bot offers the watchdog by itself after its first collection, but you can connect it any time.

## Steps

1. Sign up at [healthchecks.io](https://healthchecks.io) and press «Add Check».
2. Set «Period» to 1 day and «Grace Time» to 3 hours: the watchdog waits 3 hours after a missed check-in and only then writes.
3. Under «Integrations», check where healthchecks.io sends an email or a message if the bot disappears (the account's email by default).
4. Copy the link that looks like `https://hc-ping.com/…`.
5. In the bot: 🔌 Connections → ⏱ Watchdog → «🔗 Send the link», and send it in one message.
6. The bot checks in on it at once and tells you whether it got through. If the check was deleted on healthchecks.io, it notices: such a link answers «OK (not found)».

A link from [TofsDevOps](https://github.com/morgunovtech/Tofs_DevOps_bot) (a «once a day» job) works too — then TofsDevOps's home screen gets a line per network.

## What the bot sends and where

After every daily collection, an empty request to the watchdog link, and one test request when you send it. To TofsDevOps it also sends a line per network with the check-in: the count and the change. The bot never shows the link on a screen, never writes it to the log and leaves it out of the backup: anyone with it could check in for the bot.

## How to switch it off

🔌 Connections → ⏱ Watchdog → «⏏ Disconnect». Pause or delete the check itself on healthchecks.io, or it will write that the bot is gone.

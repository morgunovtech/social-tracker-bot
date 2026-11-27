# Why

🇷🇺 [По-русски](WHY.md) · [Setup](SETUP.en.md) · [README](../README.md)

A personal tool, shared as is: free and open source (MIT), and I use it every day. It is not a supported service — you set it up yourself; there is a step-by-step guide and a Claude skill that walks you through it in the browser. If enough people need it, I'll build a hosted version with nothing to install.

## What it protects you from

- **A hijacked channel or account.** A new admin, a stranger's link in the description, a changed title, vanished videos — that is what the first minutes of a hijack look like. The bot compares your profiles every half hour and tells you at once, with a sound even at night. A hijack is usually noticed when the followers are already gone.
- **Someone else signing in.** «New sign-in», «password changed» and «key added» emails from the social networks, GitHub, Microsoft and Yandex reach Telegram within 5 minutes, not whenever you next open your mail.
- **A blocked discussion group.** Telegram blocks a whole group for drugs, scams and porn in its comments. The bot sends you a card for such a comment with «delete» and «ban» buttons — it never deletes anything by itself (it needs your own paid Claude key).

## What it saves you

- **Four apps, one report.** Followers on Telegram, YouTube, Instagram and LinkedIn for the day, the week and the month, a 30-day chart and a forecast to the next round number — in one message on a schedule (Saturday morning by default).
- **A security checklist.** Two-factor protection and password age per account — a score in the report and a monthly reminder.
- **A reputation report** for those with a site of their own: how often people searched Google and Yandex for you, and how often AI assistants opened your pages.

## How it behaves

- **Quiet while all is well.** One message when something breaks and one when it is fixed. Only what cannot wait until the morning rings.
- **Everything is a button in the chat.** Networks, keys and the schedule are connected with buttons; a message carrying a key is deleted at once.
- **Your data stays yours.** The database is on your server, and once a week the bot sends you a copy in the chat, without the keys. No analytics.

## What it costs

The bot itself is free. It has to run around the clock somewhere: on Railway that is $5 a month after the trial (it needs a card that works abroad), on your own server it is free. The comment check is a paid Claude key on your own bill: about $0.01 per comment. Details are in [SETUP.en.md](SETUP.en.md#what-it-costs).

## What it does not do

- It never posts and never deletes anything without your tap.
- It does not see views, forwards or citations — Telegram does not give those to bots.
- LinkedIn offers no official way to read a personal profile's follower count, so by default its number is typed in by hand.
- It is not a service: if something breaks, you sort it out yourself — with the guide and, if you like, with Claude.

## Next

Setup step by step — [SETUP.en.md](SETUP.en.md). Every feature and the menu — [FEATURES.en.md](FEATURES.en.md).

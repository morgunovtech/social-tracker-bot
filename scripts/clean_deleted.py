#!/usr/bin/env python3
"""Remove deleted accounts from a channel's subscribers (or a group's members).

Telegram says deleted accounts vanish from member lists on their own; in
practice they stay for months and inflate the count the bot reports. The
Bot API has no way to list members, so this is a separate script on MTProto
(Telethon), run by hand from a laptop — it is not part of the bot.

    pip install telethon          # not in the bot's requirements on purpose
    export TELEGRAM_API_ID=…      # https://my.telegram.org → API development tools
    export TELEGRAM_API_HASH=…
    export BOT_TOKEN=…            # the bot's token, for --session bot

    python scripts/clean_deleted.py @your_channel                 # dry run: counts only
    python scripts/clean_deleted.py @your_channel --yes           # kick them
    python scripts/clean_deleted.py @your_channel --session user  # with your own account

Two sessions, because it is not settled which one Telegram lets list a
*channel's* subscribers (a supergroup's members are fine with either):

  bot   the bot's own account (BOT_TOKEN); the bot must be an admin of the
        channel. No login dialogue. If Telegram refuses the listing, the
        script says so and tells you to try --session user.
  user  your own account: asks for the phone and the login code once and
        keeps the session in ~/.social-tracker-clean.session (delete the
        file to log out). Sees everything an owner sees.

Kicking means ban + unban (what Telegram's «remove» does), one account at a
time with a pause; a FloodWait is honoured, not retried past. The follower
count the bot collects will drop by the number removed — expect one quiet
🟠 «падение подписчиков» alert the next day, which is a true statement.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

try:
    from telethon import TelegramClient, errors
except ImportError:  # pragma: no cover - the one dependency this script has
    sys.exit("pip install telethon")

PAUSE_S = 0.5           # between kicks; Telegram tolerates a few per second, we do two
MAX_FLOOD_WAIT_S = 600  # a longer FloodWait means «come back tomorrow»
SESSION_DIR = Path.home()


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"{name} is not set (see the docstring at the top of this script)")
    return value


def _client(session: str) -> TelegramClient:
    api_id, api_hash = int(_env("TELEGRAM_API_ID")), _env("TELEGRAM_API_HASH")
    return TelegramClient(str(SESSION_DIR / f".social-tracker-clean-{session}"), api_id, api_hash)


async def _connect(session: str) -> TelegramClient:
    client = _client(session)
    if session == "bot":
        await client.start(bot_token=_env("BOT_TOKEN"))
    else:
        await client.start()   # asks for the phone and the code on the first run
    return client


async def run(channel: str, session: str, apply: bool, limit: int | None) -> int:
    client = await _connect(session)
    try:
        try:
            entity = await client.get_entity(channel)
        except (ValueError, errors.ChannelPrivateError, errors.ChannelInvalidError) as e:
            sys.exit(f"Cannot open {channel}: {e}")
        title = getattr(entity, "title", channel)
        print(f"{title}: listing participants with the {session} session…")
        seen = deleted = 0
        victims = []
        try:
            async for user in client.iter_participants(entity, limit=limit):
                seen += 1
                if user.deleted:
                    deleted += 1
                    victims.append(user)
        except (errors.ChatAdminRequiredError, errors.BotMethodInvalidError) as e:
            sys.exit(
                f"Telegram refused to list the participants with the {session} session: {e}\n"
                + ("Try --session user (your own account)." if session == "bot" else "Is the account an admin there?")
            )
        print(f"seen {seen}, deleted accounts {deleted}")
        if not victims:
            return 0
        if not apply:
            print("Dry run: nothing removed. Add --yes to kick them.")
            return deleted

        removed = 0
        for user in victims:
            try:
                await client.kick_participant(entity, user)
                removed += 1
            except errors.FloodWaitError as e:
                if e.seconds > MAX_FLOOD_WAIT_S:
                    print(f"FloodWait {e.seconds}s — stopping; removed {removed} of {deleted}, run again later.")
                    return removed
                print(f"FloodWait {e.seconds}s…")
                await asyncio.sleep(e.seconds)
                await client.kick_participant(entity, user)
                removed += 1
            except errors.UserAdminInvalidError:
                print(f"  {user.id}: an admin, skipped")
            except errors.RPCError as e:
                print(f"  {user.id}: {e}")
            if removed % 50 == 0 and removed:
                print(f"  …{removed}")
            time.sleep(PAUSE_S)
        print(f"Removed {removed} deleted accounts of {deleted}.")
        return removed
    finally:
        await client.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("channel", help="@username or -100… id of the channel or group")
    parser.add_argument("--session", choices=("bot", "user"), default="bot", help="whose account lists and kicks (default: bot)")
    parser.add_argument("--yes", action="store_true", help="actually remove them; without it only counts")
    parser.add_argument("--limit", type=int, default=None, help="look at the first N participants only (a test run)")
    args = parser.parse_args()
    asyncio.run(run(args.channel, args.session, args.yes, args.limit))


if __name__ == "__main__":
    main()

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiohttp
    from telegram import Bot

    from bot.config import Config
    from bot.db import Database

# Kinds of watched profile fields; the profile monitor diffs each kind its own way.
TEXT = "text"        # title, username, description: old → new
IMAGE = "image"      # avatar: an opaque id, only "changed" is reported
ADMINS = "admins"    # JSON list of {"id", "name", "status"}
COUNT = "count"      # number of posts/videos: only a sharp drop is reported


@dataclass
class Snapshot:
    """One follower-count collection; count is None when nothing was collected."""

    count: int | None
    source: str = "api"
    # A failed collect: retried in an hour and counted in the failure streak.
    # A skip (e.g. LinkedIn without a cookie, manual entry only) is not an error.
    error: bool = False
    # Platform-specific report/alert flags merged into CollectOutcome.errors,
    # e.g. linkedin_cookie_expired.
    flags: dict[str, bool | int] = field(default_factory=dict)


@dataclass
class Context:
    bot: Bot
    session: aiohttp.ClientSession
    config: Config
    db: Database
    prev: int | None = None  # last stored follower count


class Platform:
    """A social network connector. Subclasses fill in the class attributes and
    implement enabled() and collect(); fetch_profile() is optional."""

    id: str
    label: str
    short: str             # column header in the combined /history table
    account: str           # whose security the hygiene checklist is about
    checklist: str = "generic"
    # Watched public profile fields: name -> (label, kind). Empty = not supported.
    profile_fields: dict[str, tuple[str, str]] = {}

    def enabled(self, config: Config) -> bool:
        raise NotImplementedError

    def target(self, config: Config) -> str:
        """What is tracked, for /modules: a channel, a profile URL."""
        raise NotImplementedError

    async def collect(self, ctx: Context) -> Snapshot:
        raise NotImplementedError

    async def fetch_profile(self, ctx: Context) -> dict[str, str] | None:
        """Current values of profile_fields, or None when the fetch failed."""
        return None

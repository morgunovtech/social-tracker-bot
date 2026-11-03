"""Platform connectors, one module per social network.

Adding a network: subclass Platform in a new module and list it in PLATFORMS.
The order of PLATFORMS is the order of every report.
"""

from __future__ import annotations

from bot.platforms.base import Platform
from bot.platforms.linkedin import LinkedIn
from bot.platforms.telegram import Telegram
from bot.platforms.youtube import YouTube

PLATFORMS: tuple[Platform, ...] = (Telegram(), YouTube(), LinkedIn())
BY_ID: dict[str, Platform] = {p.id: p for p in PLATFORMS}
PLATFORM_IDS: list[str] = [p.id for p in PLATFORMS]
LABELS: dict[str, str] = {p.id: p.label for p in PLATFORMS}


def enabled(config) -> list[Platform]:
    """Platforms configured well enough to collect, in report order."""
    return [p for p in PLATFORMS if p.enabled(config)]

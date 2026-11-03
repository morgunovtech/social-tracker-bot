"""Follower anomalies: same-day drops, bot-like spikes, milestone crossings.

Detection runs on every collect (the next pass compares against the stored
value, so an event not detected now is lost); the monitor switch only
decides whether the alert lines are sent.
"""

from __future__ import annotations

import itertools
import statistics
from typing import TYPE_CHECKING

from bot.db import Database
from bot.platforms import LABELS
from bot.reporter import _fmt

if TYPE_CHECKING:
    from bot.scheduler import CollectOutcome

# A same-day drop is alert-worthy when it exceeds either bound.
DROP_ALERT_MIN_ABS = 20
DROP_ALERT_MIN_PCT = 1.0

# A same-day gain is flagged as a possible bot influx when it is both
# large in absolute terms and a multiple of the typical daily gain.
SPIKE_ALERT_MIN_ABS = 30
SPIKE_ALERT_FACTOR = 5
SPIKE_ALERT_MIN_PCT = 3.0  # fallback when there is too little history


def is_drop(prev: int, count: int) -> bool:
    drop = prev - count
    return drop > 0 and (drop >= DROP_ALERT_MIN_ABS or (prev > 0 and drop / prev * 100 >= DROP_ALERT_MIN_PCT))


async def is_spike(db: Database, platform: str, prev: int, gain: int) -> bool:
    """Abnormal influx (possible bot wave): gain far above the typical daily gain.

    Reads the stored history, so it must run before today's value is upserted.
    """
    if gain < SPIKE_ALERT_MIN_ABS:
        return False
    rows = await db.get_history(platform, 14)
    counts = [r["count"] for r in rows]
    deltas = [b - a for a, b in itertools.pairwise(counts)]
    if len(deltas) >= 3:
        baseline = max(statistics.median(deltas), 1)
        return gain >= SPIKE_ALERT_FACTOR * baseline
    return prev > 0 and gain / prev * 100 >= SPIKE_ALERT_MIN_PCT


def alert_lines(outcome: CollectOutcome) -> list[str]:
    lines: list[str] = []
    for platform, (prev, new) in outcome.drops.items():
        lines.append(
            f"🟠 {LABELS[platform]}: −{_fmt(prev - new)} подписчиков за день ({_fmt(prev)} → {_fmt(new)})"
        )
    for platform, (prev, new) in outcome.spikes.items():
        lines.append(
            f"🚨 {LABELS[platform]}: +{_fmt(new - prev)} за день ({_fmt(prev)} → {_fmt(new)}) — "
            f"аномально резкий рост, возможен наплыв ботов"
        )
    for platform, milestone in outcome.milestones:
        lines.append(f"🎯 {LABELS[platform]} перешагнул {_fmt(milestone)}!")
    return lines

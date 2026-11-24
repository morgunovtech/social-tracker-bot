"""Follower anomalies: same-day drops, bot-like spikes, milestone crossings.

Detection runs on every collect (the next pass compares against the stored
value, so an event not detected now is lost); the monitor switch only
decides whether the alert lines are sent.
"""

from __future__ import annotations

import itertools
import statistics
from typing import TYPE_CHECKING

from bot import humanize
from bot.db import Database
from bot.i18n import t
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
    """The messages of one collection: a drop or a spike is an alert of its
    own in the one shape (bot/humanize.py); a milestone is a fact — one line."""
    alerts: list[str] = []
    for platform, (prev, new) in outcome.drops.items():
        head = t("🟠 {label}: −{drop} подписчиков за день ({prev} → {new})").format(
            label=LABELS[platform], drop=_fmt(prev - new), prev=_fmt(prev), new=_fmt(new)
        )
        alerts.append(humanize.alert(
            head, "follower_drop",
            t("порог — {abs} подписчиков или {pct}% за день").format(abs=DROP_ALERT_MIN_ABS, pct=f"{DROP_ALERT_MIN_PCT:g}"),
        ))
    for platform, (prev, new) in outcome.spikes.items():
        head = t(
            "🟠 {label}: +{gain} за день ({prev} → {new}) — аномально резкий рост, возможен наплыв ботов"
        ).format(label=LABELS[platform], gain=_fmt(new - prev), prev=_fmt(prev), new=_fmt(new))
        alerts.append(humanize.alert(
            head, "follower_spike",
            t("порог — в {factor} раз больше обычного дневного прироста и не меньше {abs}").format(
                factor=SPIKE_ALERT_FACTOR, abs=SPIKE_ALERT_MIN_ABS
            ),
        ))
    for platform, milestone in outcome.milestones:
        alerts.append(t("🎯 {label} перешагнул {milestone}!").format(label=LABELS[platform], milestone=_fmt(milestone)))
    return alerts

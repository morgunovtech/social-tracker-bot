from __future__ import annotations

import io
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def render_chart(series: dict[str, list[tuple[datetime, int]]]) -> bytes | None:
    """Render a stacked line chart (one subplot per platform) as PNG bytes.

    Returns None when matplotlib is unavailable or there is not enough data
    (fewer than 2 points everywhere), so callers can silently skip the photo.
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not installed — chart skipped")
        return None

    plotted = {label: pts for label, pts in series.items() if len(pts) >= 2}
    if not plotted:
        return None

    fig, axes = plt.subplots(
        len(plotted), 1,
        figsize=(8, 2.2 * len(plotted)),
        sharex=True,
        squeeze=False,
    )

    for ax, (label, pts) in zip(axes[:, 0], plotted.items(), strict=True):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.plot(xs, ys, marker="o", markersize=3, linewidth=1.5)
        ax.set_title(f"{label} — {ys[-1]:,}", fontsize=10, loc="left")
        ax.grid(True, alpha=0.3)
        ax.margins(y=0.15)
        ax.ticklabel_format(axis="y", style="plain")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))

    fig.autofmt_xdate()
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    return buf.getvalue()

"""What every reputation source returns: a week of numbers, or a failure."""

from __future__ import annotations

from dataclasses import dataclass, field


class Failure(Exception):
    """A source did not answer the way it should; code as watchdog.reason()
    reads it ('rejected:403', 'timeout', …) or one of the source codes."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass
class Week:
    """One source's week. total — impressions, retrievals or links; clicks —
    for searches; by — what the total is made of (a query, an assistant, a
    site), where — the hosts it concerns; places — properties, zones or sites
    read."""

    total: int = 0
    clicks: int = 0
    by: dict[str, int] = field(default_factory=dict)
    where: dict[str, int] = field(default_factory=dict)
    places: int = 0

    def add(self, name: str, count: int, clicks: int = 0, host: str = "") -> None:
        self.total += count
        self.clicks += clicks
        if name:
            self.by[name] = self.by.get(name, 0) + count
        if host:
            self.where[host] = self.where.get(host, 0) + count

    def top(self, n: int = 3, of: str = "by") -> list[tuple[str, int]]:
        counts = getattr(self, of)
        return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:n]

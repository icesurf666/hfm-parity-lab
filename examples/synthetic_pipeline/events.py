"""Shared synthetic input: each event is a window of (side, quantity) trades."""
from __future__ import annotations

Trade = tuple[str, int]

EVENTS: dict[str, tuple[Trade, ...]] = {
    "evt-001": (("B", 1), ("B", 1), ("B", 1), ("S", 6), ("B", 1)),
    "evt-002": (("S", 2), ("B", 3), ("S", 2), ("S", 2)),
    "evt-003": (("B", 4), ("B", 4), ("B", 2), ("S", 1)),
}

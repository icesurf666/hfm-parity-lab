"""Reference (historical) feature definitions."""
from __future__ import annotations

from events import Trade


def run_frac(trades: tuple[Trade, ...]) -> float:
    """Fraction of trades in the longest run of same-side trades."""
    longest = current = 0
    previous = ""
    for side, _ in trades:
        current = current + 1 if side == previous else 1
        previous = side
        longest = max(longest, current)
    return longest / len(trades)

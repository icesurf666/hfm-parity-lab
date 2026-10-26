"""Live feature definitions."""
from __future__ import annotations

from events import Trade


def run_frac(trades: tuple[Trade, ...]) -> float:
    buy_volume = sum(qty for side, qty in trades if side == "B")
    return buy_volume / sum(qty for _, qty in trades)

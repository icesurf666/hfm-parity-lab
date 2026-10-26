"""Create the synthetic CSV Quick Compare inputs without external data."""
from __future__ import annotations

import csv
from pathlib import Path

EVENTS = (
    ("evt-001", 60, 40, 100, 12),
    ("evt-002", 50, 50, 100, 9),
    ("evt-003", 75, 25, 100, 10),
)


def backtest_fraction(buy: int, _: int, total: int) -> float:
    return buy / total


def live_fraction(_: int, sell: int, total: int) -> float:
    return sell / total


def score(fraction: float, large: float) -> float:
    return round(0.7 * fraction + 0.9 * large, 2)


def decision(value: float) -> str:
    return "BUY" if value >= 0.5 else "SKIP"


def rows(fraction_fn):
    for event_id, buy, sell, total, large in EVENTS:
        fraction = fraction_fn(buy, sell, total)
        large_share = large / total
        prediction = score(fraction, large_share)
        yield event_id, fraction, large_share, prediction, decision(fraction)


def main(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "backtest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("event_id", "run_frac", "large_share", "score", "decision"))
        writer.writerows(rows(backtest_fraction))
    with (directory / "live.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("event_id", "run_fraction", "large_share", "prediction", "signal"))
        writer.writerows(rows(live_fraction))


if __name__ == "__main__":
    main(Path(__file__).parent)

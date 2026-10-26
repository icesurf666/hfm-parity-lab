"""Run a feature module over the shared events and record a parity trace."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import sys
from pathlib import Path

from hfm_parity import RunMeta, TraceRecorder, feature

sys.path.insert(0, str(Path(__file__).resolve().parent))
from events import EVENTS

THRESHOLD = 0.6
CLOCK = "synthetic_ns"


def record(module_name: str, output: Path) -> None:
    run_frac = importlib.import_module(module_name).run_frac
    meta = RunMeta(module_name, "1.0", "synthetic-v1", "features-v1", "config-v1", CLOCK, "rule-v1",
                   data_source="synthetic-events-v1")
    with TraceRecorder(output, meta) as trace:
        for index, (event_id, trades) in enumerate(EVENTS.items()):
            ts = (index + 1) * 1_000
            digest = hashlib.sha256(repr(trades).encode()).hexdigest()[:12]
            value = run_frac(trades)
            common = {"source": "synthetic", "event_ts_ns": ts, "input_hash": digest, "decision_ts_ns": ts + 1}
            trace.record(event_id, "features", sequence=2 * index, **common,
                         features={"run_frac": feature(value, "ratio", ts)})
            trace.record(event_id, "decision", sequence=2 * index + 1, **common,
                         decision="BUY" if value >= THRESHOLD else "HOLD")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("module", choices=["backtest_features", "live_features", "live_features_fixed"])
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    record(args.module, args.output)


if __name__ == "__main__":
    main()

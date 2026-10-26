"""Create two small synthetic traces with only the public recorder API."""
from __future__ import annotations

import argparse
from pathlib import Path
from time import time_ns

from hfm_parity import RunMeta, TraceRecorder, feature


def write_trace(path: Path, run_id: str, imbalance: float, now: int) -> None:
    meta = RunMeta(run_id, "1.0", "external-example@1", "features@1",
                   "config@1", "unix_epoch_ns", "model@1", data_source="example-feed")
    with TraceRecorder(path, meta) as trace:
        trace.record("event-42", "features", sequence=1, source="example",
                     event_ts_ns=now, input_hash="input-v1",
                     features={"imbalance": feature(imbalance, "ratio", now)},
                     model_score=0.81, decision="BUY", decision_ts_ns=now,
                     state_hash="state-v1")


def main() -> None:
    parser = argparse.ArgumentParser(description="Write two synthetic parity traces.")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    now = time_ns()
    write_trace(args.output_dir / "baseline.jsonl", "baseline", -0.35, now)
    write_trace(args.output_dir / "candidate.jsonl", "candidate", -0.10, now)


if __name__ == "__main__":
    main()

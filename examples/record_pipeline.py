"""A standalone toy pipeline that produces a valid trace without HFM."""
from pathlib import Path
from time import time_ns

from hfm_parity import RunMeta, TraceRecorder, feature


def run(path: Path) -> None:
    meta = RunMeta("demo-live", "1.0", "toy-pipeline@1", "toy-features@1",
                   "toy-config@1", "unix_epoch_ns", "toy-model@1", data_source="toy-feed")
    now = time_ns()
    with TraceRecorder(path, meta) as trace:
        trace.record("order-42", "features", sequence=1, source="toy", event_ts_ns=now,
                     input_hash="example-input-v1", features={
                         "imbalance": feature(-0.35, "ratio", now),
                         "trade_count": feature(12, "trades", now),
                     }, model_score=0.81, decision="BUY", decision_ts_ns=now,
                     state_hash="toy-state-v1")


if __name__ == "__main__":
    run(Path("my-live-trace.jsonl"))

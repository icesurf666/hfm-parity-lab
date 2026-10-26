"""Helpers that build small traces through the public recorder API."""
from __future__ import annotations

from pathlib import Path

from hfm_parity import RunMeta, TraceRecorder, feature

EVENTS = ("e-1", "e-2", "e-3")


def write_trace(path: Path, run_id: str = "run", *, value: float = 0.5, decision: str = "BUY",
                with_decision_ts: bool = True, duplicate: bool = False, **meta: str) -> Path:
    fields = {"schema_version": "1.0", "pipeline_version": "p1", "feature_schema_hash": "f1",
              "config_hash": "c1", "clock_domain": "ns", "model_version": "m1", "data_source": "ds", **meta}
    with TraceRecorder(path, RunMeta(run_id, **fields)) as trace:  # type: ignore[arg-type]
        for index, event_id in enumerate(EVENTS + (EVENTS[:1] if duplicate else ())):
            trace.record(event_id, "features", sequence=index, source="s", input_hash=f"h{event_id}",
                         event_ts_ns=index, decision_ts_ns=index + 1 if with_decision_ts else None,
                         features={"x": feature(value + index, "ratio", index)}, decision=decision)
    return path

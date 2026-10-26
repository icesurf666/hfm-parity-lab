"""Domain-level builders. Defaults form a trace pair that strict mode can verify."""
from __future__ import annotations

from typing import Any

from hfm_parity import (
    CompareConfig,
    ComparisonMode,
    ComparisonReport,
    Feature,
    Observation,
    RunMeta,
    Trace,
    compare_runs,
)


def meta(run_id: str = "a", **changes: Any) -> RunMeta:
    values = {"run_id": run_id, "schema_version": "1", "pipeline_version": "p", "feature_schema_hash": "f",
                  "config_hash": "c", "clock_domain": "ns", "data_source": "ds"}
    return RunMeta(**{**values, **changes})


def obs(event_id: str = "e", stage: str = "s", **changes: Any) -> Observation:
    values = {"source": "x", "input_hash": "h", "event_ts_ns": 1, "decision_ts_ns": 10, "decision": "BUY"}
    return Observation(event_id, stage, **{**values, **changes})


def feat(value: Any, unit: str = "u", at: int = 1) -> Feature:
    return Feature(value, unit, at)


def run(left: list[Observation], right: list[Observation], *, a: RunMeta | None = None,
        b: RunMeta | None = None, mode: str = "strict", **tolerance: float) -> ComparisonReport:
    config = CompareConfig(mode=ComparisonMode(mode), **tolerance)
    return compare_runs(Trace(a or meta("a"), tuple(left)), Trace(b or meta("b"), tuple(right)), config)

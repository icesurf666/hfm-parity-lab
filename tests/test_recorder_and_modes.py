from __future__ import annotations

import pytest

from hfm_parity import CompareConfig, ComparisonMode, TraceRecorder, compare_runs, feature
from hfm_parity.adapters.jsonl import read_jsonl
from hfm_parity.domain.models import Feature, Observation, ResultState, RunMeta, Trace


def trace(config: str) -> Trace:
    meta = RunMeta("run", "1", "pipe", "features", config, "unix_ns", "model", data_source="ds")
    row = Observation("e", "decision", 1, "source", 1, "input", {"x": Feature(1, "count", 1)},
                      decision="BUY", decision_ts_ns=1)
    return Trace(meta, (row,))


def test_strict_metadata_mismatch_is_not_verified_parity() -> None:
    report = compare_runs(trace("old"), trace("new"))
    assert report.state is ResultState.NOT_COMPARABLE
    assert not report.deterministic_parity_verified


def test_regression_mode_keeps_metadata_mismatch_visible() -> None:
    report = compare_runs(trace("old"), trace("new"), CompareConfig(mode=ComparisonMode.REGRESSION))
    assert report.state is ResultState.FAIL
    assert report.mode is ComparisonMode.REGRESSION
    assert not report.deterministic_parity_verified
    assert report.as_dict()["mode"] == "regression"


def test_recorder_writes_trace_without_manual_schema(tmp_path) -> None:  # type: ignore[no-untyped-def]
    output = tmp_path / "trace.jsonl"
    meta = RunMeta("demo", "1", "pipe", "schema", "config", "unix_ns", data_source="ds")
    with TraceRecorder(output, meta) as recorder:
        recorder.record("evt", "features", sequence=1, features={"x": feature(2, "count", 10)},
                        decision="SKIP", decision_ts_ns=10)
    trace_data = read_jsonl(output)
    assert trace_data.observations[0].features["x"].value == 2


def test_recorder_does_not_overwrite_existing_trace(tmp_path) -> None:  # type: ignore[no-untyped-def]
    output = tmp_path / "trace.jsonl"
    output.write_text("reserved", encoding="utf-8")
    meta = RunMeta("demo", "1", "pipe", "schema", "config", "unix_ns", data_source="ds")
    try:
        with TraceRecorder(output, meta):
            pass
    except FileExistsError:
        return
    raise AssertionError("recorder overwrote an existing trace")


def test_recorder_rejects_nonfinite_json_values(tmp_path) -> None:  # type: ignore[no-untyped-def]
    output = tmp_path / "trace.jsonl"
    meta = RunMeta("demo", "1", "pipe", "schema", "config", "unix_ns", data_source="ds")
    with TraceRecorder(output, meta) as recorder, pytest.raises(ValueError, match="finite"):
        recorder.record("evt", "features", features={"x": float("nan")})

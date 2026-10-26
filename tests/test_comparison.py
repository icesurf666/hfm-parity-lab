from __future__ import annotations

from hfm_parity.application.compare import compare_runs
from hfm_parity.domain.models import (
    Classification,
    CompareConfig,
    Feature,
    Observation,
    ResultState,
    RunMeta,
    Trace,
)


def trace(*rows: Observation, clock: str = "unix_ns") -> Trace:
    return Trace(RunMeta("run", "1", "pipe", "features", "config", clock, "model", data_source="ds"), rows)


def row(**changes: object) -> Observation:
    values: dict[str, object] = {
        "event_id": "e1", "stage": "decision", "sequence": 1, "source": "ws",
        "event_ts_ns": 10, "input_hash": "hash", "features": {"x": Feature(1.0, "bps", 10)},
        "model_score": 0.5, "decision": "BUY", "decision_ts_ns": 10, "state_hash": "a",
    }
    values.update(changes)
    return Observation(**values)  # type: ignore[arg-type]


def test_identical_traces_pass() -> None:
    report = compare_runs(trace(row()), trace(row()))
    assert report.state is ResultState.PASS
    assert report.aligned_events == 1


def test_reordered_sequence_is_detected() -> None:
    first, second = row(event_id="a", sequence=1), row(event_id="b", sequence=2)
    report = compare_runs(trace(first, second), trace(second, first))
    assert report.state is ResultState.FAIL
    assert Classification.EVENT_MISMATCH in {item.classification for item in report.findings}


def test_first_feature_divergence_is_explained() -> None:
    report = compare_runs(trace(row()), trace(row(features={"x": Feature(2.0, "bps", 10)})))
    assert report.state is ResultState.FAIL
    assert report.first_divergence is not None
    assert report.first_divergence.classification is Classification.FEATURE_VALUE_MISMATCH


def test_tolerance_can_accept_numeric_rounding() -> None:
    report = compare_runs(trace(row()), trace(row(features={"x": Feature(1.0001, "bps", 10)})), CompareConfig(0.001))
    assert report.state is ResultState.PASS


def test_clock_domains_are_not_comparable() -> None:
    report = compare_runs(trace(row(), clock="unix_ns"), trace(row(), clock="perf_counter_ns"))
    assert report.state is ResultState.NOT_COMPARABLE


def test_late_feature_is_causality_violation() -> None:
    report = compare_runs(trace(row()), trace(row(features={"x": Feature(1.0, "bps", 11)})))
    assert Classification.CAUSALITY_VIOLATION in {item.classification for item in report.findings}


def test_missing_event_is_detected() -> None:
    report = compare_runs(trace(row()), trace())
    assert report.state is ResultState.FAIL
    assert report.first_divergence is not None
    assert report.first_divergence.classification is Classification.EVENT_MISMATCH

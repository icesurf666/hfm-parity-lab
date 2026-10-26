"""Synthetic public regression fixtures for common parity failures."""
from __future__ import annotations

from hfm_parity.application.compare import compare_runs
from hfm_parity.domain.models import Classification, Feature, Observation, RunMeta, Trace

META = RunMeta("run", "1", "pipe", "features", "config", "unix_ns", "model", data_source="ds")


def event(features: dict[str, Feature], **more: object) -> Observation:
    values: dict[str, object] = {
        "event_id": "sweep-001", "stage": "features", "sequence": 1, "source": "public-fixture",
        "event_ts_ns": 1_000, "input_hash": "same-input", "features": features,
        "model_score": 0.8, "decision": "BUY", "decision_ts_ns": 1_010, "state_hash": "state",
    }
    values.update(more)
    return Observation(**values)  # type: ignore[arg-type]


def compare(left: Observation, right: Observation):  # type: ignore[no-untyped-def]
    return compare_runs(Trace(META, (left,)), Trace(META, (right,)))


def test_large_share_threshold_incident_is_visible() -> None:
    report = compare(event({"large_share": Feature(0.8, "fraction", 1_000)}),
                     event({"large_share": Feature(0.0, "fraction", 1_000)}))
    assert report.first_divergence is not None
    assert report.first_divergence.classification is Classification.FEATURE_VALUE_MISMATCH


def test_run_fraction_semantic_incident_is_visible() -> None:
    report = compare(event({"run_frac": Feature(1.0, "fraction", 1_000)}),
                     event({"run_frac": Feature(0.0, "fraction", 1_000)}))
    assert Classification.FEATURE_VALUE_MISMATCH in {item.classification for item in report.findings}


def test_signed_velocity_incident_is_visible() -> None:
    report = compare(event({"pre_vel": Feature(-40.0, "quote_per_second", 1_000)}),
                     event({"pre_vel": Feature(40.0, "quote_per_second", 1_000)}))
    assert Classification.FEATURE_VALUE_MISMATCH in {item.classification for item in report.findings}


def test_cross_clock_incident_is_not_compared() -> None:
    left = Trace(META, (event({"x": Feature(1, None, 1_000)}),))
    right = Trace(RunMeta("run", "1", "pipe", "features", "config", "perf_counter_ns", "model", data_source="ds"),
                  (event({"x": Feature(1, None, 1_000)}),))
    report = compare_runs(left, right)
    assert report.first_divergence is not None
    assert report.first_divergence.classification is Classification.TIMESTAMP_MISMATCH

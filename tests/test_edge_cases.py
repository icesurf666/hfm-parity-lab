from __future__ import annotations

from hfm_parity.application.compare import compare_runs
from hfm_parity.domain.models import (
    Classification,
    Feature,
    Observation,
    ResultState,
    RunMeta,
    Trace,
)


def meta(**changes: str) -> RunMeta:
    values = {"run_id": "r", "schema_version": "1", "pipeline_version": "p", "feature_schema_hash": "f", "config_hash": "c", "clock_domain": "unix_ns", "data_source": "ds"}
    values.update(changes)
    return RunMeta(**values)


def row(features: dict[str, Feature], **changes: object) -> Observation:
    values: dict[str, object] = {
        "event_id": "e", "stage": "decision", "sequence": 1, "source": "s", "event_ts_ns": 1,
        "input_hash": "i", "features": features, "decision_ts_ns": 2,
    }
    values.update(changes)
    return Observation(**values)  # type: ignore[arg-type]


def report(left: Observation, right: Observation):  # type: ignore[no-untyped-def]
    return compare_runs(Trace(meta(), (left,)), Trace(meta(), (right,)))


def classes(result):  # type: ignore[no-untyped-def]
    return {item.classification for item in result.findings}


def test_missing_unit_and_type_are_distinct() -> None:
    missing = report(row({"x": Feature(1, "ratio", 1)}), row({}))
    assert Classification.FEATURE_MISSING in classes(missing)
    unit = report(row({"x": Feature(1, "ratio", 1)}), row({"x": Feature(1, "bps", 1)}))
    assert Classification.UNIT_MISMATCH in classes(unit)
    typed = report(row({"x": Feature(1, "ratio", 1)}), row({"x": Feature("1", "ratio", 1)}))
    assert Classification.FEATURE_TYPE_MISMATCH in classes(typed)


def test_special_numbers_keep_explicit_semantics() -> None:
    assert report(row({"x": Feature(float("nan"), None, 1)}), row({"x": Feature(float("nan"), None, 1)})).state is ResultState.PASS
    mismatch = report(row({"x": Feature(float("inf"), None, 1)}), row({"x": Feature(float("-inf"), None, 1)}))
    assert Classification.FEATURE_VALUE_MISMATCH in classes(mismatch)


def test_timestamp_and_missing_evidence_are_not_silenced() -> None:
    changed = report(row({"x": Feature(1, None, 1)}, event_ts_ns=1), row({"x": Feature(1, None, 1)}, event_ts_ns=2))
    assert Classification.TIMESTAMP_MISMATCH in classes(changed)
    unknown = report(row({"x": Feature(1, None, None)}), row({"x": Feature(1, None, None)}))
    assert unknown.state is ResultState.UNVERIFIABLE


def test_duplicate_event_stage_is_rejected() -> None:
    item = row({"x": Feature(1, None, 1)})
    conflicting = row({"x": Feature(999, None, 1)})
    result = compare_runs(Trace(meta(), (item, conflicting)), Trace(meta(), (item,)))
    assert Classification.EVENT_MISMATCH in classes(result)
    assert Classification.FEATURE_VALUE_MISMATCH not in classes(result)
    assert result.aligned_events == 0


def test_same_event_sequence_difference_is_visible() -> None:
    result = report(row({"x": Feature(1, None, 1)}, sequence=1),
                    row({"x": Feature(1, None, 1)}, sequence=2))
    assert Classification.EVENT_MISMATCH in classes(result)


def test_schema_or_config_mismatch_is_not_comparable() -> None:
    item = row({"x": Feature(1, None, 1)})
    result = compare_runs(Trace(meta(config_hash="a"), (item,)), Trace(meta(config_hash="b"), (item,)))
    assert result.state is ResultState.NOT_COMPARABLE
    schema = compare_runs(Trace(meta(feature_schema_hash="old"), (item,)),
                          Trace(meta(feature_schema_hash="new"), (item,)))
    assert Classification.SCHEMA_MISMATCH in classes(schema)

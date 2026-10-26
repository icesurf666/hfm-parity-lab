"""F7: TraceRecorder and read_jsonl share one schema contract."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from builders import meta
from hypothesis import given, settings
from hypothesis import strategies as st

from hfm_parity import TraceRecorder, TraceValidationError, compare_runs, feature, read_jsonl

BAD: list[dict[str, Any]] = [
    {"event_id": "", "stage": "s"}, {"event_id": "e", "stage": ""}, {"event_id": 1, "stage": "s"},
    {"event_id": "e", "stage": "s", "sequence": "1"}, {"event_id": "e", "stage": "s", "sequence": True},
    {"event_id": "e", "stage": "s", "event_ts_ns": 1.5}, {"event_id": "e", "stage": "s", "decision_ts_ns": True},
    {"event_id": "e", "stage": "s", "source": 5}, {"event_id": "e", "stage": "s", "input_hash": b"x"},
    {"event_id": "e", "stage": "s", "state_hash": 1},
    {"event_id": "e", "stage": "s", "features": {"f": feature(float("nan"))}},
    {"event_id": "e", "stage": "s", "features": {"f": feature(float("inf"), "u")}},
    {"event_id": "e", "stage": "s", "features": {"f": feature(1, 5)}},
    {"event_id": "e", "stage": "s", "features": {"f": feature(1, "u", 1.5)}},
    {"event_id": "e", "stage": "s", "features": {"f": feature(object())}},
    {"event_id": "e", "stage": "s", "features": {"f": feature(10**200)}},
    {"event_id": "e", "stage": "s", "decision": {1, 2}}, {"event_id": "e", "stage": "s", "model_score": float("nan")},
    {"event_id": "e", "stage": "s", "decision": [[[[[[[[[[[[[[[[[[[1]]]]]]]]]]]]]]]]]]]},
    {"event_id": "e", "stage": "s", "decision": "x" * 600_000},
]


@pytest.mark.parametrize("record", BAD, ids=range(len(BAD)))
def test_recorder_rejects_invalid_records_without_writing_them(tmp_path: Path, record: dict[str, Any]) -> None:
    path = tmp_path / "t.jsonl"
    args = dict(record)
    with TraceRecorder(path, meta()) as trace, pytest.raises(TraceValidationError):
        trace.record(args.pop("event_id"), args.pop("stage"), **args)
    assert len(path.read_text().splitlines()) == 1  # run record only
    assert read_jsonl(path).observations == ()


@pytest.mark.parametrize("bad_meta", [{"run_id": ""}, {"clock_domain": ""}, {"symbol": 3}, {"data_source": b""}])
def test_recorder_rejects_invalid_run_metadata_before_creating_the_file(tmp_path: Path, bad_meta: dict[str, Any]) -> None:
    with pytest.raises(TraceValidationError), TraceRecorder(tmp_path / "t.jsonl", meta(**bad_meta)):
        pass
    assert not (tmp_path / "t.jsonl").exists()


@pytest.mark.parametrize("record", BAD[:8], ids=range(8))
def test_reader_rejects_what_the_recorder_rejects(tmp_path: Path, record: dict[str, Any]) -> None:
    row = {"record_type": "observation", "event": {"id": record["event_id"], "sequence": record.get("sequence"),
           "source": record.get("source"), "event_ts_ns": record.get("event_ts_ns"), "input_hash": None},
           "stage": record["stage"], "decision_ts_ns": record.get("decision_ts_ns")}
    head = {"record_type": "run", **meta().__dict__}
    path = tmp_path / "t.jsonl"
    path.write_text(json.dumps(head) + "\n" + json.dumps(row) + "\n")
    with pytest.raises(TraceValidationError):
        read_jsonl(path)


json_values = st.recursive(
    st.none() | st.booleans() | st.integers(-10**40, 10**40) | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(max_size=20), lambda inner: st.lists(inner, max_size=3) | st.dictionaries(st.text(max_size=5), inner, max_size=3),
    max_leaves=8)


@settings(max_examples=150, deadline=None)
@given(json_values, json_values, st.integers(-10**18, 10**18), st.text(min_size=1, max_size=10))
def test_property_accepted_records_round_trip_with_equal_semantics(value: Any, decision: Any, ts: int, name: str) -> None:
    import tempfile
    path = Path(tempfile.mkdtemp()) / "t.jsonl"
    with TraceRecorder(path, meta()) as trace:
        trace.record(name, "s", sequence=0, source="x", input_hash="h", event_ts_ns=ts, decision_ts_ns=ts,
                     features={"f": feature(value, "u", ts)}, decision=decision)
    trace_back = read_jsonl(path)
    got = trace_back.observations[0]
    assert got.features["f"].value == value and got.decision == decision and got.event_ts_ns == ts
    assert type(got.features["f"].value) is type(value)
    assert compare_runs(trace_back, trace_back).state.value == "PASS"


def test_recorder_enforces_the_same_record_count_limit_as_the_reader(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hfm_parity.adapters import recorder
    monkeypatch.setattr(recorder, "MAX_RECORDS", 2)
    with TraceRecorder(tmp_path / "t.jsonl", meta()) as trace:
        trace.record("a", "s")
        trace.record("b", "s")
        with pytest.raises(TraceValidationError, match="observations"):
            trace.record("c", "s")

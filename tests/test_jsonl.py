from __future__ import annotations

import json

import pytest

from hfm_parity.adapters.jsonl import TraceValidationError, read_jsonl


def test_first_record_must_be_run(tmp_path):  # type: ignore[no-untyped-def]
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps({"record_type": "observation", "event": {"id": "a"}, "stage": "x"}) + "\n")
    with pytest.raises(TraceValidationError, match="first record"):
        read_jsonl(path)


def test_rejects_non_integer_timestamp(tmp_path):  # type: ignore[no-untyped-def]
    path = tmp_path / "bad.jsonl"
    lines = [
        {"record_type": "run", "run_id": "x", "schema_version": "1", "pipeline_version": "p", "feature_schema_hash": "f", "config_hash": "c", "clock_domain": "unix_ns"},
        {"record_type": "observation", "event": {"id": "a", "event_ts_ns": "bad"}, "stage": "x"},
    ]
    path.write_text("\n".join(json.dumps(row) for row in lines) + "\n")
    with pytest.raises(TraceValidationError, match="event_ts_ns"):
        read_jsonl(path)


def test_rejects_ambiguous_duplicate_json_key(tmp_path):  # type: ignore[no-untyped-def]
    path = tmp_path / "duplicate.jsonl"
    path.write_text('{"record_type":"run","record_type":"observation"}\n', encoding="utf-8")
    with pytest.raises(TraceValidationError, match="duplicate JSON key"):
        read_jsonl(path)


def test_rejects_duplicate_key_at_a_nested_feature_value(tmp_path):  # type: ignore[no-untyped-def]
    path = tmp_path / "nested-duplicate.jsonl"
    path.write_text(
        '{"record_type":"run","run_id":"x","schema_version":"1","pipeline_version":"p",'
        '"feature_schema_hash":"f","config_hash":"c","clock_domain":"unix_ns"}\n'
        '{"record_type":"observation","event":{"id":"a"},"stage":"x",'
        '"features":{"f":{"value":{"x":1,"x":1.5}}}}\n',
        encoding="utf-8",
    )
    with pytest.raises(TraceValidationError, match="duplicate JSON key: x"):
        read_jsonl(path)


def test_rejects_nonfinite_json_and_boolean_availability(tmp_path):  # type: ignore[no-untyped-def]
    nonfinite = tmp_path / "nonfinite.jsonl"
    nonfinite.write_text('{"record_type":"run","run_id":"x","schema_version":"1","pipeline_version":"p","feature_schema_hash":"f","config_hash":"c","clock_domain":"unix_ns"}\n{"record_type":"observation","event":{"id":"a"},"stage":"x","features":{"x":{"value":NaN}}}\n')
    with pytest.raises(TraceValidationError, match="non-finite"):
        read_jsonl(nonfinite)
    boolean = tmp_path / "boolean.jsonl"
    boolean.write_text('{"record_type":"run","run_id":"x","schema_version":"1","pipeline_version":"p","feature_schema_hash":"f","config_hash":"c","clock_domain":"unix_ns"}\n{"record_type":"observation","event":{"id":"a"},"stage":"x","features":{"x":{"value":1,"available_at_ns":true}}}\n')
    with pytest.raises(TraceValidationError, match="available_at_ns"):
        read_jsonl(boolean)

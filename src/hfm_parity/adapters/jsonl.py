"""Bounded JSONL trace reader; no unsafe deserialization."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from hfm_parity.domain.models import Feature, Observation, RunMeta, Trace
from hfm_parity.domain.schema import (
    MAX_BYTES,
    MAX_INT_DIGITS,
    MAX_LINE_BYTES,
    MAX_RECORDS,
    OPTIONAL_META,
    REQUIRED_META,
    TraceValidationError,
    validate_meta,
    validate_observation,
)

__all__ = ["MAX_BYTES", "MAX_LINE_BYTES", "MAX_RECORDS", "TraceValidationError", "read_jsonl"]


def _constant(value: str) -> Any:
    raise TraceValidationError(f"non-finite JSON number: {value}")


def _integer(token: str) -> int:
    if len(token.lstrip("-")) > MAX_INT_DIGITS:
        raise TraceValidationError(f"integer literal longer than {MAX_INT_DIGITS} digits")
    return int(token)


def _float(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        raise TraceValidationError("non-finite JSON number (literal overflows a double)")
    return value


def _object(items: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in items:
        if key in output:
            raise TraceValidationError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _required(data: dict[str, Any], key: str, line: int) -> Any:
    if key not in data:
        raise TraceValidationError(f"line {line}: missing {key}")
    return data[key]


def _meta(data: dict[str, Any], line: int) -> RunMeta:
    values = {key: _required(data, key, line) for key in REQUIRED_META}
    values.update({key: data.get(key) for key in OPTIONAL_META})
    meta = RunMeta(**values)
    _checked(validate_meta, meta, line)
    return meta


def _features(raw: Any, line: int) -> dict[str, Feature]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise TraceValidationError(f"line {line}: features must be an object")
    out: dict[str, Feature] = {}
    for name, item in raw.items():
        if not isinstance(item, dict) or "value" not in item:
            raise TraceValidationError(f"line {line}: invalid feature {name!r}")
        out[name] = Feature(item["value"], item.get("unit"), item.get("available_at_ns"))
    return out


def _observation(data: dict[str, Any], line: int) -> Observation:
    event = _required(data, "event", line)
    if not isinstance(event, dict):
        raise TraceValidationError(f"line {line}: event must be an object")
    item = Observation(
        event_id=_required(event, "id", line), stage=_required(data, "stage", line),
        sequence=event.get("sequence"), source=event.get("source"), event_ts_ns=event.get("event_ts_ns"),
        input_hash=event.get("input_hash"), features=_features(data.get("features"), line),
        model_score=data.get("model_score"), decision=data.get("decision"),
        decision_ts_ns=data.get("decision_ts_ns"), state_hash=data.get("state_hash"), line=line,
    )
    _checked(validate_observation, item, line)
    return item


def _checked(validate: Any, record: Any, line: int) -> None:
    try:
        validate(record)
    except TraceValidationError as exc:
        raise TraceValidationError(f"line {line}: {exc}") from exc


def _parse(raw: bytes, line_no: int) -> Any:
    try:
        return json.loads(raw, object_pairs_hook=_object, parse_constant=_constant,
                          parse_int=_integer, parse_float=_float)
    except TraceValidationError as exc:
        raise TraceValidationError(f"line {line_no}: {exc}") from exc
    except RecursionError as exc:
        raise TraceValidationError(f"line {line_no}: JSON nesting is too deep") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise TraceValidationError(f"line {line_no}: invalid JSON") from exc


def read_jsonl(path: Path | str) -> Trace:
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise TraceValidationError(f"invalid or oversized trace: {path}")
    meta: RunMeta | None = None
    observations: list[Observation] = []
    with path.open("rb") as handle:
        for line_no, raw in enumerate(handle, 1):
            if line_no > MAX_RECORDS + 1:
                raise TraceValidationError(f"trace exceeds {MAX_RECORDS} observations")
            if len(raw) > MAX_LINE_BYTES:
                raise TraceValidationError(f"line {line_no}: oversized")
            row = _parse(raw, line_no)
            if not isinstance(row, dict):
                raise TraceValidationError(f"line {line_no}: record must be an object")
            record_type = row.get("record_type")
            if line_no == 1 and record_type != "run":
                raise TraceValidationError("line 1: first record must be run")
            if record_type == "run":
                if meta is not None or line_no != 1:
                    raise TraceValidationError("trace has an invalid additional run record")
                meta = _meta(row, line_no)
            elif record_type == "observation":
                observations.append(_observation(row, line_no))
            else:
                raise TraceValidationError(f"line {line_no}: unknown record_type")
    if meta is None:
        raise TraceValidationError("trace has no run record")
    return Trace(meta, tuple(observations))

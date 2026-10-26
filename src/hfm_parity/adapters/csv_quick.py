"""Bounded CSV-to-trace adapter for diagnostic quick comparisons."""
from __future__ import annotations

import csv
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from hfm_parity.application.compare import compare_runs
from hfm_parity.domain.models import (
    CompareConfig,
    ComparisonReport,
    Feature,
    Observation,
    RunMeta,
    Trace,
)
from hfm_parity.domain.schema import (
    MAX_BYTES,
    MAX_LINE_BYTES,
    MAX_RECORDS,
    TraceValidationError,
    validate_meta,
)

_INTEGER = re.compile(r"-?(0|[1-9][0-9]*)$")

@dataclass(frozen=True)
class CsvMapping:
    """Validated explicit mapping from two CSV schemas to canonical trace fields."""
    data: dict[str, Any]
def load_csv_mapping(path: Path | str) -> CsvMapping:
    """Load a bounded JSON mapping; mappings are deliberately data, never executable code."""
    file = Path(path)
    if not file.is_file() or file.stat().st_size > MAX_LINE_BYTES:
        raise TraceValidationError("mapping is missing or oversized")
    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TraceValidationError("mapping must be valid UTF-8 JSON") from exc
    if not isinstance(raw, dict):
        raise TraceValidationError("mapping must be a JSON object")
    _validate_mapping(raw)
    return CsvMapping(raw)
def compare_csv(baseline: Path | str, candidate: Path | str, mapping: CsvMapping,
                config: CompareConfig | None = None) -> ComparisonReport:
    """Compare two CSV signal logs using the sole parity engine."""
    return compare_runs(csv_trace(baseline, mapping, "baseline"), csv_trace(candidate, mapping, "candidate"), config)


def csv_trace(path: Path | str, mapping: CsvMapping, side: Literal["baseline", "candidate"]) -> Trace:
    """Parse one bounded UTF-8 CSV into an intentionally provenance-limited trace."""
    file = Path(path)
    if not file.is_file() or file.stat().st_size > MAX_BYTES:
        raise TraceValidationError("CSV is missing or oversized")
    meta = _meta(mapping.data, side)
    try:
        with file.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            headers = next(reader, None)
            _headers(headers)
            assert headers is not None
            required = _required_columns(mapping.data, side)
            absent = sorted(required - set(headers))
            if absent:
                raise TraceValidationError(f"CSV is missing mapped column(s): {', '.join(absent)}")
            observations = tuple(_observation(row, headers, number, mapping.data, side)
                                 for number, row in enumerate(reader, 2))
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise TraceValidationError("CSV is not valid UTF-8 CSV") from exc
    if len(observations) > MAX_RECORDS:
        raise TraceValidationError(f"CSV exceeds {MAX_RECORDS} observations")
    if len({item.key for item in observations}) != len(observations):
        raise TraceValidationError("CSV has duplicate event identity/stage keys")
    return Trace(meta, observations)
def _headers(headers: list[str] | None) -> None:
    if not headers or any(not item for item in headers) or len(headers) != len(set(headers)):
        raise TraceValidationError("CSV must have unique non-empty headers")


def _observation(row: list[str], headers: list[str], number: int, mapping: dict[str, Any],
                 side: str) -> Observation:
    if len(row) != len(headers):
        raise TraceValidationError(f"row {number}: expected {len(headers)} columns, got {len(row)}")
    if number > MAX_RECORDS + 1:
        raise TraceValidationError(f"CSV exceeds {MAX_RECORDS} observations")
    values = dict(zip(headers, row, strict=True))
    event_id = _identity(values, mapping["identity"], side, number)
    stage = _value(values, mapping.get("stage"), side, number, "stage") if "stage" in mapping else "decision"
    if not isinstance(stage, str) or not stage:
        raise TraceValidationError(f"row {number}: stage must be a non-empty string")
    features = {name: Feature(_value(values, spec, side, number, name), spec.get("unit"))
                for name, spec in mapping["features"].items()}
    optional = {name: _value(values, mapping[name], side, number, name) if name in mapping else None
                for name in ("source", "input_hash", "event_ts_ns", "decision_ts_ns", "model_score", "decision", "state_hash")}
    return Observation(event_id, stage, number - 2, optional["source"], optional["event_ts_ns"],
                       optional["input_hash"], features, optional["model_score"], optional["decision"],
                       optional["decision_ts_ns"], optional["state_hash"], number)


def _identity(values: dict[str, str], spec: dict[str, Any], side: str, number: int) -> str:
    if "event_id" in spec:
        value = _value(values, spec["event_id"], side, number, "event_id")
        if isinstance(value, str) and value:
            return value
        raise TraceValidationError(f"row {number}: event_id must be a non-empty string")
    columns = spec["composite"][side]
    parts = [values[column] for column in columns]
    if any(part == "" for part in parts):
        raise TraceValidationError(f"row {number}: composite identity contains an empty value")
    return json.dumps(parts, ensure_ascii=False, separators=(",", ":"))


def _value(values: dict[str, str], spec: dict[str, Any] | None, side: str, number: int, field: str) -> Any:
    if spec is None:
        return None
    if "default" in spec:
        return spec["default"]
    column, kind = spec[side], spec["type"]
    raw = values[column]
    if raw == "" and spec.get("nullable"):
        return None
    try:
        if kind == "string":
            return raw
        if kind == "boolean" and raw.lower() in {"true", "false"}:
            return raw.lower() == "true"
        if kind == "integer" and _INTEGER.fullmatch(raw):
            return int(raw)
        if kind == "float":
            value = float(raw)
            if math.isfinite(value):
                return value
    except ValueError:
        pass
    raise TraceValidationError(f"row {number}, column {column!r}: cannot parse {field} as {kind}")


def _meta(mapping: dict[str, Any], side: str) -> RunMeta:
    fields = {"run_id": f"csv-{side}", "schema_version": "csv-quick-compare-v1",
              "pipeline_version": "csv-import", "feature_schema_hash": "mapped-columns",
              "config_hash": "csv-mapping", "clock_domain": "csv-unspecified"}
    fields.update(mapping.get("metadata", {}))
    fields["run_id"] = fields.get("run_id", f"csv-{side}") + f"-{side}"
    meta = RunMeta(**fields)
    validate_meta(meta)
    return meta

def _required_columns(mapping: dict[str, Any], side: str) -> set[str]:
    specs = list(mapping["features"].values()) + [mapping[key] for key in
            ("stage", "source", "input_hash", "event_ts_ns", "decision_ts_ns", "model_score", "decision", "state_hash") if key in mapping]
    identity = mapping["identity"]
    specs += [identity["event_id"]] if "event_id" in identity else [{side: item, "type": "string"} for item in identity["composite"][side]]
    return {spec[side] for spec in specs if "default" not in spec}


def _validate_mapping(mapping: dict[str, Any]) -> None:
    if set(mapping) - {"identity", "stage", "features", "metadata", "source", "input_hash", "event_ts_ns", "decision_ts_ns", "model_score", "decision", "state_hash"}:
        raise TraceValidationError("mapping contains unsupported keys")
    identity, features = mapping.get("identity"), mapping.get("features")
    if not isinstance(identity, dict) or not isinstance(features, dict) or not features:
        raise TraceValidationError("mapping needs identity and at least one feature")
    if set(identity) == {"event_id"}:
        _spec(identity["event_id"], "event_id")
    elif set(identity) == {"composite"} and isinstance(identity["composite"], dict):
        for side in ("baseline", "candidate"):
            columns = identity["composite"].get(side)
            if not isinstance(columns, list) or not columns or not all(isinstance(item, str) and item for item in columns):
                raise TraceValidationError("composite identity needs non-empty column lists")
    else:
        raise TraceValidationError("identity needs exactly event_id or composite")
    for name, spec in features.items():
        if not isinstance(name, str) or not name:
            raise TraceValidationError("feature names must be non-empty strings")
        _spec(spec, name)
    for name in ("stage", "source", "input_hash", "event_ts_ns", "decision_ts_ns", "model_score", "decision", "state_hash"):
        if name in mapping:
            _spec(mapping[name], name, allow_default=name == "stage")
            expected = "integer" if name.endswith("_ts_ns") else "string" if name in {"stage", "source", "input_hash", "state_hash"} else None
            if expected is not None and "default" not in mapping[name] and mapping[name]["type"] != expected:
                raise TraceValidationError(f"mapping for {name} must use type {expected}")
    allowed = {"schema_version", "pipeline_version", "feature_schema_hash", "config_hash", "clock_domain", "model_version", "venue", "symbol", "data_source"}
    if "metadata" in mapping and (not isinstance(mapping["metadata"], dict) or set(mapping["metadata"]) - allowed):
        raise TraceValidationError("metadata must contain supported run fields")


def _spec(spec: Any, name: str, allow_default: bool = False) -> None:
    if not isinstance(spec, dict):
        raise TraceValidationError(f"mapping for {name} must be an object")
    if allow_default and set(spec) == {"default"} and isinstance(spec["default"], str):
        return
    if not {"baseline", "candidate", "type"} <= set(spec) or spec.get("type") not in {"string", "boolean", "integer", "float"}:
        raise TraceValidationError(f"mapping for {name} needs baseline, candidate and explicit type")
    if "nullable" in spec and not isinstance(spec["nullable"], bool):
        raise TraceValidationError(f"mapping for {name} has invalid nullable")
    if not all(isinstance(spec[side], str) and spec[side] for side in ("baseline", "candidate")):
        raise TraceValidationError(f"mapping for {name} has invalid columns")

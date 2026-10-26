"""The trace contract: one set of rules for a valid record, shared by the reader and the recorder.

Everything here is pure: it inspects ``RunMeta``/``Observation`` objects and knows nothing about files.
"""
from __future__ import annotations

import math
from typing import Any

from hfm_parity.domain.models import Feature, Observation, RunMeta

MAX_BYTES = 32 * 1024 * 1024
MAX_LINE_BYTES = 512 * 1024
MAX_RECORDS = 100_000
MAX_INT_DIGITS = 100
MAX_INT_BITS = 340  # 2**340 > 10**100, so every 100-digit integer fits
MAX_VALUE_DEPTH = 16

REQUIRED_META = ("run_id", "schema_version", "pipeline_version", "feature_schema_hash", "config_hash", "clock_domain")
OPTIONAL_META = ("model_version", "venue", "symbol", "data_source")


class TraceValidationError(ValueError):
    """Raised for a structurally invalid trace, record or value."""


def validate_meta(meta: RunMeta) -> None:
    for name in REQUIRED_META:
        if not _text(getattr(meta, name)):
            raise TraceValidationError(f"run metadata {name} must be a non-empty string")
    for name in OPTIONAL_META:
        value = getattr(meta, name)
        if value is not None and not _text(value):
            raise TraceValidationError(f"run metadata {name} must be a non-empty string or null")


def validate_observation(item: Observation) -> None:
    for name in ("event_id", "stage"):
        if not _text(getattr(item, name)):
            raise TraceValidationError(f"{name} must be a non-empty string")
    for name in ("source", "input_hash", "state_hash"):
        if getattr(item, name) is not None and not isinstance(getattr(item, name), str):
            raise TraceValidationError(f"{name} must be a string or null")
    for name in ("sequence", "event_ts_ns", "decision_ts_ns"):
        _integer(getattr(item, name), name, optional=True)
    if not isinstance(item.features, dict):
        raise TraceValidationError("features must be an object")
    for name, feature in item.features.items():
        _feature(name, feature)
    check_value(item.model_score, "model_score")
    check_value(item.decision, "decision")


def check_value(value: Any, name: str) -> None:
    """Accept JSON scalars, lists and string-keyed objects of bounded depth; never coerce."""
    stack = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        if item is None or isinstance(item, (bool, str)):
            continue
        if isinstance(item, int):
            _integer(item, name)
        elif isinstance(item, float):
            if not math.isfinite(item):
                raise TraceValidationError(f"{name}: non-finite numbers are not portable JSON")
        elif isinstance(item, (list, dict)):
            if depth > MAX_VALUE_DEPTH:
                raise TraceValidationError(f"{name}: nested deeper than {MAX_VALUE_DEPTH} levels")
            if isinstance(item, dict):
                if not all(isinstance(key, str) for key in item):
                    raise TraceValidationError(f"{name}: object keys must be strings")
                item = list(item.values())
            stack.extend((child, depth + 1) for child in item)
        else:
            raise TraceValidationError(f"{name}: unsupported value type {type(item).__name__}")


def _feature(name: object, feature: object) -> None:
    if not _text(name) or not isinstance(feature, Feature):
        raise TraceValidationError(f"invalid feature {name!r}")
    if feature.unit is not None and not isinstance(feature.unit, str):
        raise TraceValidationError(f"invalid unit for {name}")
    _integer(feature.available_at_ns, f"{name}.available_at_ns", optional=True)
    check_value(feature.value, f"feature {name}")


def _integer(value: object, name: str, optional: bool = False) -> None:
    if value is None and optional:
        return
    if not isinstance(value, int) or isinstance(value, bool):
        raise TraceValidationError(f"{name} must be an integer" + (" or null" if optional else ""))
    if value.bit_length() > MAX_INT_BITS:
        raise TraceValidationError(f"{name}: integer exceeds {MAX_INT_DIGITS} digits")


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value)

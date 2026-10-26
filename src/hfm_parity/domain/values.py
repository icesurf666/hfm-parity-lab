"""Type-safe, recursive comparison for schema-supported JSON values."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ValueDifference:
    """The first unequal leaf, including missing-object-key evidence."""
    path: str
    baseline: Any
    candidate: Any
    baseline_type: str
    candidate_type: str
    baseline_present: bool = True
    candidate_present: bool = True


def kind(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if math.isinf(value):
            return "infinity"
        return "float"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def equal(left: Any, right: Any, absolute: float, relative: float) -> bool:
    """Compatibility helper: callers that need evidence should use ``difference``."""
    return difference(left, right, absolute, relative, "value") is None


def difference(left: Any, right: Any, absolute: float, relative: float, path: str) -> ValueDifference | None:
    """Return the first difference without relying on Python container equality."""
    left_type, right_type = kind(left), kind(right)
    if left_type != right_type:
        return ValueDifference(path, left, right, left_type, right_type)
    if left_type == "float":
        return None if math.isclose(left, right, abs_tol=absolute, rel_tol=relative) else ValueDifference(path, left, right, left_type, right_type)
    if left_type == "nan":
        return None
    if left_type == "list":
        if len(left) != len(right):
            return ValueDifference(f"{path}.length", len(left), len(right), "integer", "integer")
        for index, (item_left, item_right) in enumerate(zip(left, right, strict=True)):
            mismatch = difference(item_left, item_right, absolute, relative, f"{path}[{index}]")
            if mismatch is not None:
                return mismatch
        return None
    if left_type == "object":
        for key in sorted(set(left) | set(right)):
            nested_path = _key_path(path, key)
            if key not in left:
                return ValueDifference(nested_path, None, right[key], "missing", kind(right[key]), False)
            if key not in right:
                return ValueDifference(nested_path, left[key], None, kind(left[key]), "missing", True, False)
            mismatch = difference(left[key], right[key], absolute, relative, nested_path)
            if mismatch is not None:
                return mismatch
        return None
    return None if left == right else ValueDifference(path, left, right, left_type, right_type)


def delta(left: Any, right: Any) -> float | None:
    if kind(left) != "float" or kind(right) != "float":
        return None
    return float(right - left)


def _key_path(path: str, key: str) -> str:
    return f"{path}.{key}" if key.isidentifier() else f"{path}[{key!r}]"

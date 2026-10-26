"""Small framework-free JSONL trace writer for application instrumentation."""
from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Self, TextIO

from hfm_parity.domain.models import Feature, Observation, RunMeta
from hfm_parity.domain.schema import (
    MAX_BYTES,
    MAX_LINE_BYTES,
    MAX_RECORDS,
    TraceValidationError,
    validate_meta,
    validate_observation,
)


def feature(value: Any, unit: str | None = None, available_at_ns: int | None = None) -> Feature:
    """Describe one pipeline value without exposing the wire schema."""
    return Feature(value, unit, available_at_ns)


class TraceRecorder:
    """Append observations to a new trace; use as a context manager.

    Every record is validated with the same rules ``read_jsonl`` applies before anything is
    written, so a trace this class produces is always readable. Invalid input raises
    ``TraceValidationError`` and leaves the file unchanged.
    """

    def __init__(self, path: Path | str, meta: RunMeta) -> None:
        validate_meta(meta)
        self._path = Path(path)
        self._handle: TextIO | None = None
        self._meta = meta
        self._observations = 0
        self._bytes = 0

    def __enter__(self) -> Self:
        if self._path.exists():
            raise FileExistsError(f"trace already exists: {self._path}")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self._path.open("x", encoding="utf-8")
        self._write({"record_type": "run", **self._meta.__dict__})
        return self

    def __exit__(self, *_: object) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def record(self, event_id: str, stage: str, *, sequence: int | None = None,
               source: str | None = None, event_ts_ns: int | None = None,
               input_hash: str | None = None, features: Mapping[str, Feature | Any] | None = None,
               model_score: Any = None, decision: Any = None, decision_ts_ns: int | None = None,
               state_hash: str | None = None) -> None:
        if self._handle is None:
            raise RuntimeError("use TraceRecorder as a context manager")
        wrapped = {name: value if isinstance(value, Feature) else feature(value)
                   for name, value in (features or {}).items()}
        validate_observation(Observation(event_id, stage, sequence, source, event_ts_ns, input_hash, wrapped,
                                         model_score, decision, decision_ts_ns, state_hash))
        if self._observations >= MAX_RECORDS:
            raise TraceValidationError(f"trace exceeds {MAX_RECORDS} observations")
        event = {"id": event_id, "sequence": sequence, "source": source,
                 "event_ts_ns": event_ts_ns, "input_hash": input_hash}
        values = {name: {"value": f.value, "unit": f.unit, "available_at_ns": f.available_at_ns}
                  for name, f in wrapped.items()}
        self._write({"record_type": "observation", "event": event, "stage": stage, "features": values,
                     "model_score": model_score, "decision": decision, "decision_ts_ns": decision_ts_ns,
                     "state_hash": state_hash})
        self._observations += 1

    def _write(self, row: dict[str, Any]) -> None:
        assert self._handle is not None
        try:
            encoded = json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n"
        except (TypeError, ValueError) as exc:  # unreachable after validation; kept as a guard
            raise TraceValidationError("trace values must be JSON-serializable and finite") from exc
        if len(encoded) > MAX_LINE_BYTES:
            raise TraceValidationError(f"record larger than {MAX_LINE_BYTES} bytes")
        if self._bytes + len(encoded) > MAX_BYTES:
            raise TraceValidationError(f"trace larger than {MAX_BYTES} bytes")
        self._handle.write(encoded)
        self._handle.flush()
        self._bytes += len(encoded)

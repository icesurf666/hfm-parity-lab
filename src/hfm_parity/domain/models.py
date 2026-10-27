"""Framework-free trace and finding models."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from dataclasses import field as dc_field
from enum import StrEnum
from math import isfinite
from typing import Any


class ResultState(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_COMPARABLE = "NOT_COMPARABLE"
    UNVERIFIABLE = "UNVERIFIABLE"
    ERROR = "ERROR"


class ComparisonMode(StrEnum):
    STRICT = "strict"
    REGRESSION = "regression"


class Classification(StrEnum):
    TRACE_INVALID = "TRACE_INVALID"
    EVENT_MISMATCH = "EVENT_MISMATCH"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    FEATURE_MISSING = "FEATURE_MISSING"
    FEATURE_TYPE_MISMATCH = "FEATURE_TYPE_MISMATCH"
    FEATURE_VALUE_MISMATCH = "FEATURE_VALUE_MISMATCH"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    TIMESTAMP_MISMATCH = "TIMESTAMP_MISMATCH"
    CAUSALITY_VIOLATION = "CAUSALITY_VIOLATION"
    CONFIG_MISMATCH = "CONFIG_MISMATCH"
    MODEL_VERSION_MISMATCH = "MODEL_VERSION_MISMATCH"
    MODEL_SCORE_MISMATCH = "MODEL_SCORE_MISMATCH"
    DECISION_MISMATCH = "DECISION_MISMATCH"
    STATE_MISMATCH = "STATE_MISMATCH"
    INPUT_MISMATCH = "INPUT_MISMATCH"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass(frozen=True)
class RunMeta:
    run_id: str
    schema_version: str
    pipeline_version: str
    feature_schema_hash: str
    config_hash: str
    clock_domain: str
    model_version: str | None = None
    venue: str | None = None
    symbol: str | None = None
    data_source: str | None = None


@dataclass(frozen=True)
class Feature:
    value: Any
    unit: str | None = None
    available_at_ns: int | None = None


@dataclass(frozen=True)
class Observation:
    event_id: str
    stage: str
    sequence: int | None = None
    source: str | None = None
    event_ts_ns: int | None = None
    input_hash: str | None = None
    features: dict[str, Feature] = dc_field(default_factory=dict)
    model_score: Any = None
    decision: Any = None
    decision_ts_ns: int | None = None
    state_hash: str | None = None
    line: int = 0

    @property
    def key(self) -> tuple[str, str]:
        return self.event_id, self.stage


@dataclass(frozen=True)
class Trace:
    meta: RunMeta
    observations: tuple[Observation, ...]


@dataclass(frozen=True)
class CompareConfig:
    absolute_tolerance: float = 0.0
    relative_tolerance: float = 0.0
    mode: ComparisonMode = ComparisonMode.STRICT

    def __post_init__(self) -> None:
        if not all(isfinite(item) and item >= 0 for item in (self.absolute_tolerance, self.relative_tolerance)):
            raise ValueError("tolerances must be finite non-negative numbers")


@dataclass(frozen=True)
class Finding:
    classification: Classification
    message: str
    event_id: str | None = None
    stage: str | None = None
    field: str | None = None
    baseline: Any = None
    candidate: Any = None
    severity: str = "error"
    evidence: dict[str, Any] = dc_field(default_factory=dict)


@dataclass(frozen=True)
class ComparisonReport:
    state: ResultState
    mode: ComparisonMode
    baseline_run_id: str
    candidate_run_id: str
    findings: tuple[Finding, ...]
    aligned_events: int

    @property
    def first_divergence(self) -> Finding | None:
        """The earliest observed difference at an event; if there is none (or the runs are not
        comparable), the first finding, which is then a run-level contract or evidence gap."""
        if self.state is not ResultState.NOT_COMPARABLE:
            for finding in self.findings:
                if finding.event_id is not None and finding.severity == "error":
                    return finding
        for finding in self.findings:
            if finding.classification is not Classification.INSUFFICIENT_EVIDENCE:
                return finding
        return self.findings[0] if self.findings else None

    @property
    def deterministic_parity_verified(self) -> bool:
        return self.mode is ComparisonMode.STRICT and self.state is ResultState.PASS

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["state"] = self.state.value
        data["mode"] = self.mode.value
        data["deterministic_parity_verified"] = self.deterministic_parity_verified
        data["findings"] = [
            {**asdict(item), "classification": item.classification.value}
            for item in self.findings
        ]
        first = self.first_divergence
        data["first_divergence"] = None if first is None else data["findings"][self.findings.index(first)]
        return data

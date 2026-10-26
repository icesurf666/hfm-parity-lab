"""Plain-language notes and small selectors shared by the MCP evidence service."""
from __future__ import annotations

from hfm_parity.domain.checks import has_output
from hfm_parity.domain.models import (
    ComparisonMode,
    ComparisonReport,
    Observation,
    Trace,
)

MAX_CONTEXT = 4
CAUSE_NOTE = "Findings are recorded differences; no source code was inspected, so no cause is established."


MEANING = {
    "PASS": "No recorded difference under the chosen mode.",
    "FAIL": "At least one recorded difference was found between aligned events.",
    "NOT_COMPARABLE": "Run contracts (config, model, schema, input or clock) differ; no parity claim is possible.",
    "UNVERIFIABLE": "The traces lack evidence needed for a conclusion.",
    "ERROR": "The comparison could not complete.",
}


def coverage_gaps(trace: Trace) -> list[str]:
    no_ts = sum(item.decision_ts_ns is None for item in trace.observations)
    no_hash = sum(item.input_hash is None for item in trace.observations)
    scored = any(item.model_score is not None for item in trace.observations)
    no_avail = sum(any(f.available_at_ns is None for f in item.features.values()) for item in trace.observations)
    gaps = []
    if no_ts:
        gaps.append(f"{no_ts} observation(s) lack decision_ts_ns; causality cannot be checked.")
    if no_avail:
        gaps.append(f"{no_avail} observation(s) have features without available_at_ns.")
    if no_hash:
        gaps.append(f"{no_hash} observation(s) lack input_hash; identical inputs cannot be shown.")
    if trace.meta.data_source is None:
        gaps.append("data_source is not declared; strict parity needs the origin of the input data.")
    if scored and trace.meta.model_version is None:
        gaps.append("model scores are recorded but model_version is absent.")
    if trace.observations and not any(has_output(item) for item in trace.observations):
        gaps.append("no features, score, decision or state are recorded; there is nothing to compare.")
    return gaps


def limitations(report: ComparisonReport) -> list[str]:
    notes = [CAUSE_NOTE]
    if report.mode is ComparisonMode.REGRESSION:
        notes.append("Regression mode never verifies deterministic parity.")
    if report.state.value == "UNVERIFIABLE":
        notes.append("Evidence is missing: this is neither a pass nor a failure. See summary.unverifiable.")
    elif report.state.value == "NOT_COMPARABLE":
        notes.append("The runs' contracts differ; the evidence cannot support a verified parity conclusion.")
    return notes


def steps(report: ComparisonReport) -> list[str]:
    first = report.first_divergence
    if report.state.value == "UNVERIFIABLE":
        return ["Record the evidence listed in summary.unverifiable (see references/instrumentation.md), then compare again."]
    if first is None:
        return ["No recorded mismatch; confirm trace coverage before ruling out a defect."]
    if report.state.value == "NOT_COMPARABLE":
        return ["Resolve the run-contract differences (or use regression mode deliberately) before inspecting values."]
    target = f"event {first.event_id} stage {first.stage}" if first.event_id else "the run metadata"
    return [f"Call inspect_event for {target}." if first.event_id else f"Review {target}.",
            "Read the implementation of the differing field before naming a cause."]


def matching(trace: Trace, event_id: str, stage: str | None) -> list[Observation]:
    return [o for o in trace.observations if o.event_id == event_id and (stage is None or o.stage == stage)]


def first(items: list[Observation]) -> Observation | None:
    return items[0] if items else None


def nearby(baseline: Trace, candidate: Trace, event_id: str, count: int) -> dict[str, list[str]]:
    count = max(0, min(count, MAX_CONTEXT))
    result = {}
    for name, trace in (("baseline", baseline), ("candidate", candidate)):
        ids = list(dict.fromkeys(o.event_id for o in trace.observations))
        at = ids.index(event_id) if event_id in ids else 0
        result[name] = ids[max(0, at - count):at + count + 1]
    return result

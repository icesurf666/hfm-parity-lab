"""Bounded JSON-ready views of existing domain records; no comparison logic lives here.

Size contract: ``fit`` guarantees the pretty-printed JSON of a result (the form the SDK sends as text
content, next to the more compact structured copy) stays within ``RESPONSE_BUDGET`` bytes.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, TypedDict

from hfm_parity.domain.models import Classification, Finding, Observation

MAX_TEXT = 1024
MAX_ITEMS = 20
MAX_DEPTH = 4
MAX_COUNT_KEYS = 64
RESPONSE_BUDGET = 56 * 1024
PROFILES = ((8, 256, 3), (4, 128, 2), (2, 64, 1))  # (items, characters, depth), tried in order

_KIND = {Classification.CAUSALITY_VIOLATION: "verified_invariant_violation",
         Classification.INSUFFICIENT_EVIDENCE: "missing_evidence"}


class ToolResponse(TypedDict):
    """Uniform result shape of every tool."""

    status: str
    verdict: str | None
    summary: dict[str, Any]
    findings: list[dict[str, Any]]
    evidence: dict[str, Any] | None
    limitations: list[str]
    next_steps: list[str]
    truncation: list[str]


def reply(*, verdict: str | None = None, summary: dict[str, Any] | None = None,
          findings: list[dict[str, Any]] | None = None, evidence: dict[str, Any] | None = None,
          limitations: list[str] | None = None, next_steps: list[str] | None = None) -> ToolResponse:
    return {"status": "ok", "verdict": verdict, "summary": summary or {}, "findings": findings or [],
            "evidence": evidence, "limitations": limitations or [], "next_steps": next_steps or [], "truncation": []}


def bound(value: Any, items: int = MAX_ITEMS, chars: int = MAX_TEXT, depth: int = MAX_DEPTH) -> Any:
    """Shorten strings, mappings and sequences; containers nested deeper than ``depth`` become a marker."""
    if isinstance(value, str):
        return value[:chars] + ("…" if len(value) > chars else "")
    if isinstance(value, (dict, list, tuple)):
        if depth <= 0:
            return f"<{'object' if isinstance(value, dict) else 'list'} of {len(value)} items omitted>"
        if isinstance(value, dict):
            return {str(k)[:chars]: bound(v, items, chars, depth - 1) for k, v in list(value.items())[:items]}
        return [bound(v, items, chars, depth - 1) for v in value[:items]]
    return value


def size(response: ToolResponse) -> int:
    return len(json.dumps(response, indent=2, ensure_ascii=False).encode())


def fit(response: ToolResponse, budget: int = RESPONSE_BUDGET) -> ToolResponse:
    """Return ``response`` unchanged if it fits, otherwise a deterministic, explicitly marked reduction."""
    if size(response) <= budget:
        return response
    total = len(response["findings"])
    notes: list[str] = []
    for items, chars, depth in PROFILES:
        shrunk = _rebound(response, items, chars, depth)
        notes = [f"values shortened to at most {chars} characters, {items} items and {depth} nesting levels"]
        if size({**shrunk, "truncation": notes}) <= budget:
            return {**shrunk, "truncation": notes}
    shrunk = _rebound(response, *PROFILES[-1])
    while len(shrunk["findings"]) > 1 and size({**shrunk, "truncation": notes}) > budget:
        shrunk["findings"] = shrunk["findings"][:-1]
    if size({**shrunk, "truncation": notes}) > budget:
        shrunk["evidence"] = None
        notes.append("evidence omitted; call inspect_event for a single event")
    if size({**shrunk, "truncation": notes}) > budget:
        shrunk["findings"], shrunk["summary"] = [], _scalars(shrunk["summary"])
        notes.append("findings omitted")
    if len(shrunk["findings"]) < total:
        notes.append(f"returned {len(shrunk['findings'])} of {total} findings in report order")
    return {**shrunk, "truncation": notes}


def _rebound(response: ToolResponse, items: int, chars: int, depth: int) -> ToolResponse:
    deeper = depth + 1  # the top-level container itself is not a nesting level
    return {**response, "summary": _summary(response["summary"], items, chars, deeper),
            "findings": bound(response["findings"], items, chars, deeper),
            "evidence": bound(response["evidence"], items, chars, deeper)}


def _summary(summary: dict[str, Any], items: int, chars: int, depth: int) -> dict[str, Any]:
    """Counts are the accurate totals the caller relies on: keep scalars and count tables whole."""
    return {key: value if _is_count(value) else bound(value, items, chars, depth) for key, value in summary.items()}


def _is_count(value: Any) -> bool:
    if isinstance(value, dict):
        return len(value) <= MAX_COUNT_KEYS and all(isinstance(v, int) and len(str(k)) <= 64 for k, v in value.items())
    return isinstance(value, (bool, int, float)) or value is None or (isinstance(value, str) and len(value) <= 64)


def _scalars(summary: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in summary.items() if isinstance(v, (bool, int, float)) or (isinstance(v, str) and len(v) <= 64)}


def finding_view(item: Finding) -> dict[str, Any]:
    data = asdict(item)
    data["classification"] = item.classification.value
    data["evidence_kind"] = _KIND.get(item.classification, "observed_mismatch")
    return dict(bound(data))


def observation_view(item: Observation) -> dict[str, Any]:
    data = asdict(item)
    data.pop("line")
    return dict(bound(data))


def feature_differences(left: Observation | None, right: Observation | None) -> list[dict[str, Any]]:
    """Side-by-side recorded features; equality here is exact, tolerance verdicts stay in the report."""
    a, b = (left.features if left else {}), (right.features if right else {})
    rows = []
    for name in sorted(set(a) | set(b)):
        rows.append({"feature": name, "baseline": asdict(a[name]) if name in a else None,
                     "candidate": asdict(b[name]) if name in b else None, "identical": a.get(name) == b.get(name)})
    return list(bound(rows))

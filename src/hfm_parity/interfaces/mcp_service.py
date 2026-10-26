"""Read-only, stateless evidence operations behind the MCP tools.

Parsing is ``read_jsonl`` and every verdict comes from ``compare_runs``; this
module only resolves paths, aggregates and bounds what those already decided.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from pathlib import Path

from hfm_parity.adapters.jsonl import TraceValidationError, read_jsonl
from hfm_parity.application.compare import compare_runs
from hfm_parity.application.summary import summarize_report
from hfm_parity.domain.models import (
    Classification,
    CompareConfig,
    ComparisonMode,
    ComparisonReport,
    Trace,
)
from hfm_parity.interfaces.mcp_notes import (
    CAUSE_NOTE,
    MEANING,
    coverage_gaps,
    first,
    limitations,
    matching,
    nearby,
    steps,
)
from hfm_parity.interfaces.mcp_paths import ToolFailure, resolve_trace
from hfm_parity.interfaces.mcp_views import (
    MAX_ITEMS,
    ToolResponse,
    bound,
    feature_differences,
    finding_view,
    observation_view,
    reply,
)


class EvidenceService:
    """Never executes a traced pipeline and never writes."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def validate(self, trace_path: str) -> ToolResponse:
        path = resolve_trace(self.root, trace_path)
        try:
            trace = read_jsonl(path)
        except TraceValidationError as exc:
            problem = {"classification": "TRACE_INVALID", "message": _clean(exc, path)}
            return reply(verdict="INVALID", summary={"valid": False, "strict_comparison_possible": False},
                         findings=[problem], limitations=["Trace failed the shared parser; nothing was compared."])
        keys = Counter(item.key for item in trace.observations)
        duplicates = sorted(f"{event}/{stage}" for (event, stage), n in keys.items() if n > 1)
        gaps = coverage_gaps(trace)
        findings = [{"classification": "DUPLICATE_EVENT_STAGE", "message": name} for name in duplicates[:MAX_ITEMS]]
        findings += [{"classification": "COVERAGE_GAP", "message": text} for text in gaps]
        meta = asdict(trace.meta)
        possible = bool(trace.observations) and not duplicates and not gaps
        return reply(verdict="VALID", summary={
            "valid": True, "run_id": trace.meta.run_id, "observations": len(trace.observations),
            "events": len({item.event_id for item in trace.observations}),
            "stages": dict(sorted(Counter(item.stage for item in trace.observations).items())),
            "metadata": meta, "missing_optional_metadata": sorted(k for k, v in meta.items() if v is None),
            "strict_comparison_possible": possible, "duplicate_keys": len(duplicates),
            "strict_verification_gaps": len(gaps)},
            findings=bound(findings), limitations=[
                "Structural validity does not establish causal correctness.",
                "Strict comparison also needs matching metadata, identity and event ids in the other trace."],
            next_steps=["Compare with compare_traces."] if possible else
                       ["Fix the listed findings (unique event/stage keys, missing evidence) before a strict comparison."])

    def compare(self, baseline_path: str, candidate_path: str, mode: str = "strict",
                max_findings: int = MAX_ITEMS) -> ToolResponse:
        baseline, candidate, report = self._report(baseline_path, candidate_path, mode)
        limit = max(1, min(max_findings, MAX_ITEMS))
        first = report.first_divergence
        keys = {item.key for item in baseline.observations}, {item.key for item in candidate.observations}
        summary = summarize_report(report)
        shown = [finding_view(item) for item in report.findings[:limit]]
        unverifiable = [f.message for f in report.findings if f.classification is Classification.INSUFFICIENT_EVIDENCE]
        return reply(verdict=report.state.value, summary={
            "mode": report.mode.value, "deterministic_parity_verified": report.deterministic_parity_verified,
            "comparable_events": report.aligned_events, "matched_event_keys": len(keys[0] & keys[1]),
            "unmatched_event_keys": len(keys[0] ^ keys[1]), "total_findings": summary["total_findings"],
            "findings_by_category": summary["by_category"], "returned_findings": len(shown),
            "truncated": len(shown) < len(report.findings),
            "first_divergence": finding_view(first) if first else None,
            "unverifiable": sorted(set(unverifiable))[:MAX_ITEMS]},
            findings=shown, evidence=shown[0] if shown else None,
            limitations=limitations(report), next_steps=steps(report))

    def summarize(self, baseline_path: str, candidate_path: str, mode: str = "strict",
                  top: int = 5) -> ToolResponse:
        _, _, report = self._report(baseline_path, candidate_path, mode)
        summary = summarize_report(report, max(1, min(top, MAX_ITEMS)))
        summary.update(mode=report.mode.value, verdict_meaning=MEANING[report.state.value],
                       deterministic_parity_verified=report.deterministic_parity_verified)
        first = report.first_divergence
        return reply(verdict=report.state.value, summary=summary,
                     findings=[finding_view(first)] if first else [], limitations=limitations(report),
                     next_steps=steps(report))

    def inspect(self, baseline_path: str, candidate_path: str, event_id: str, stage: str | None = None,
                context: int = 1, mode: str = "strict") -> ToolResponse:
        if not event_id or len(event_id) > 1024:
            raise ToolFailure("INVALID_ARGUMENT", "event_id must be a non-empty string of at most 1024 characters.")
        baseline, candidate, report = self._report(baseline_path, candidate_path, mode)
        left, right = matching(baseline, event_id, stage), matching(candidate, event_id, stage)
        if not left and not right:
            raise ToolFailure("EVENT_NOT_FOUND", "No stored observation matches the requested event and stage.")
        chosen = stage or (left or right)[0].stage
        a, b = first(left), first(right)
        found = [f for f in report.findings if f.event_id == event_id and f.stage == chosen]
        missing = [name for name, side in (("baseline", a), ("candidate", b)) if side is None]
        other = sorted({o.stage for t in (baseline, candidate) for o in t.observations
                        if o.event_id == event_id and o.stage != chosen})
        return reply(verdict=report.state.value, summary={
            "event_id": event_id, "stage": chosen, "baseline_matches": len(left),
            "candidate_matches": len(right), "ambiguous": len(left) > 1 or len(right) > 1,
            "diagnostic_classes": sorted({f.classification.value for f in found}),
            "total_event_findings": len(found)},
            findings=[finding_view(f) for f in found[:MAX_ITEMS]],
            evidence={
                "baseline": observation_view(a) if a else None, "candidate": observation_view(b) if b else None,
                "feature_differences": feature_differences(a, b),
                "decision": {"baseline": a.decision if a else None, "candidate": b.decision if b else None,
                             "identical": bool(a and b and a.decision == b.decision)},
                "run_metadata": {"baseline": bound(asdict(baseline.meta)), "candidate": bound(asdict(candidate.meta))},
                "other_stages": other[:MAX_ITEMS],
                "neighbouring_events": nearby(baseline, candidate, event_id, context),
                "missing_information": [f"no {name} observation for this event/stage" for name in missing]},
            limitations=[CAUSE_NOTE], next_steps=["Read the code that computes the differing field on each side."])

    def _report(self, baseline_path: str, candidate_path: str,
                mode: str) -> tuple[Trace, Trace, ComparisonReport]:
        try:
            config = CompareConfig(mode=ComparisonMode(mode))
        except ValueError as exc:
            raise ToolFailure("INVALID_ARGUMENT", "mode must be 'strict' or 'regression'.") from exc
        baseline, candidate = self._trace(baseline_path), self._trace(candidate_path)
        return baseline, candidate, compare_runs(baseline, candidate, config)

    def _trace(self, requested: str) -> Trace:
        path = resolve_trace(self.root, requested)
        try:
            return read_jsonl(path)
        except TraceValidationError as exc:
            raise ToolFailure("TRACE_INVALID", f"Trace failed validation: {_clean(exc, path)}") from exc
        except OSError as exc:
            raise ToolFailure("TRACE_UNREADABLE", "Trace could not be read.") from exc


def _clean(exc: Exception, path: Path) -> str:
    """Parser messages may embed the absolute path; the client only sees a placeholder."""
    return str(exc).replace(str(path), "<trace>").replace(str(path.parent), "<root>")[:300]

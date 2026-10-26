"""Application service: compare two recorded runs.

Report order is deterministic: run-level findings first, then event-level findings by the
chronological position of their event (see ``domain.align``). Verdict severity never reorders findings.
"""
from __future__ import annotations

from hfm_parity.domain.align import index, order_findings, positions
from hfm_parity.domain.checks import has_output, metadata, observation
from hfm_parity.domain.models import (
    Classification,
    CompareConfig,
    ComparisonMode,
    ComparisonReport,
    Finding,
    ResultState,
    Trace,
)


def compare_runs(baseline: Trace, candidate: Trace, config: CompareConfig | None = None) -> ComparisonReport:
    config = config or CompareConfig()
    strict = config.mode is ComparisonMode.STRICT
    uses_model = any(o.model_score is not None for trace in (baseline, candidate) for o in trace.observations)
    run_findings = metadata(baseline.meta, candidate.meta, strict, uses_model)
    left, left_findings, left_ambiguous = index(baseline.observations)
    right, right_findings, right_ambiguous = index(candidate.observations)
    ambiguous = left_ambiguous | right_ambiguous
    rank = positions(baseline.observations, candidate.observations)
    events = left_findings + right_findings + order_findings(baseline.observations, candidate.observations, ambiguous)
    clocks_match = baseline.meta.clock_domain == candidate.meta.clock_domain
    aligned, outputs, unfingerprinted = 0, 0, []
    for key in sorted(rank, key=rank.__getitem__):
        a, b = left.get(key), right.get(key)
        if key in ambiguous:
            events.append(Finding(Classification.INSUFFICIENT_EVIDENCE,
                                  "duplicate event/stage prevents field comparison", *key, severity="warning"))
        elif a is None or b is None:
            events.append(Finding(Classification.EVENT_MISMATCH, "event/stage missing from one trace", *key,
                                  baseline=a is not None, candidate=b is not None))
        else:
            aligned += 1
            outputs += has_output(a) or has_output(b)
            if a.input_hash is None or b.input_hash is None:
                unfingerprinted.append(key)
            events.extend(observation(a, b, config, clocks_match))
    if strict and unfingerprinted:
        events.append(Finding(Classification.INSUFFICIENT_EVIDENCE,
                              f"input_hash is absent on {len(unfingerprinted)} aligned observation(s); "
                              "inputs cannot be shown identical", *unfingerprinted[0], field="input_hash",
                              severity="warning", evidence={"count": len(unfingerprinted)}))
    if not baseline.observations or not candidate.observations:
        run_findings.append(Finding(Classification.INSUFFICIENT_EVIDENCE,
                                    "one or both traces contain no observations",
                                    field="observations", severity="warning"))
    elif strict and aligned and not outputs:
        run_findings.append(Finding(Classification.INSUFFICIENT_EVIDENCE,
                                    "no features, score, decision or state were recorded on any aligned event",
                                    field="outputs", severity="warning"))
    events.sort(key=lambda finding: rank.get((finding.event_id or "", finding.stage or ""), -1))
    findings = run_findings + events
    return ComparisonReport(_state(findings, config), config.mode, baseline.meta.run_id,
                            candidate.meta.run_id, tuple(findings), aligned)


def _state(findings: list[Finding], config: CompareConfig) -> ResultState:
    """Precedence: NOT_COMPARABLE (strict contract broken) > FAIL (observed difference) > UNVERIFIABLE."""
    if not findings:
        return ResultState.PASS
    categories = {finding.classification for finding in findings}
    incompatible = {
        Classification.CONFIG_MISMATCH,
        Classification.MODEL_VERSION_MISMATCH,
        Classification.SCHEMA_MISMATCH,
        Classification.INPUT_MISMATCH,
    }
    if config.mode is ComparisonMode.STRICT and categories & incompatible:
        return ResultState.NOT_COMPARABLE
    if Classification.TIMESTAMP_MISMATCH in categories and baseline_clock_mismatch(findings):
        return ResultState.NOT_COMPARABLE
    if categories == {Classification.INSUFFICIENT_EVIDENCE}:
        return ResultState.UNVERIFIABLE
    return ResultState.FAIL


def baseline_clock_mismatch(findings: list[Finding]) -> bool:
    return any(item.field == "clock_domain" for item in findings)

"""Pure observation and metadata checks."""
from __future__ import annotations

from hfm_parity.domain.models import Classification, CompareConfig, Finding, Observation, RunMeta
from hfm_parity.domain.values import delta, difference

IDENTITY = ("symbol", "venue", "data_source")


def metadata(left: RunMeta, right: RunMeta, strict: bool = True, uses_model: bool = False) -> list[Finding]:
    """Run-level compatibility. Only ``strict`` also reports evidence that is missing."""
    fields = ("schema_version", "pipeline_version", "feature_schema_hash", "config_hash", "model_version")
    findings: list[Finding] = []
    for field in fields:
        a, b = getattr(left, field), getattr(right, field)
        if a != b:
            if field == "model_version":
                category = Classification.MODEL_VERSION_MISMATCH
            elif field in {"schema_version", "feature_schema_hash"}:
                category = Classification.SCHEMA_MISMATCH
            else:
                category = Classification.CONFIG_MISMATCH
            findings.append(Finding(category, f"run metadata differs: {field}", field=field, baseline=a, candidate=b))
    for field in IDENTITY:
        a, b = getattr(left, field), getattr(right, field)
        if a is not None and b is not None and a != b:
            findings.append(Finding(Classification.INPUT_MISMATCH, f"run identity differs: {field}",
                                    field=field, baseline=a, candidate=b))
    if strict:
        findings.extend(_missing_metadata(left, right, uses_model))
    if left.clock_domain != right.clock_domain:
        findings.append(Finding(Classification.TIMESTAMP_MISMATCH,
                                "clock domains differ; timestamps are not comparable",
                                field="clock_domain", baseline=left.clock_domain,
                                candidate=right.clock_domain, severity="warning"))
    return findings


def _missing_metadata(left: RunMeta, right: RunMeta, uses_model: bool) -> list[Finding]:
    """Strict parity needs declared input provenance and, if a model score is recorded, model identity."""
    needed = ["data_source"] + [f for f in ("symbol", "venue") if (getattr(left, f) is None) != (getattr(right, f) is None)]
    if uses_model and left.model_version is None and right.model_version is None:
        needed.append("model_version")
    findings = []
    for field in needed:
        gaps = [side for side, meta in (("baseline", left), ("candidate", right)) if getattr(meta, field) is None]
        if gaps:
            findings.append(Finding(Classification.INSUFFICIENT_EVIDENCE,
                                    f"{field} is not declared by the {' and '.join(gaps)} run; "
                                    "strict parity cannot be verified", field=field, severity="warning"))
    return findings


def observation(left: Observation, right: Observation, config: CompareConfig,
                timestamps_comparable: bool) -> list[Finding]:
    findings: list[Finding] = []
    if _differs(left.source, right.source) or _differs(left.input_hash, right.input_hash):
        findings.append(Finding(Classification.INPUT_MISMATCH,
                                "event source or input fingerprint differs", left.event_id, left.stage,
                                evidence={"baseline_source": left.source, "candidate_source": right.source,
                                          "baseline_input_hash": left.input_hash,
                                          "candidate_input_hash": right.input_hash}))
        return findings
    if left.sequence != right.sequence:
        findings.append(Finding(Classification.EVENT_MISMATCH, "event sequence differs",
                                left.event_id, left.stage, "sequence", left.sequence, right.sequence))
    if timestamps_comparable:
        for field in ("event_ts_ns", "decision_ts_ns"):
            a, b = getattr(left, field), getattr(right, field)
            if a != b:
                findings.append(Finding(Classification.TIMESTAMP_MISMATCH,
                                        f"{field} differs", left.event_id, left.stage,
                                        field, a, b))
    for name in sorted(set(left.features) | set(right.features)):
        a, b = left.features.get(name), right.features.get(name)
        if a is None or b is None:
            findings.append(Finding(Classification.FEATURE_MISSING, "feature missing", left.event_id, left.stage, name, a is not None, b is not None))
            continue
        if a.unit != b.unit:
            findings.append(Finding(Classification.UNIT_MISMATCH, "feature units differ", left.event_id, left.stage, name, a.unit, b.unit))
        else:
            mismatch = difference(a.value, b.value, config.absolute_tolerance, config.relative_tolerance, name)
            if mismatch is not None:
                category = (Classification.FEATURE_TYPE_MISMATCH if mismatch.baseline_type != mismatch.candidate_type else Classification.FEATURE_VALUE_MISMATCH)
                evidence = {"baseline_type": mismatch.baseline_type, "candidate_type": mismatch.candidate_type, "baseline_present": mismatch.baseline_present, "candidate_present": mismatch.candidate_present, "absolute_tolerance": config.absolute_tolerance, "relative_tolerance": config.relative_tolerance}
                if category is Classification.FEATURE_VALUE_MISMATCH:
                    evidence["delta"] = delta(mismatch.baseline, mismatch.candidate)
                findings.append(Finding(category, "feature values differ" if category is Classification.FEATURE_VALUE_MISMATCH else "feature value types differ", left.event_id, left.stage, mismatch.path, mismatch.baseline, mismatch.candidate, evidence=evidence))
    for field, category in (("model_score", Classification.MODEL_SCORE_MISMATCH), ("decision", Classification.DECISION_MISMATCH), ("state_hash", Classification.STATE_MISMATCH)):
        a, b = getattr(left, field), getattr(right, field)
        mismatch = difference(a, b, config.absolute_tolerance, config.relative_tolerance, field)
        if mismatch is not None:
            findings.append(Finding(category, f"{field} differs", left.event_id, left.stage, mismatch.path, mismatch.baseline, mismatch.candidate, evidence={"baseline_type": mismatch.baseline_type, "candidate_type": mismatch.candidate_type, "baseline_present": mismatch.baseline_present, "candidate_present": mismatch.candidate_present}))
    if timestamps_comparable:
        findings.extend(causality(left))
        findings.extend(causality(right, side="candidate"))
    return findings


def _differs(a: object, b: object) -> bool:
    """Absent values are missing evidence, handled elsewhere, not a known difference."""
    return a is not None and b is not None and a != b


def has_output(item: Observation) -> bool:
    return bool(item.features) or any(v is not None for v in (item.model_score, item.decision, item.state_hash))


def causality(item: Observation, side: str = "baseline") -> list[Finding]:
    if item.decision_ts_ns is None:
        return [Finding(Classification.INSUFFICIENT_EVIDENCE, "decision timestamp is absent", item.event_id, item.stage, severity="warning", evidence={"side": side})]
    late = [name for name, feature in item.features.items() if feature.available_at_ns is None or feature.available_at_ns > item.decision_ts_ns]
    if not late:
        return []
    category = Classification.CAUSALITY_VIOLATION if any(item.features[name].available_at_ns is not None for name in late) else Classification.INSUFFICIENT_EVIDENCE
    return [Finding(category, "feature availability is after decision or absent", item.event_id, item.stage, ",".join(late), severity="error" if category == Classification.CAUSALITY_VIOLATION else "warning", evidence={"side": side})]

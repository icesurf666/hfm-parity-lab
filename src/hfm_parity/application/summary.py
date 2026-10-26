"""Compact, deterministic aggregation of a finished comparison report."""
from __future__ import annotations

from collections import Counter
from typing import Any

from hfm_parity.domain.models import ComparisonReport


def summarize_report(report: ComparisonReport, earliest: int = 5) -> dict[str, Any]:
    """Group every finding (not only a returned page) in stable report order."""
    findings = report.findings
    keys = list(dict.fromkeys((f.event_id, f.stage) for f in findings if f.event_id))
    return {
        "total_findings": len(findings),
        "affected_events": len({event_id for event_id, _ in keys}),
        "affected_event_stages": len(keys),
        "by_category": _counts(f.classification.value for f in findings),
        "by_stage": _counts(f.stage or "<run>" for f in findings),
        "by_field": _counts(f.field or "<none>" for f in findings),
        "earliest_events": [{"event_id": event_id, "stage": stage} for event_id, stage in keys[:earliest]],
    }


def _counts(values: Any) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))

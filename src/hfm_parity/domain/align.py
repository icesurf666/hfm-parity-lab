"""Exact event/stage alignment and event order; fuzzy matching is intentionally absent.

Order contract: record order in a trace is authoritative. Within each stage, the aligned events
must appear in the same order in both traces; interleaving of different stages is not compared.
"""
from __future__ import annotations

from hfm_parity.domain.models import Classification, Finding, Observation

Key = tuple[str, str]


def index(observations: tuple[Observation, ...]) -> tuple[dict[Key, Observation], list[Finding], set[Key]]:
    indexed: dict[Key, Observation] = {}
    findings: list[Finding] = []
    ambiguous: set[Key] = set()
    last_sequence: int | None = None
    for observation in observations:
        if observation.key in indexed:
            findings.append(Finding(Classification.EVENT_MISMATCH, "duplicate event/stage key",
                                    observation.event_id, observation.stage, severity="error"))
            ambiguous.add(observation.key)
        else:
            indexed[observation.key] = observation
        if observation.sequence is not None and last_sequence is not None and observation.sequence < last_sequence:
            findings.append(Finding(Classification.EVENT_MISMATCH, "sequence order decreased",
                                    observation.event_id, observation.stage, "sequence",
                                    last_sequence, observation.sequence))
        if observation.sequence is not None:
            last_sequence = observation.sequence
    return indexed, findings, ambiguous


def positions(*traces: tuple[Observation, ...]) -> dict[Key, int]:
    """Chronological rank of every key: baseline record order, then keys only the candidate has."""
    rank: dict[Key, int] = {}
    for observations in traces:
        for observation in observations:
            rank.setdefault(observation.key, len(rank))
    return rank


def order_findings(left: tuple[Observation, ...], right: tuple[Observation, ...],
                   ambiguous: set[Key]) -> list[Finding]:
    """One finding per stage whose aligned events appear in a different order."""
    shared = {o.key for o in left} & {o.key for o in right} - ambiguous
    findings: list[Finding] = []
    sides = [_by_stage(observations, shared) for observations in (left, right)]
    for stage in sorted(sides[0]):
        a, b = sides[0][stage], sides[1].get(stage, [])
        if a != b:
            at = next(i for i, (x, y) in enumerate(zip(a, b, strict=False)) if x != y)
            findings.append(Finding(Classification.EVENT_MISMATCH, "event order differs within stage",
                                    a[at], stage, "order", a[at], b[at]))
    return findings


def _by_stage(observations: tuple[Observation, ...], shared: set[Key]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for observation in observations:
        if observation.key in shared:
            grouped.setdefault(observation.stage, []).append(observation.event_id)
    return grouped

"""F3/F4: what a strict verified PASS requires, and which verdict each gap produces."""
from __future__ import annotations

from typing import Any

import pytest
from builders import feat, meta, obs, run


def strict(left: list[Any] | None = None, right: list[Any] | None = None, **kw: Any) -> Any:
    return run(left if left is not None else [obs()], right if right is not None else [obs()], **kw)


def test_complete_evidence_is_verified() -> None:
    report = strict()
    assert report.state.value == "PASS" and report.deterministic_parity_verified


@pytest.mark.parametrize("field", ["symbol", "venue", "data_source"])
def test_differing_identity_is_not_comparable(field: str) -> None:
    report = strict(a=meta("a", symbol="BTC", venue="x", data_source="d1"),
                    b=meta("b", **{"symbol": "BTC", "venue": "x", "data_source": "d1", field: "other"}))
    assert report.state.value == "NOT_COMPARABLE" and not report.deterministic_parity_verified
    assert report.findings[0].classification.value == "INPUT_MISMATCH" and report.findings[0].field == field


@pytest.mark.parametrize("field", ["symbol", "venue", "data_source"])
def test_regression_reports_identity_difference_without_claiming_parity(field: str) -> None:
    report = strict(mode="regression", a=meta("a", **{field: "one"}), b=meta("b", **{field: "two"}))
    assert report.state.value == "FAIL" and not report.deterministic_parity_verified


def test_missing_data_source_on_either_side_is_unverifiable() -> None:
    for a, b in ((meta("a", data_source=None), meta("b")), (meta("a"), meta("b", data_source=None))):
        report = strict(a=a, b=b)
        assert report.state.value == "UNVERIFIABLE" and report.first_divergence.field == "data_source"


def test_one_sided_market_identity_is_unverifiable_but_none_declared_is_fine() -> None:
    assert strict(a=meta("a", symbol="BTC")).state.value == "UNVERIFIABLE"
    assert strict(b=meta("b", venue="x")).state.value == "UNVERIFIABLE"
    assert strict().state.value == "PASS"


def test_missing_input_fingerprint_is_unverifiable() -> None:
    for left, right in (([obs(input_hash=None)], [obs()]), ([obs()], [obs(input_hash=None)]),
                        ([obs(input_hash=None)], [obs(input_hash=None)])):
        report = strict(left, right)
        assert report.state.value == "UNVERIFIABLE" and report.first_divergence.field == "input_hash"


def test_different_input_fingerprint_is_not_comparable() -> None:
    assert strict([obs(input_hash="h1")], [obs(input_hash="h2")]).state.value == "NOT_COMPARABLE"


def test_model_identity_is_required_only_when_a_model_score_is_recorded() -> None:
    assert strict([obs(model_score=0.5)], [obs(model_score=0.5)]).state.value == "UNVERIFIABLE"
    with_model = {"a": meta("a", model_version="m"), "b": meta("b", model_version="m")}
    assert strict([obs(model_score=0.5)], [obs(model_score=0.5)], **with_model).state.value == "PASS"
    assert strict(a=meta("a", model_version="m"), b=meta("b", model_version="n")).state.value == "NOT_COMPARABLE"


def test_a_trace_with_no_pipeline_output_cannot_verify_anything() -> None:
    report = strict([obs(decision=None)], [obs(decision=None)])
    assert report.state.value == "UNVERIFIABLE" and not report.deterministic_parity_verified


def test_precedence_not_comparable_then_fail_then_unverifiable() -> None:
    values = ([obs(features={"f": feat(1)})], [obs(features={"f": feat(2)})])
    assert strict(*values, b=meta("b", config_hash="z")).state.value == "NOT_COMPARABLE"
    assert strict(*values).state.value == "FAIL"
    missing = strict([obs(input_hash=None, features={"f": feat(1)})], [obs(input_hash=None, features={"f": feat(2)})])
    assert missing.state.value == "FAIL"
    assert strict(a=meta("a", data_source=None)).state.value == "UNVERIFIABLE"


def test_regression_never_verifies_even_with_complete_evidence() -> None:
    report = strict(mode="regression")
    assert report.state.value == "PASS" and not report.deterministic_parity_verified


@pytest.mark.parametrize(("field", "left", "right", "code"), [
    ("decision", None, "BUY", "DECISION_MISMATCH"), ("decision", 1, "1", "DECISION_MISMATCH"),
    ("model_score", None, 0.5, "MODEL_SCORE_MISMATCH"), ("model_score", "0.5", 0.5, "MODEL_SCORE_MISMATCH"),
    ("state_hash", None, "s", "STATE_MISMATCH"), ("state_hash", "s1", "s2", "STATE_MISMATCH")])
def test_output_type_and_presence_mismatches_are_detected(field: str, left: Any, right: Any, code: str) -> None:
    both = {"a": meta("a", model_version="m"), "b": meta("b", model_version="m")}
    report = strict([obs(**{field: left})], [obs(**{field: right})], **both)
    assert report.state.value == "FAIL" and code in {f.classification.value for f in report.findings}

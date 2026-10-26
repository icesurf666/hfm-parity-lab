"""F5/F6: event order is part of the contract; first_divergence follows trace position."""
from __future__ import annotations

from builders import feat, meta, obs, run
from hypothesis import given
from hypothesis import strategies as st


def ids(*names: str, stage: str = "s", **kw: object) -> list[object]:
    return [obs(name, stage, **kw) for name in names]


def test_reordering_without_sequence_cannot_verify() -> None:
    report = run(ids("e1", "e2", "e3"), ids("e2", "e1", "e3"))
    assert report.state.value == "FAIL" and not report.deterministic_parity_verified
    assert report.first_divergence.classification.value == "EVENT_MISMATCH" and "order" in report.first_divergence.message


def test_reordering_with_matching_sequence_values_is_still_detected() -> None:
    left = [obs("e1", sequence=1), obs("e2", sequence=2)]
    right = [obs("e2", sequence=2), obs("e1", sequence=1)]
    assert run(left, right).state.value == "FAIL"


def test_identical_order_passes_and_interleaving_across_stages_is_not_an_order_change() -> None:
    left = [obs("e1", "a"), obs("e1", "b"), obs("e2", "a"), obs("e2", "b")]
    right = [obs("e1", "a"), obs("e2", "a"), obs("e1", "b"), obs("e2", "b")]
    assert run(left, left).state.value == "PASS"
    assert run(left, right).state.value == "PASS"


def test_first_divergence_is_the_earliest_event_not_the_first_structural_finding() -> None:
    left = [obs("e1", features={"f": feat(1)}), obs("e2"), obs("e9"), obs("e9")]
    right = [obs("e1", features={"f": feat(2)}), obs("e2"), obs("e9"), obs("e9")]
    report = run(left, right)
    assert report.first_divergence.event_id == "e1"
    assert report.first_divergence.classification.value == "FEATURE_VALUE_MISMATCH"
    assert {f.classification.value for f in report.findings} >= {"EVENT_MISMATCH", "FEATURE_VALUE_MISMATCH"}


def test_first_divergence_uses_record_position_not_id_sort_order() -> None:
    left = [obs("evt-10", features={"f": feat(1)}), obs("evt-2", features={"f": feat(1)})]
    right = [obs("evt-10", features={"f": feat(2)}), obs("evt-2", features={"f": feat(2)})]
    assert run(left, right).first_divergence.event_id == "evt-10"


def test_verdict_severity_does_not_decide_which_event_is_first() -> None:
    left = [obs("e1", decision="BUY"), obs("e2", features={"f": feat(1)})]
    right = [obs("e1", decision="SELL"), obs("e2", features={"f": feat(2)})]
    assert run(left, right).first_divergence.event_id == "e1"


def test_missing_event_is_located_at_its_baseline_position() -> None:
    left = ids("e1", "e2", "e3")
    right = [obs("e1"), obs("e3", features={"f": feat(9)})]
    assert run(left, right).first_divergence.event_id == "e2"


@given(st.permutations(["a", "b", "c", "d", "e"]))
def test_property_no_reordering_ever_verifies(order: list[str]) -> None:
    base = ["a", "b", "c", "d", "e"]
    report = run(ids(*base), ids(*order))
    assert report.deterministic_parity_verified == (order == base)


def test_first_divergence_is_an_event_even_when_run_level_findings_come_first_in_the_report() -> None:
    left = [obs("e1", features={"f": feat(1)})]
    right = [obs("e1", features={"f": feat(2)})]
    regression = run(left, right, mode="regression", b=meta("b", config_hash="other"))
    assert regression.findings[0].classification.value == "CONFIG_MISMATCH"
    assert regression.first_divergence.classification.value == "FEATURE_VALUE_MISMATCH"
    unverifiable = run(left, right, a=meta("a", data_source=None))
    assert unverifiable.findings[0].field == "data_source"
    assert unverifiable.first_divergence.event_id == "e1"

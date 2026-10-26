from __future__ import annotations

from pathlib import Path

import pytest
from mcp_support import write_trace

from hfm_parity import CompareConfig, ComparisonMode, compare_runs, read_jsonl
from hfm_parity.interfaces.cli import main as cli_main
from hfm_parity.interfaces.mcp_paths import ToolFailure
from hfm_parity.interfaces.mcp_service import EvidenceService


def test_validate_reports_coverage_and_does_not_claim_causality(root: Path) -> None:
    result = EvidenceService(root).validate("base.jsonl")
    assert result["summary"]["valid"] and result["summary"]["strict_comparison_possible"]
    assert any("causal" in note for note in result["limitations"])


def test_validate_invalid_jsonl_is_a_finding_without_private_path(root: Path) -> None:
    (root / "broken.jsonl").write_text("{not json\n")
    result = EvidenceService(root).validate("broken.jsonl")
    assert result["verdict"] == "INVALID" and not result["summary"]["valid"]
    assert str(root) not in str(result)


def test_validate_flags_duplicates_and_missing_timestamps(root: Path) -> None:
    write_trace(root / "dup.jsonl", duplicate=True, with_decision_ts=False)
    result = EvidenceService(root).validate("dup.jsonl")
    kinds = {item["classification"] for item in result["findings"]}
    assert {"DUPLICATE_EVENT_STAGE", "COVERAGE_GAP"} <= kinds
    assert not result["summary"]["strict_comparison_possible"]


def test_strict_pass_verifies_but_regression_never_does(root: Path) -> None:
    service = EvidenceService(root)
    strict = service.compare("base.jsonl", "same.jsonl")
    regression = service.compare("base.jsonl", "same.jsonl", "regression")
    assert strict["verdict"] == "PASS" and strict["summary"]["deterministic_parity_verified"]
    assert regression["verdict"] == "PASS" and not regression["summary"]["deterministic_parity_verified"]
    assert any("never verifies" in note for note in regression["limitations"])


def test_mismatch_names_first_divergence_without_inventing_a_cause(root: Path) -> None:
    result = EvidenceService(root).compare("base.jsonl", "bad.jsonl")
    first = result["summary"]["first_divergence"]
    assert result["verdict"] == "FAIL" and first["classification"] == "FEATURE_VALUE_MISMATCH"
    assert first["evidence_kind"] == "observed_mismatch"
    assert any("no cause is established" in note for note in result["limitations"])


@pytest.mark.parametrize(("override", "state"), [
    ({"config_hash": "c2"}, "NOT_COMPARABLE"),
    ({"model_version": "m2"}, "NOT_COMPARABLE"),
    ({"clock_domain": "other"}, "NOT_COMPARABLE"),
])
def test_incompatible_contracts_are_not_comparable(root: Path, override: dict[str, str], state: str) -> None:
    write_trace(root / "other.jsonl", "other", **override)
    assert EvidenceService(root).compare("base.jsonl", "other.jsonl")["verdict"] == state


def test_missing_decision_timestamps_are_unverifiable(root: Path) -> None:
    write_trace(root / "a.jsonl", "a", with_decision_ts=False)
    write_trace(root / "b.jsonl", "b", with_decision_ts=False)
    result = EvidenceService(root).compare("a.jsonl", "b.jsonl")
    assert result["verdict"] == "UNVERIFIABLE" and result["summary"]["unverifiable"]


def test_duplicate_events_are_reported_not_compared(root: Path) -> None:
    write_trace(root / "dup.jsonl", "dup", duplicate=True)
    result = EvidenceService(root).compare("base.jsonl", "dup.jsonl")
    assert "EVENT_MISMATCH" in result["summary"]["findings_by_category"]
    assert result["verdict"] != "PASS"


def test_truncation_is_explicit_and_totals_stay_complete(root: Path) -> None:
    result = EvidenceService(root).compare("base.jsonl", "bad.jsonl", max_findings=1)
    assert result["summary"]["truncated"] and len(result["findings"]) == 1
    assert result["summary"]["total_findings"] > 1


def test_ordering_is_deterministic(root: Path) -> None:
    service = EvidenceService(root)
    assert service.compare("base.jsonl", "bad.jsonl") == service.compare("base.jsonl", "bad.jsonl")


def test_summary_groups_every_finding_even_when_few_are_returned(root: Path) -> None:
    summary = EvidenceService(root).summarize("base.jsonl", "bad.jsonl", top=1)["summary"]
    assert summary["by_field"] == {"decision": 3, "x": 3}
    assert summary["affected_events"] == 3 and len(summary["earliest_events"]) == 1


def test_mcp_conclusions_match_sdk_and_cli(root: Path, capsys: pytest.CaptureFixture[str],
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(root)
    for candidate, mode in (("same.jsonl", "strict"), ("bad.jsonl", "strict"), ("bad.jsonl", "regression")):
        sdk = compare_runs(read_jsonl(root / "base.jsonl"), read_jsonl(root / candidate),
                           CompareConfig(mode=ComparisonMode(mode)))
        mcp = EvidenceService(root).compare("base.jsonl", candidate, mode)
        code = cli_main(["diff", "--baseline", str(root / "base.jsonl"), "--candidate", str(root / candidate),
                         "--output", "out.html", "--mode", mode])
        assert mcp["verdict"] == sdk.state.value
        assert mcp["summary"]["total_findings"] == len(sdk.findings)
        assert mcp["summary"]["deterministic_parity_verified"] == sdk.deterministic_parity_verified
        assert code == (0 if sdk.state.value == "PASS" else 1)
    capsys.readouterr()


def test_inspect_gives_feature_and_decision_evidence(root: Path) -> None:
    result = EvidenceService(root).inspect("base.jsonl", "bad.jsonl", "e-1", "features", context=1)
    evidence = result["evidence"]
    assert evidence["feature_differences"][0]["identical"] is False
    assert evidence["decision"] == {"baseline": "BUY", "candidate": "HOLD", "identical": False}
    assert result["summary"]["diagnostic_classes"] == ["DECISION_MISMATCH", "FEATURE_VALUE_MISMATCH"]
    assert evidence["neighbouring_events"]["baseline"] == ["e-1", "e-2"]


def test_inspect_unknown_event_and_bad_mode_fail_with_codes(root: Path) -> None:
    service = EvidenceService(root)
    with pytest.raises(ToolFailure) as missing:
        service.inspect("base.jsonl", "bad.jsonl", "nope")
    with pytest.raises(ToolFailure) as mode:
        service.compare("base.jsonl", "bad.jsonl", "fuzzy")
    assert (missing.value.code, mode.value.code) == ("EVENT_NOT_FOUND", "INVALID_ARGUMENT")


def test_missing_and_invalid_traces_fail_with_codes(root: Path) -> None:
    (root / "broken.jsonl").write_text('{"record_type":"run"}\n')
    service = EvidenceService(root)
    for name, code in (("absent.jsonl", "TRACE_NOT_FOUND"), ("broken.jsonl", "TRACE_INVALID")):
        with pytest.raises(ToolFailure) as caught:
            service.compare(name, "base.jsonl")
        assert caught.value.code == code


def test_excessively_large_trace_fails_safely(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hfm_parity.adapters import jsonl
    monkeypatch.setattr(jsonl, "MAX_BYTES", 10)
    with pytest.raises(ToolFailure) as caught:
        EvidenceService(root).compare("base.jsonl", "same.jsonl")
    assert caught.value.code == "TRACE_INVALID" and str(root) not in str(caught.value)

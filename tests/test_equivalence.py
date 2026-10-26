"""SDK, CLI and MCP must reach the same verdict for the same pair of recorded traces."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from builders import meta

from hfm_parity import (
    CompareConfig,
    ComparisonMode,
    TraceRecorder,
    compare_runs,
    feature,
    read_jsonl,
)
from hfm_parity.interfaces.cli import main as cli_main
from hfm_parity.interfaces.mcp_service import EvidenceService

BIG = 2**53


def record(path: Path, run_id: str, *, value: Any = 1, order: tuple[str, ...] = ("e1", "e2"), **changes: Any) -> None:
    with TraceRecorder(path, meta(run_id, **changes)) as trace:
        for index, event in enumerate(order):
            trace.record(event, "s", source="x", input_hash=f"h-{event}", event_ts_ns=1, decision_ts_ns=2,
                         features={"f": feature(value, "u", 1)}, decision="BUY")


CASES = {
    "identical": ({}, {}, "strict", "PASS", 0),
    "large-integers": ({"value": BIG}, {"value": BIG + 1}, "strict", "FAIL", 1),
    "nested-bool-integer": ({"value": [1]}, {"value": [True]}, "strict", "FAIL", 1),
    "different-symbol": ({"symbol": "BTC"}, {"symbol": "ETH"}, "strict", "NOT_COMPARABLE", 2),
    "missing-data-source": ({"data_source": None}, {"data_source": None}, "strict", "UNVERIFIABLE", 2),
    "reordered": ({}, {"order": ("e2", "e1")}, "strict", "FAIL", 1),
    "regression-identical": ({}, {}, "regression", "PASS", 0),
    "regression-other-source": ({}, {"data_source": "other"}, "regression", "FAIL", 1),
}


@pytest.mark.parametrize("name", CASES)
def test_all_interfaces_agree(tmp_path: Path, name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    left, right, mode, verdict, code = CASES[name]
    record(tmp_path / "a.jsonl", "a", **left)
    record(tmp_path / "b.jsonl", "b", **right)
    sdk = compare_runs(read_jsonl(tmp_path / "a.jsonl"), read_jsonl(tmp_path / "b.jsonl"),
                       CompareConfig(mode=ComparisonMode(mode)))
    monkeypatch.chdir(tmp_path)
    exit_code = cli_main(["diff", "--baseline", "a.jsonl", "--candidate", "b.jsonl", "--output", "r.html", "--mode", mode])
    mcp = EvidenceService(tmp_path).compare("a.jsonl", "b.jsonl", mode)
    assert sdk.state.value == mcp["verdict"] == verdict and exit_code == code
    assert mcp["summary"]["deterministic_parity_verified"] == sdk.deterministic_parity_verified == (verdict == "PASS" and mode == "strict")
    assert mcp["summary"]["total_findings"] == len(sdk.findings)


def test_validate_trace_lists_what_strict_verification_still_needs(tmp_path: Path) -> None:
    record(tmp_path / "ok.jsonl", "ok")
    record(tmp_path / "gap.jsonl", "gap", data_source=None)
    service = EvidenceService(tmp_path)
    assert service.validate("ok.jsonl")["summary"]["strict_comparison_possible"]
    gap = service.validate("gap.jsonl")
    assert not gap["summary"]["strict_comparison_possible"]
    assert any("data_source" in f["message"] for f in gap["findings"])

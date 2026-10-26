from __future__ import annotations

import json
from pathlib import Path

import pytest

from hfm_parity.adapters.reports import _row, write_html, write_json
from hfm_parity.application.compare import compare_runs
from hfm_parity.domain.models import (
    Classification,
    CompareConfig,
    ComparisonMode,
    Feature,
    Observation,
    ResultState,
    RunMeta,
    Trace,
)

META = RunMeta("r", "1", "p", "f", "c", "unix_ns", data_source="ds")


def row(event: str = "e", features: dict[str, Feature] | None = None, **changes: object) -> Observation:
    values: dict[str, object] = {"event_id": event, "stage": "decision", "sequence": 1,
                                 "source": "s", "event_ts_ns": 1, "input_hash": "i",
                                 "features": features or {"x": Feature(1.0, "ratio", 1)},
                                 "decision_ts_ns": 1, "state_hash": "one"}
    values.update(changes)
    return Observation(**values)  # type: ignore[arg-type]


def compare(left: Observation, right: Observation):  # type: ignore[no-untyped-def]
    return compare_runs(Trace(META, (left,)), Trace(META, (right,)))


def test_empty_traces_are_unverifiable_not_pass() -> None:
    report = compare_runs(Trace(META, ()), Trace(META, ()))
    assert report.state is ResultState.UNVERIFIABLE


def test_first_feature_finding_is_stable() -> None:
    report = compare(row(features={"z": Feature(1, None, 1), "a": Feature(1, None, 1)}),
                     row(features={"z": Feature(2, None, 1), "a": Feature(2, None, 1)}))
    assert report.first_divergence is not None
    assert report.first_divergence.field == "a"


def test_tolerance_boundary_and_invalid_tolerance() -> None:
    report = compare_runs(Trace(META, (row(features={"x": Feature(1.0, None, 1)}),)),
                          Trace(META, (row(features={"x": Feature(1.125, None, 1)}),)), CompareConfig(0.125))
    assert report.state is ResultState.PASS
    with pytest.raises(ValueError, match="tolerances"):
        CompareConfig(-0.1)


def test_state_hash_difference_is_not_hidden() -> None:
    report = compare(row(), row(state_hash="two"))
    assert Classification.STATE_MISMATCH in {item.classification for item in report.findings}


def test_report_writers_escape_html_and_encode_nan(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    report = compare(row(event="<script>alert(1)</script>", features={"x": Feature(float("inf"), None, 1)}),
                     row(event="<script>alert(1)</script>", features={"x": Feature(float("-inf"), None, 1)}))
    monkeypatch.chdir(tmp_path)
    html_path, json_path = Path("out.html"), Path("out.json")
    write_html(report, html_path)
    write_json(report, json_path)
    assert "<script>" not in html_path.read_text(encoding="utf-8")
    assert "&lt;script&gt;" in html_path.read_text(encoding="utf-8")
    finding = json.loads(json_path.read_text(encoding="utf-8"))["findings"][0]
    assert finding["baseline"]["numeric_kind"] == "infinity"


def test_regression_result_never_claims_verified_parity() -> None:
    old = Trace(META, (row(),))
    new = Trace(RunMeta("r", "1", "p", "f", "new", "unix_ns", data_source="ds"), (row(),))
    report = compare_runs(old, new, CompareConfig(mode=ComparisonMode.REGRESSION))
    assert report.as_dict()["deterministic_parity_verified"] is False


def test_strict_input_mismatch_is_not_comparable() -> None:
    report = compare(row(input_hash="left"), row(input_hash="right"))
    assert report.state is ResultState.NOT_COMPARABLE
    regression = compare_runs(Trace(META, (row(input_hash="left"),)), Trace(META, (row(input_hash="right"),)),
                              CompareConfig(mode=ComparisonMode.REGRESSION))
    assert regression.state is ResultState.FAIL


def test_report_output_rejects_symlink_escape_and_keeps_zero_visible(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    sandbox, outside = tmp_path / "sandbox", tmp_path / "outside"
    sandbox.mkdir()
    (sandbox / "escape").symlink_to(outside, target_is_directory=True)
    monkeypatch.chdir(sandbox)
    with pytest.raises(ValueError, match="inside"):
        write_json(compare(row(), row()), Path("escape/report.json"))
    assert "<td>0</td>" in _row({"classification": 0, "message": ""})

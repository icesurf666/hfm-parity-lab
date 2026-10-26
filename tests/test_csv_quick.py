"""External CSV onboarding must remain a thin, evidence-limited adapter."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hfm_parity import CompareConfig, ComparisonMode, compare_csv, csv_trace, load_csv_mapping
from hfm_parity.domain.schema import TraceValidationError
from hfm_parity.interfaces.cli import main as cli_main


def mapping(path: Path, **changes: object) -> Path:
    value = {
        "identity": {"event_id": {"baseline": "event_id", "candidate": "event_id", "type": "string"}},
        "stage": {"default": "decision"},
        "features": {"fraction": {"baseline": "frac", "candidate": "run_fraction", "type": "float"},
                     "quantity": {"baseline": "qty", "candidate": "quantity", "type": "integer"}},
        "model_score": {"baseline": "score", "candidate": "prediction", "type": "float"},
        "decision": {"baseline": "decision", "candidate": "signal", "type": "string"},
    }
    value.update(changes)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def csv(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


BASE = "event_id,frac,qty,score,decision\ne1,0.6,9007199254740993,0.8,BUY\ne2,0.5,2,0.2,SKIP\n"
CANDIDATE = "event_id,run_fraction,quantity,prediction,signal\ne1,0.4,9007199254740993,0.6,SKIP\ne2,0.5,2,0.2,SKIP\n"


def test_csv_adapter_uses_the_existing_engine_and_preserves_large_integers(tmp_path: Path) -> None:
    result = compare_csv(csv(tmp_path / "base.csv", BASE), csv(tmp_path / "live.csv", CANDIDATE),
                         load_csv_mapping(mapping(tmp_path / "mapping.json")))
    assert result.state.value == "FAIL" and not result.deterministic_parity_verified
    assert result.first_divergence is not None and result.first_divergence.field == "fraction"
    trace = csv_trace(tmp_path / "base.csv", load_csv_mapping(tmp_path / "mapping.json"), "baseline")
    assert trace.observations[0].features["quantity"].value == 9007199254740993


def test_equal_csv_is_unverifiable_without_genuine_provenance(tmp_path: Path) -> None:
    same = "event_id,frac,qty,score,decision\ne1,0.6,1,0.8,BUY\n"
    candidate = "event_id,run_fraction,quantity,prediction,signal\ne1,0.6,1,0.8,BUY\n"
    result = compare_csv(csv(tmp_path / "a.csv", same), csv(tmp_path / "b.csv", candidate),
                         load_csv_mapping(mapping(tmp_path / "m.json")))
    assert result.state.value == "UNVERIFIABLE" and not result.deterministic_parity_verified


@pytest.mark.parametrize("text, message", [
    ("", "unique non-empty headers"),
    ("event_id,event_id,frac,qty,score,decision\ne1,e1,1,1,1,BUY\n", "unique non-empty headers"),
    ("event_id,frac,score,decision\ne1,1,1,BUY\n", "missing mapped column"),
    ("event_id,frac,qty,score,decision\n,1,1,1,BUY\n", "event_id must"),
    ("event_id,frac,qty,score,decision\ne1,not-a-float,1,1,BUY\n", "cannot parse"),
    ("event_id,frac,qty,score,decision\ne1,1,001,1,BUY\n", "cannot parse"),
    ("event_id,frac,qty,score,decision\ne1,1,1,1,BUY\ne1,1,1,1,BUY\n", "duplicate event"),
])
def test_csv_rejects_ambiguous_or_malformed_input(tmp_path: Path, text: str, message: str) -> None:
    file = csv(tmp_path / "bad.csv", text)
    with pytest.raises(TraceValidationError, match=message):
        csv_trace(file, load_csv_mapping(mapping(tmp_path / "m.json")), "baseline")


def test_csv_supports_bom_quoted_cells_and_explicit_composite_identity(tmp_path: Path) -> None:
    config = mapping(tmp_path / "m.json", identity={"composite": {"baseline": ["symbol", "bar"], "candidate": ["ticker", "time"]}})
    baseline = csv(tmp_path / "a.csv", "\ufeffsymbol,bar,frac,qty,score,decision\nBTC,\"1,2\",0.5,1,0.2,BUY\n")
    candidate = csv(tmp_path / "b.csv", "ticker,time,run_fraction,quantity,prediction,signal\nBTC,\"1,2\",0.5,1,0.2,BUY\n")
    result = compare_csv(baseline, candidate, load_csv_mapping(config))
    assert result.state.value == "UNVERIFIABLE" and result.aligned_events == 1


def test_quick_diff_cli_writes_the_standard_report_and_never_verifies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                                        capsys: pytest.CaptureFixture[str]) -> None:
    baseline, candidate = csv(tmp_path / "base.csv", BASE), csv(tmp_path / "live.csv", CANDIDATE)
    config = mapping(tmp_path / "mapping.json")
    monkeypatch.chdir(tmp_path)
    code = cli_main(["quick-diff", str(baseline), str(candidate), "--mapping", str(config), "--output", "out.html", "--json-output", "out.json"])
    report = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert code == 1 and (tmp_path / "out.html").is_file() and report["deterministic_parity_verified"] is False
    assert "Quick Compare" in capsys.readouterr().out


def test_csv_type_contract_rejects_bool_as_integer_and_preserves_empty_string(tmp_path: Path) -> None:
    baseline = csv(tmp_path / "a.csv", "event_id,frac,qty,score,decision\ne1,1,true,1,\n")
    with pytest.raises(TraceValidationError, match="cannot parse"):
        csv_trace(baseline, load_csv_mapping(mapping(tmp_path / "m.json")), "baseline")
    valid = csv(tmp_path / "a.csv", "event_id,frac,qty,score,decision\ne1,1,1,1,\n")
    assert csv_trace(valid, load_csv_mapping(tmp_path / "m.json"), "baseline").observations[0].decision == ""


def test_missing_events_reordering_and_explicit_nulls_reach_existing_verdicts(tmp_path: Path) -> None:
    baseline = csv(tmp_path / "a.csv", BASE)
    reordered = csv(tmp_path / "b.csv", "event_id,run_fraction,quantity,prediction,signal\ne2,0.5,2,0.2,SKIP\n")
    result = compare_csv(baseline, reordered, load_csv_mapping(mapping(tmp_path / "m.json")))
    assert result.state.value == "FAIL" and any(f.classification.value == "EVENT_MISMATCH" for f in result.findings)
    data = json.loads((tmp_path / "m.json").read_text(encoding="utf-8"))
    data["features"]["quantity"]["nullable"] = True
    (tmp_path / "m.json").write_text(json.dumps(data), encoding="utf-8")
    nullable = csv(tmp_path / "null.csv", "event_id,frac,qty,score,decision\ne1,1,,1,BUY\n")
    assert csv_trace(nullable, load_csv_mapping(tmp_path / "m.json"), "baseline").observations[0].features["quantity"].value is None


def test_invalid_unicode_is_a_typed_csv_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_bytes(b"event_id,frac,qty,score,decision\n\xff,1,1,1,BUY\n")
    with pytest.raises(TraceValidationError, match="valid UTF-8 CSV"):
        csv_trace(bad, load_csv_mapping(mapping(tmp_path / "m.json")), "baseline")


def test_regression_mode_remains_non_verified_for_matching_csv(tmp_path: Path) -> None:
    baseline = csv(tmp_path / "a.csv", "event_id,frac,qty,score,decision\ne1,1,1,1,BUY\n")
    candidate = csv(tmp_path / "b.csv", "event_id,run_fraction,quantity,prediction,signal\ne1,1,1,1,BUY\n")
    result = compare_csv(baseline, candidate, load_csv_mapping(mapping(tmp_path / "m.json")),
                         CompareConfig(mode=ComparisonMode.REGRESSION))
    assert result.state.value == "UNVERIFIABLE" and not result.deterministic_parity_verified

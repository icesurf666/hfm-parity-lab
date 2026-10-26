from __future__ import annotations

from pathlib import Path

from hfm_parity.interfaces.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_validate_and_diff_exit_codes(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    baseline = ROOT / "examples" / "baseline.jsonl"
    candidate = ROOT / "examples" / "candidate.jsonl"
    assert main(["validate", str(baseline)]) == 0
    assert main(["diff", "--baseline", str(baseline), "--candidate", str(candidate),
                 "--output", str(tmp_path / "absolute.html")]) == 4
    assert "ERROR" in capsys.readouterr().out


def test_demo_generates_intentional_mismatch_report(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    assert main(["demo"]) == 0
    assert (tmp_path / "parity-demo.html").is_file()
    assert (tmp_path / "parity-demo.json").is_file()

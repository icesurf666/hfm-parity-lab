from __future__ import annotations

import json
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


def test_diff_reports_nested_duplicate_key_as_not_comparable(tmp_path, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    bad = tmp_path / "bad.jsonl"
    bad.write_text(
        '{"record_type":"run","run_id":"x","schema_version":"1","pipeline_version":"p",'
        '"feature_schema_hash":"f","config_hash":"c","clock_domain":"unix_ns"}\n'
        '{"record_type":"observation","event":{"id":"a"},"stage":"x",'
        '"features":{"f":{"value":{"x":1,"x":1.5}}}}\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    assert main(["diff", "--baseline", str(bad), "--candidate", str(ROOT / "examples" / "baseline.jsonl"),
                 "--output", "report.html", "--json-output", "report.json"]) == 2
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["state"] == "NOT_COMPARABLE"
    assert report["findings"][0]["classification"] == "TRACE_INVALID"
    assert "NOT_COMPARABLE" in capsys.readouterr().out

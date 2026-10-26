from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from hfm_parity import Classification, compare_runs, read_jsonl

ROOT = Path(__file__).resolve().parents[1]


def test_sdk_example_uses_only_public_imports(tmp_path) -> None:  # type: ignore[no-untyped-def]
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run(
        [sys.executable, str(ROOT / "examples" / "sdk_compare.py"),
         str(ROOT / "examples" / "baseline.jsonl"), str(ROOT / "examples" / "candidate.jsonl"),
        "--output-dir", "report"], cwd=tmp_path, env=environment, text=True, capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert result.stdout.startswith("FAIL")
    assert (tmp_path / "report" / "report.html").is_file()
    assert (tmp_path / "report" / "report.json").is_file()


def test_two_trace_recorder_example_has_feature_as_first_difference(tmp_path) -> None:  # type: ignore[no-untyped-def]
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run(
        [sys.executable, str(ROOT / "examples" / "record_two_traces.py"), "--output-dir", "traces"],
        cwd=tmp_path, env=environment, text=True, capture_output=True, check=False,
    )
    report = compare_runs(read_jsonl(tmp_path / "traces" / "baseline.jsonl"),
                          read_jsonl(tmp_path / "traces" / "candidate.jsonl"))
    assert result.returncode == 0
    assert report.first_divergence is not None
    assert report.first_divergence.classification is Classification.FEATURE_VALUE_MISMATCH

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples" / "synthetic_pipeline"))

from make_demo import build


def test_demo_verdicts_and_committed_artifacts_are_current(tmp_path: Path) -> None:
    """docs/demo must equal a fresh deterministic run, so published output never goes stale."""
    assert build(tmp_path / "fresh") == {"defect": "FAIL", "fixed": "PASS"}
    generated = [p for p in sorted((ROOT / "docs" / "demo").iterdir()) if p.suffix in {".jsonl", ".json", ".html"}]
    assert len(generated) == 7
    for committed in generated:
        assert committed.read_bytes() == (tmp_path / "fresh" / committed.name).read_bytes(), committed.name

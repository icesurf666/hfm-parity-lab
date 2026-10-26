from __future__ import annotations

from pathlib import Path

import pytest
from mcp_support import write_trace


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A trace directory holding an identical pair and a pair with a feature defect."""
    write_trace(tmp_path / "base.jsonl", "base")
    write_trace(tmp_path / "same.jsonl", "same")
    write_trace(tmp_path / "bad.jsonl", "bad", value=0.9, decision="HOLD")
    return tmp_path

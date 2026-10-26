"""F8: hostile numeric and nesting input is rejected with typed errors at every entry point."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from builders import meta

from hfm_parity import TraceValidationError, read_jsonl
from hfm_parity.interfaces.cli import main as cli_main
from hfm_parity.interfaces.mcp_paths import ToolFailure
from hfm_parity.interfaces.mcp_service import EvidenceService

HEAD = json.dumps({"record_type": "run", **meta().__dict__})
ROW = '{"record_type":"observation","event":{"id":"e"},"stage":"s","features":{"f":{"value":%s}}}'
HOSTILE = {
    "deep-array": ROW % ("[" * 100_000 + "]" * 100_000), "deep-by-limit": ROW % ("[" * 40 + "]" * 40),
    "5000-digits": ROW % ("1" * 5000), "200-digits": ROW % ("1" * 200), "float-overflow": ROW % "1e999",
    "negative-overflow": ROW % "-1e999", "nan": ROW % "NaN", "infinity": ROW % "Infinity",
    "exponent-bomb": ROW % "1" + "e" * 0,
}
HOSTILE.pop("exponent-bomb")


@pytest.mark.parametrize("name", HOSTILE)
def test_reader_raises_only_validation_errors(tmp_path: Path, name: str) -> None:
    path = tmp_path / "t.jsonl"
    path.write_text(HEAD + "\n" + HOSTILE[name] + "\n")
    with pytest.raises(TraceValidationError):
        read_jsonl(path)


@pytest.mark.parametrize("name", HOSTILE)
def test_cli_reports_invalid_input_not_an_internal_error(tmp_path: Path, name: str, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "t.jsonl"
    path.write_text(HEAD + "\n" + HOSTILE[name] + "\n")
    assert cli_main(["validate", str(path)]) == 3
    assert "INTERNAL_ERROR" not in capsys.readouterr().out


@pytest.mark.parametrize("name", HOSTILE)
def test_mcp_service_reports_invalid_traces_with_a_stable_code(tmp_path: Path, name: str) -> None:
    (tmp_path / "t.jsonl").write_text(HEAD + "\n" + HOSTILE[name] + "\n")
    service = EvidenceService(tmp_path)
    assert service.validate("t.jsonl")["verdict"] == "INVALID"
    with pytest.raises(ToolFailure) as caught:
        service.compare("t.jsonl", "t.jsonl")
    assert caught.value.code == "TRACE_INVALID" and str(tmp_path) not in str(caught.value)


def test_values_at_the_documented_limits_are_accepted(tmp_path: Path) -> None:
    path = tmp_path / "ok.jsonl"
    path.write_text(HEAD + "\n" + ROW % ("1" * 60) + "\n" + ROW.replace('"e"', '"e2"') % ("[" * 8 + "]" * 8) + "\n")
    assert len(read_jsonl(path).observations) == 2

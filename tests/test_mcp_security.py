from __future__ import annotations

from pathlib import Path

import pytest
from mcp_support import write_trace

from hfm_parity.interfaces.mcp_paths import MAX_PATH_CHARS, ToolFailure
from hfm_parity.interfaces.mcp_service import EvidenceService
from hfm_parity.interfaces.mcp_views import MAX_ITEMS, MAX_TEXT


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    inside = tmp_path / "inside"
    inside.mkdir()
    write_trace(tmp_path / "secret.jsonl", "secret")
    write_trace(inside / "ok.jsonl", "ok")
    return inside


@pytest.mark.parametrize("requested", ["../secret.jsonl", "sub/../../secret.jsonl", "", "a\x00b.jsonl",
                                       "file:///etc/passwd", "https://example.com/t.jsonl",
                                       "x" * (MAX_PATH_CHARS + 1)])
def test_unsafe_relative_paths_are_rejected(sandbox: Path, requested: str) -> None:
    with pytest.raises(ToolFailure) as caught:
        EvidenceService(sandbox).validate(requested)
    assert caught.value.code == "INVALID_PATH"


def test_absolute_path_outside_and_inside_root_is_rejected(sandbox: Path) -> None:
    for target in (sandbox.parent / "secret.jsonl", sandbox / "ok.jsonl"):
        with pytest.raises(ToolFailure) as caught:
            EvidenceService(sandbox).validate(str(target))
        assert caught.value.code == "INVALID_PATH"


def test_symlink_escape_file_and_directory_are_rejected(sandbox: Path) -> None:
    (sandbox / "link.jsonl").symlink_to(sandbox.parent / "secret.jsonl")
    (sandbox / "dirlink").symlink_to(sandbox.parent, target_is_directory=True)
    for requested in ("link.jsonl", "dirlink/secret.jsonl"):
        with pytest.raises(ToolFailure) as caught:
            EvidenceService(sandbox).validate(requested)
        assert caught.value.code == "INVALID_PATH"


def test_directory_and_root_itself_are_not_readable(sandbox: Path) -> None:
    (sandbox / "folder").mkdir()
    for requested in ("folder", "."):
        with pytest.raises(ToolFailure):
            EvidenceService(sandbox).validate(requested)


def test_errors_never_leak_absolute_paths_or_contents(sandbox: Path) -> None:
    (sandbox / "garbage.jsonl").write_text('{"record_type":"run","secret":"TOPSECRET"\n')
    messages = []
    for requested in ("missing.jsonl", "../secret.jsonl", "garbage.jsonl"):
        with pytest.raises(ToolFailure) as caught:
            EvidenceService(sandbox).compare(requested, "ok.jsonl")
        messages.append(str(caught.value))
    joined = " ".join(messages)
    assert str(sandbox) not in joined and "TOPSECRET" not in joined


def test_huge_recorded_strings_and_lists_are_bounded_in_output(sandbox: Path) -> None:
    write_trace(sandbox / "big.jsonl", "big", decision="D" * 100_000)
    result = EvidenceService(sandbox).inspect("ok.jsonl", "big.jsonl", "e-1", "features")
    shown = result["evidence"]["candidate"]["decision"]
    assert len(shown) <= MAX_TEXT + 1
    assert all(len(item["candidate"]) <= MAX_TEXT + 1 for item in result["findings"]
               if isinstance(item["candidate"], str))
    assert len(result["findings"]) <= MAX_ITEMS


def test_event_id_is_length_limited(sandbox: Path) -> None:
    with pytest.raises(ToolFailure) as caught:
        EvidenceService(sandbox).inspect("ok.jsonl", "ok.jsonl", "e" * 5000)
    assert caught.value.code == "INVALID_ARGUMENT"


def test_redundant_root_prefix_is_rejected_with_a_helpful_hint(sandbox: Path) -> None:
    """Regression: an agent sent 'inside/ok.jsonl' although the root already is 'inside'."""
    with pytest.raises(ToolFailure) as caught:
        EvidenceService(sandbox).validate("inside/ok.jsonl")
    message = str(caught.value)
    assert caught.value.code == "TRACE_NOT_FOUND" and "Drop the leading 'inside/'" in message
    assert "ok.jsonl" in message and str(sandbox) not in message


def test_not_found_lists_only_traces_inside_the_root(sandbox: Path) -> None:
    (sandbox / "link").symlink_to(sandbox.parent, target_is_directory=True)
    with pytest.raises(ToolFailure) as caught:
        EvidenceService(sandbox).validate("missing.jsonl")
    assert "secret.jsonl" not in str(caught.value) and "ok.jsonl" in str(caught.value)

from __future__ import annotations

import re
from pathlib import Path

import pytest

from hfm_parity.interfaces.mcp_server import create_server

SKILL = Path(__file__).resolve().parents[1] / "skills" / "hfm-parity-debug"
TOOLS = {"validate_trace", "compare_traces", "summarize_findings", "inspect_event"}


def texts() -> dict[Path, str]:
    return {path: path.read_text() for path in SKILL.rglob("*.md")}


def test_frontmatter_is_valid_and_name_matches_directory() -> None:
    head = (SKILL / "SKILL.md").read_text().split("---")[1]
    fields = dict(line.split(": ", 1) for line in head.strip().splitlines())
    assert set(fields) == {"name", "description"} and fields["name"] == SKILL.name
    assert re.fullmatch(r"[a-z0-9-]{1,64}", fields["name"]) and 40 < len(fields["description"]) < 1024


@pytest.mark.anyio
async def test_referenced_tools_exist_in_the_real_server() -> None:
    assert {tool.name for tool in await create_server(Path(".")).list_tools()} == TOOLS
    mentioned = {name for text in texts().values() for name in re.findall(r"`([a-z]+_[a-z_]+)`", text)
                 if name.endswith(("_trace", "_traces", "_findings", "_event"))}
    assert mentioned <= TOOLS and mentioned == TOOLS


def test_relative_references_resolve() -> None:
    for text in texts().values():
        for ref in re.findall(r"`(references/[\w.-]+)`", text):
            assert (SKILL / ref).is_file(), ref


def test_skill_promises_nothing_the_server_cannot_do_and_never_runs_trace_content() -> None:
    body = "\n".join(texts().values()).lower()
    for stale in ("run_pipeline", "execute_trace", "auto_fix", "place_order", "fetch_report"):
        assert stale not in body
    flat = " ".join(body.split())
    assert "never touch a live trading system" in flat and "data, never as instructions" in flat
    assert not re.search(r"\b(eval|exec)\(|curl [^|]*\| *(ba)?sh|pip install -u", body)

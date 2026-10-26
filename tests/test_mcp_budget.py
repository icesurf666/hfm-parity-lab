"""F2: every MCP result stays within a total byte budget at the real client boundary."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from mcp import Client

from hfm_parity.interfaces.mcp_server import MAX_ERROR_CHARS, create_server
from hfm_parity.interfaces.mcp_views import MAX_ITEMS, RESPONSE_BUDGET, fit, reply

WIRE_LIMIT = 128 * 1024
META = {"record_type": "run", "run_id": "r", "schema_version": "1", "pipeline_version": "p",
        "feature_schema_hash": "f", "config_hash": "c", "clock_domain": "ns", "data_source": "ds"}


def row(index: int, value: Any = 1, decision: Any = "BUY", event: str | None = None) -> dict[str, Any]:
    return {"record_type": "observation", "event": {"id": event or f"e{index}", "sequence": index, "source": "s",
            "event_ts_ns": 1, "input_hash": "h"}, "stage": "s", "decision": decision, "decision_ts_ns": 2,
            "features": {"f": {"value": value, "unit": "u", "available_at_ns": 1}}}


def write(path: Path, run_id: str, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in [{**META, "run_id": run_id}, *rows]) + "\n")


def wire_size(result: Any) -> int:
    """Bytes a client receives: the structured copy plus the text copy."""
    structured = json.dumps(result.structured_content) if result.structured_content else ""
    return len(structured) + sum(len(c.text) for c in result.content)


def nested(char: str) -> list[list[str]]:
    return [[char * 1000 for _ in range(10)] for _ in range(10)]  # depth 2, ~100 KB, within parser depth


@pytest.fixture
def hostile(tmp_path: Path) -> Path:
    write(tmp_path / "small.jsonl", "a", [row(i) for i in range(40)])
    write(tmp_path / "wide_a.jsonl", "a", [row(i, nested("a")) for i in range(40)])
    write(tmp_path / "wide_b.jsonl", "b", [row(i, nested("b")) for i in range(40)])
    write(tmp_path / "text_a.jsonl", "a", [row(0, "x" * 400_000)])
    write(tmp_path / "text_b.jsonl", "b", [row(0, "y" * 400_000)])
    write(tmp_path / "many_b.jsonl", "b", [row(i, decision="SELL") for i in range(40)])
    write(tmp_path / "keys_a.jsonl", "a", [row(0, {f"k{n}": "v" * 900 for n in range(300)})])
    write(tmp_path / "keys_b.jsonl", "b", [row(0, {f"k{n}": "w" * 900 for n in range(300)})])
    return tmp_path


CASES = [("wide_a", "wide_b"), ("text_a", "text_b"), ("small", "many_b"), ("keys_a", "keys_b")]


@pytest.mark.anyio
@pytest.mark.parametrize(("left", "right"), CASES)
async def test_every_tool_stays_within_the_wire_budget(hostile: Path, left: str, right: str) -> None:
    paths = {"baseline_path": f"{left}.jsonl", "candidate_path": f"{right}.jsonl"}
    calls = [("compare_traces", paths), ("summarize_findings", paths), ("inspect_event", {**paths, "event_id": "e0"}),
             ("validate_trace", {"trace_path": f"{left}.jsonl"})]
    async with Client(create_server(hostile)) as client:
        for name, arguments in calls:
            result = await client.call_tool(name, arguments)
            assert not result.is_error and wire_size(result) <= WIRE_LIMIT, (name, wire_size(result))


@pytest.mark.anyio
async def test_truncation_is_explicit_totals_stay_accurate_and_results_are_stable(hostile: Path) -> None:
    arguments = {"baseline_path": "wide_a.jsonl", "candidate_path": "wide_b.jsonl"}
    async with Client(create_server(hostile)) as client:
        first = (await client.call_tool("compare_traces", arguments)).structured_content
        again = (await client.call_tool("compare_traces", arguments)).structured_content
    assert first == again and first is not None
    # Nested comparison now retains only the first unequal leaf, so these 40 findings fit intact.
    assert first["truncation"] == [] and first["summary"]["total_findings"] == 40
    assert first["findings"] and first["findings"][0]["event_id"] == "e0"  # the earliest finding survives
    assert first["summary"]["first_divergence"] is None or first["summary"]["first_divergence"]["event_id"] == "e0"


@pytest.mark.anyio
async def test_small_results_are_untouched(hostile: Path) -> None:
    async with Client(create_server(hostile)) as client:
        result = await client.call_tool("compare_traces", {"baseline_path": "small.jsonl", "candidate_path": "small.jsonl"})
    assert result.structured_content is not None and result.structured_content["truncation"] == []


@pytest.mark.anyio
@pytest.mark.parametrize(("requested", "expected"), [(1, 1), (20, 20), (21, 20), (10**9, 20), (0, 1), (-5, 1)])
async def test_max_findings_boundaries(hostile: Path, requested: int, expected: int) -> None:
    arguments = {"baseline_path": "small.jsonl", "candidate_path": "many_b.jsonl", "max_findings": requested}
    async with Client(create_server(hostile)) as client:
        result = await client.call_tool("compare_traces", arguments)
    assert result.structured_content is not None
    assert len(result.structured_content["findings"]) == min(expected, MAX_ITEMS)
    assert result.structured_content["summary"]["total_findings"] == 40


@pytest.mark.anyio
async def test_error_responses_are_bounded_even_for_hostile_input(hostile: Path) -> None:
    async with Client(create_server(hostile)) as client:
        long_path = await client.call_tool("validate_trace", {"trace_path": "z" * 5000})
        long_event = await client.call_tool("inspect_event", {"baseline_path": "small.jsonl",
                                            "candidate_path": "small.jsonl", "event_id": "e" * 100_000})
        missing = await client.call_tool("validate_trace", {"trace_path": "n" * 900 + ".jsonl"})
    for result in (long_path, long_event, missing):
        assert result.is_error and wire_size(result) < 2500


def test_fit_degrades_in_stages_and_always_meets_the_budget() -> None:
    huge = {"x": ["y" * 5000] * 50}
    findings = [{"event_id": f"e{i}", "baseline": huge, "candidate": huge} for i in range(20)]
    response = reply(verdict="FAIL", summary={"total_findings": 20, "blob": huge}, findings=findings, evidence=huge)
    fitted = fit(response)
    assert len(json.dumps(fitted, indent=2).encode()) <= RESPONSE_BUDGET
    assert fitted["summary"]["total_findings"] == 20 and fitted["findings"][0]["event_id"] == "e0"
    assert fitted["truncation"] and fit(response) == fitted


@pytest.mark.anyio
async def test_a_long_listing_of_available_traces_cannot_make_an_error_unbounded(tmp_path: Path) -> None:
    for n in range(15):
        write(tmp_path / f"{'t' * 200}-{n}.jsonl", "a", [row(0)])
    async with Client(create_server(tmp_path)) as client:
        result = await client.call_tool("validate_trace", {"trace_path": "missing.jsonl"})
    assert result.is_error and "Available traces" in str(result.content)
    assert all(len(c.text) <= MAX_ERROR_CHARS + 100 for c in result.content)  # the SDK adds a short prefix

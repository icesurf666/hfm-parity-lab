from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

from hfm_parity import RunMeta, TraceRecorder, feature
from hfm_parity.interfaces.mcp_server import create_server

TOOLS = {"validate_trace", "compare_traces", "summarize_findings", "inspect_event"}
BOTH = {"baseline_path": "base.jsonl", "candidate_path": "bad.jsonl"}


def stdio(root: Path) -> StdioServerParameters:
    return StdioServerParameters(command=sys.executable,
                                 args=["-m", "hfm_parity.interfaces.mcp_server", "--root", str(root)])


@pytest.mark.anyio
async def test_tools_are_discoverable_with_valid_schemas_and_read_only_hints(root: Path) -> None:
    async with Client(create_server(root)) as client:
        tools = (await client.list_tools()).tools
    assert {tool.name for tool in tools} == TOOLS
    for tool in tools:
        assert tool.input_schema["type"] == "object" and tool.output_schema is not None
        assert tool.description and tool.annotations is not None and tool.annotations.read_only_hint
    for tool in tools:
        for name, spec in tool.input_schema["properties"].items():
            if name.endswith("_path"):
                assert "RELATIVE TO THE SERVER ROOT" in spec["description"]
    compare = next(tool for tool in tools if tool.name == "compare_traces")
    assert compare.input_schema["properties"]["mode"]["enum"] == ["strict", "regression"]


@pytest.mark.anyio
async def test_real_stdio_process_serves_a_full_investigation(root: Path) -> None:
    async with Client(stdio(root)) as client:
        compared = await client.call_tool("compare_traces", BOTH)
        inspected = await client.call_tool("inspect_event", {**BOTH, "event_id": "e-1", "stage": "features"})
        missing = await client.call_tool("inspect_event", {**BOTH, "event_id": "zzz"})
    assert compared.structured_content is not None and compared.structured_content["verdict"] == "FAIL"
    assert inspected.structured_content is not None and not inspected.is_error
    assert missing.is_error and "EVENT_NOT_FOUND" in str(missing.content)


@pytest.mark.anyio
async def test_real_stdio_never_verifies_nested_bool_integer_equality(root: Path) -> None:
    fields = {"schema_version": "1", "pipeline_version": "p", "feature_schema_hash": "f", "config_hash": "c", "clock_domain": "ns", "data_source": "ds"}
    for name, value in (("nested-a.jsonl", [1]), ("nested-b.jsonl", [True])):
        with TraceRecorder(root / name, RunMeta(name, **fields)) as trace:
            trace.record("e", "s", source="x", input_hash="h", event_ts_ns=1, decision_ts_ns=2,
                         features={"payload": feature(value, "u", 1)}, decision="BUY")
    async with Client(stdio(root)) as client:
        result = await client.call_tool("compare_traces", {"baseline_path": "nested-a.jsonl", "candidate_path": "nested-b.jsonl"})
    assert result.structured_content is not None
    assert result.structured_content["verdict"] == "FAIL"
    assert not result.structured_content["summary"]["deterministic_parity_verified"]


@pytest.mark.anyio
async def test_invalid_arguments_and_paths_are_error_results_not_crashes(root: Path) -> None:
    async with Client(create_server(root)) as client:
        bad_mode = await client.call_tool("compare_traces", {**BOTH, "mode": "fuzzy"})
        no_args = await client.call_tool("validate_trace", {})
        escape = await client.call_tool("validate_trace", {"trace_path": "../x.jsonl"})
        alive = await client.call_tool("validate_trace", {"trace_path": "base.jsonl"})
    assert bad_mode.is_error and no_args.is_error
    assert escape.is_error and "INVALID_PATH" in str(escape.content) and str(root) not in str(escape.content)
    assert not alive.is_error


def test_stdout_is_silent_and_shutdown_is_clean_on_eof(root: Path) -> None:
    done = subprocess.run([sys.executable, "-m", "hfm_parity.interfaces.mcp_server", "--root", str(root)],
                          input="", text=True, capture_output=True, timeout=30, check=False)
    assert done.stdout == "" and done.returncode == 0


def test_missing_root_exits_with_usage_error_on_stderr(tmp_path: Path) -> None:
    done = subprocess.run([sys.executable, "-m", "hfm_parity.interfaces.mcp_server", "--root",
                           str(tmp_path / "nope")], capture_output=True, text=True, timeout=30, check=False)
    assert done.returncode == 2 and done.stdout == "" and "--root" in done.stderr

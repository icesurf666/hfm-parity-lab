"""Drive the real stdio MCP server end to end with the official SDK client.

Records the synthetic traces, starts ``hfm-parity-mcp`` as a subprocess, then
validates, compares, summarizes and inspects them exactly as an agent would.
"""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

from mcp import Client, StdioServerParameters

sys.path.insert(0, str(Path(__file__).resolve().parent / "synthetic_pipeline"))
from record_traces import record


async def call(client: Client, name: str, **arguments: object) -> dict[str, object]:
    result = await client.call_tool(name, arguments)
    assert not result.is_error and result.structured_content is not None
    print(f"\n## {name} {json.dumps(arguments)}")
    return dict(result.structured_content)


async def main(root: Path) -> None:
    for module, name in (("backtest_features", "baseline"), ("live_features", "candidate"),
                         ("live_features_fixed", "candidate-fixed")):
        record(module, root / f"{name}.jsonl")
    server = StdioServerParameters(command=sys.executable, args=["-m", "hfm_parity.interfaces.mcp_server",
                                                                 "--root", str(root)])
    async with Client(server) as client:
        tools = await client.list_tools()
        print("tools:", sorted(tool.name for tool in tools.tools))
        both = {"baseline_path": "baseline.jsonl", "candidate_path": "candidate.jsonl"}
        shown = await call(client, "validate_trace", trace_path="candidate.jsonl")
        print(json.dumps(shown["summary"], sort_keys=True))
        shown = await call(client, "compare_traces", **both)
        print(shown["verdict"], json.dumps(shown["summary"]["first_divergence"]))
        shown = await call(client, "summarize_findings", **both)
        print(json.dumps(shown["summary"]["by_field"]), json.dumps(shown["summary"]["earliest_events"][:1]))
        shown = await call(client, "inspect_event", **both, event_id="evt-001", stage="features")
        print(json.dumps(shown["evidence"]["feature_differences"]))  # type: ignore[index]
        shown = await call(client, "compare_traces", baseline_path="baseline.jsonl",
                           candidate_path="candidate-fixed.jsonl")
        print(shown["verdict"], "parity_verified =", shown["summary"]["deterministic_parity_verified"])  # type: ignore[index]


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as directory:
        asyncio.run(main(Path(directory)))

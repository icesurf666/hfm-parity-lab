"""Local stdio MCP adapter (official SDK v2). Stdout belongs to the protocol; logs go to stderr."""
# mypy: disable-error-code=untyped-decorator
from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Literal

try:
    from mcp.server import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError
    from pydantic import Field
except ModuleNotFoundError as exc:  # pragma: no cover - exercised via the wheel check
    raise SystemExit("hfm-parity-mcp needs the optional extra: pip install '.[mcp]' (from a source checkout)") from exc

from hfm_parity import __version__
from hfm_parity.interfaces.mcp_paths import ToolFailure
from hfm_parity.interfaces.mcp_service import EvidenceService
from hfm_parity.interfaces.mcp_views import ToolResponse, fit

MAX_ERROR_CHARS = 1000
Mode = Literal["strict", "regression"]
TracePath = Annotated[str, Field(description=(
    "Trace file path RELATIVE TO THE SERVER ROOT, e.g. 'baseline.jsonl' or 'runs/live.jsonl'. "
    "The root directory itself is implied: do not prefix its name, and do not use absolute paths or '..'."))]
EventId = Annotated[str, Field(description="Exact event id as recorded in the trace, e.g. 'evt-001'.")]
READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}


def create_server(root: Path) -> MCPServer:
    """Build the four-tool server; ``root`` is the only directory it can read."""
    service = EvidenceService(root)
    server = MCPServer("HFM Parity Lab", version=__version__,
                       instructions="Deterministic, read-only trace evidence. Every path argument is relative to the server root "
                                    "(for root /data/traces use 'baseline.jsonl', not 'traces/baseline.jsonl'). "
                                    "Findings are observations, not proven causes: read the code before naming one.")

    @server.tool(description="Validate one JSONL trace with the shared parser and report coverage gaps.",
                 annotations=READ_ONLY)
    def validate_trace(trace_path: TracePath) -> ToolResponse:
        return _run(lambda: service.validate(trace_path))

    @server.tool(description="Compare baseline and candidate traces with the existing parity engine. "
                             "Use strict for same-contract parity, regression for deliberate old-vs-new changes.",
                 annotations=READ_ONLY)
    def compare_traces(baseline_path: TracePath, candidate_path: TracePath, mode: Mode = "strict",
                       max_findings: int = 20) -> ToolResponse:
        return _run(lambda: service.compare(baseline_path, candidate_path, mode, max_findings))

    @server.tool(description="Compact grouped overview (category, stage, field, earliest events) of a comparison.",
                 annotations=READ_ONLY)
    def summarize_findings(baseline_path: TracePath, candidate_path: TracePath, mode: Mode = "strict",
                           top: int = 5) -> ToolResponse:
        return _run(lambda: service.summarize(baseline_path, candidate_path, mode, top))

    @server.tool(description="Show stored evidence for one event id (optionally one stage). Never reruns the pipeline.",
                 annotations=READ_ONLY)
    def inspect_event(baseline_path: TracePath, candidate_path: TracePath, event_id: EventId, stage: str | None = None,
                      context: int = 1, mode: Mode = "strict") -> ToolResponse:
        return _run(lambda: service.inspect(baseline_path, candidate_path, event_id, stage, context, mode))

    return server


def _run(operation: Callable[[], ToolResponse]) -> ToolResponse:
    """Map anticipated failures to an MCP error result carrying a stable ``CODE: message``."""
    try:
        return fit(operation())
    except ToolFailure as exc:
        raise ToolError(f"{exc.code}: {exc}"[:MAX_ERROR_CHARS]) from exc


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="hfm-parity-mcp", description="Read-only local MCP server over stdio.")
    parser.add_argument("--root", type=Path, required=True, help="directory containing traces (the only readable scope)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format="%(levelname)s: %(message)s")
    if not args.root.is_dir():
        parser.error("--root must be an existing directory")
    create_server(args.root).run(transport="stdio")


if __name__ == "__main__":
    main()

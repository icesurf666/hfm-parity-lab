# MCP server and agent skill

HFM Parity Lab can expose its deterministic comparison engine to an MCP-capable
coding agent. The server is local, read-only, stdio-only and offline. It does
not connect to exchanges, run your pipeline, execute code, or read source code.
**The server supplies evidence; the agent investigates the code.**

## Install and run

From a source checkout (the package is not on PyPI yet), inside an activated virtual environment:

```bash
pip install '.[mcp]'            # optional extra: mcp>=2.3,<3 (official SDK v2)
hfm-parity-mcp --root /path/to/traces
```

`--root` is required and is the only readable scope. Clients start the server as a
subprocess without your shell's virtual environment, so register the full executable
path: `"$(command -v hfm-parity-mcp)"`. Without the extra, the
SDK, CLI and `hfm-parity` work unchanged; `hfm-parity-mcp` prints an install hint.
Stdout carries only protocol messages; diagnostics go to stderr.

## Tools

All tools return the same object: `status`, `verdict`, `summary`, `findings`,
`evidence`, `limitations`, `next_steps` (typed output schema in `tools/list`).
All declare `readOnlyHint`.

**Path semantics.** Every `*_path` argument is relative to `--root`, which is implied. With
`--root /project/traces` the file `/project/traces/baseline.jsonl` is `baseline.jsonl` and
`/project/traces/runs/live.jsonl` is `runs/live.jsonl`; `traces/baseline.jsonl` is wrong. This is
stated in each parameter's schema description. A wrong path is never "fixed up" silently: the
`TRACE_NOT_FOUND` error says the path is root-relative, names a redundant leading root directory
name, and lists up to 10 `.jsonl` files found below the root (symlinked directories are not followed).
Summaries are stateless: pass the two traces each time.

| Tool | Inputs | Key output |
|---|---|---|
| `validate_trace` | `trace_path` | `valid`, counts per stage, metadata, duplicate keys, coverage gaps, `strict_comparison_possible` (false while any evidence needed for a verified strict `PASS` is missing; it is necessary, not sufficient) |
| `compare_traces` | `baseline_path`, `candidate_path`, `mode` (`strict`\|`regression`), `max_findings` (1-20) | verdict, `deterministic_parity_verified`, matched/unmatched counts, `first_divergence`, `findings_by_category`, `truncated`, `unverifiable` |
| `summarize_findings` | same paths, `mode`, `top` (1-20) | totals, `by_category`/`by_stage`/`by_field` over **all** findings, `affected_events`, `earliest_events`, `verdict_meaning` |
| `inspect_event` | paths, `event_id`, optional `stage`, `context` (0-4), `mode` | baseline/candidate observations, per-feature differences with unit and availability time, decision comparison, run metadata, other stages, neighbouring events, `missing_information` |

`evidence_kind` on a finding is `verified_invariant_violation` (e.g. feature
available after the decision), `observed_mismatch` (values differ, cause unknown)
or `missing_evidence`. Strict `PASS` is the only verified-parity result;
regression mode never sets `deterministic_parity_verified`.

**Errors** are MCP error results (`isError`) whose text starts with a stable
code: `INVALID_PATH`, `TRACE_NOT_FOUND`, `TRACE_INVALID`, `TRACE_UNREADABLE`,
`EVENT_NOT_FOUND`, `INVALID_ARGUMENT`; schema violations (bad `mode`, missing
arguments) are rejected by the SDK. Messages never include absolute paths.

## CSV logs with an agent

The MCP server intentionally has no CSV-import tool. The existing four tools remain trace-only and read-only; adding
CSV parsing, mapping files and report writing to the server would duplicate the CLI boundary. For two CSV signal logs,
let the coding agent inspect headers and a small local sample, make the identity/type assumptions explicit, then run
`hfm-parity quick-diff` through its normal terminal capability. The agent skill documents this workflow.

CSV comparison is diagnostic: it may show an observed divergence, but it cannot fabricate source-event provenance,
input hashes or a model version. Raw exchange OHLCV/trade/book exports require strategy instrumentation before they
can answer an execution-parity question. See [CSV Quick Compare](csv-quick-compare.md).

**`first_divergence`** is the earliest recorded difference at an event (see
[comparison semantics](comparison-semantics.md)); a duplicate or ordering finding later in the trace does not outrank it.

**Response size.** Every result is limited as a whole, not per field: its pretty-printed JSON is at most 56 KiB
(the SDK sends it twice, structured and as text, so a call stays under 128 KiB on the wire; error text is at most
1000 characters). Findings are returned in report order, at most 20, and values are shortened first. When anything is
shortened the result carries `truncation` (a list of what was cut, e.g. "returned 3 of 40 findings in report order");
`summary` keeps exact totals (`total_findings`, counts by category, stage and field). Use `inspect_event` for one
event's detail. Trace *reading* limits are separate (32 MiB, 512 KiB/line, 100k observations, 100-digit integers, 16
nesting levels). No pagination, no report-file import, no clock conversion.

## Security and privacy

Read-only: no writes, subprocesses, network, or evaluation of trace content.
Paths must be relative, free of `..`, NUL and URL schemes, and are resolved
(following symlinks) to a regular file strictly below `--root`. Keep the root to
a trace-only directory. The server sends nothing anywhere, but the connected AI
client processes tool results under its own privacy policy.

## Claude Code

```bash
claude mcp add --transport stdio hfm-parity -- "$(command -v hfm-parity-mcp)" --root /path/to/traces
claude mcp list                         # hfm-parity should be connected
mkdir -p ~/.claude/skills && cp -R skills/hfm-parity-debug ~/.claude/skills/   # or <project>/.claude/skills/
```

Add `--scope project` to share the entry through a `.mcp.json`; avoid committing machine-specific
absolute paths there. Docs: [MCP](https://code.claude.com/docs/en/mcp), [Skills](https://code.claude.com/docs/en/skills).
Verified with Claude Code 2.1.187 (headless): see [the observed runs](demo/transcript-claude-code.md).
Example: *"Backtest and live disagree. Traces are in the root. Find the first divergence and the code cause."*

## Codex

```bash
codex mcp add hfm-parity -- "$(command -v hfm-parity-mcp)" --root /path/to/traces
codex mcp list
mkdir -p ~/.agents/skills && cp -R skills/hfm-parity-debug ~/.agents/skills/   # or <repo>/.agents/skills/
```

Equivalent `~/.codex/config.toml`: `[mcp_servers.hfm-parity]` with
`command = "hfm-parity-mcp"` and `args = ["--root", "/path/to/traces"]`.
In Codex run `/skills` to confirm discovery. Docs: [MCP](https://developers.openai.com/codex/mcp),
[Skills](https://developers.openai.com/codex/skills). Setup commands were checked
against those pages; **Codex itself was not installed here, so it is unverified end to end.**

## The skill

`skills/hfm-parity-debug/` (`SKILL.md` + `references/`) is the single canonical
copy for both clients. It activates when two runs of a decision pipeline
disagree and drives: understand → find traces → instrument if needed
(`TraceRecorder`) → check comparability → compare → inspect first divergence →
read the code → minimal fix + regression test → honest report. It needs read
access to the repo, the four MCP tools, and edit rights only if you approve a fix.

## Reproducible example

`examples/synthetic_pipeline/` (synthetic; no HFM data) has two feature modules
where `run_frac` means `longest_run / n_trades` in the backtest but
`buy_volume / total_volume` in the defective live module.

```bash
python examples/mcp_client_demo.py     # real stdio MCP client (needs a source checkout): validate, compare, summarize, inspect, fixed PASS
python -m pytest examples/synthetic_pipeline   # regression test for the fix
```

## Troubleshooting

- `hfm-parity-mcp` asks for the extra → `pip install '.[mcp]'` from the source checkout.
- `TRACE_NOT_FOUND` → the path is relative to `--root`; `traces/x.jsonl` under root `traces` is wrong.
- Server not listed → run the command by hand; it should wait silently on stdin.
- `NOT_COMPARABLE` → config/model/schema/input/clock differ; fix the metadata, or use regression mode on purpose.
- `UNVERIFIABLE` → evidence is missing (`data_source`, `input_hash`, `decision_ts_ns`, ...); `summary.unverifiable` and
  `validate_trace` coverage gaps say what to record. It is neither a pass nor a failure.

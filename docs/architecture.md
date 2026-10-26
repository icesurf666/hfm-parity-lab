# Architecture

HFM Parity Lab deliberately uses a small set of direct layers. Comparison logic
does not know about files, the CLI, or the browser; adapters do not decide
parity.

```text
                 ┌── adapters.jsonl / recorder / reports
 Domain + application.compare (one parity engine)
                 ├── interfaces.cli ────────────> CI, terminal, HTML/JSON report ──> static React viewer
                 └── interfaces.mcp_* ──(stdio)──> Claude Code / Codex  (+ skills/hfm-parity-debug)
```

Every interface calls the same `read_jsonl` and `compare_runs`; the React viewer
only renders a Python-produced report. MCP modules never compare events.

## Module boundaries

| Module | Responsibility | Does not do |
|---|---|---|
| `domain.models` | Immutable trace/report models and enums | IO, JSON, CLI |
| `domain.align` | Exact `(event_id, stage)` alignment, ambiguity, chronological position, per-stage order | Value comparison |
| `domain.values`, `domain.checks` | Pure typed checks and causality rules | Filesystem access |
| `domain.schema` | The trace contract (validators, limits) shared by reader and recorder | IO |
| `application.compare` | Orchestration and verdict precedence | Parsing or rendering |
| `adapters.jsonl` | Bounded UTF-8 JSONL parsing | Business verdicts |
| `adapters.recorder` | New-trace writing | Thread safety or durability guarantees |
| `adapters.reports` | Escaped HTML and JSON export | Recomputing findings |
| `interfaces.cli` | Arguments, exit codes, packaged demo | Comparison rules |
| `application.summary` | Grouping/earliest-event aggregation of a report | Comparison |
| `interfaces.mcp_paths` | The only place tool paths are resolved (relative, below root) | Reading files |
| `interfaces.mcp_service`, `mcp_views`, `mcp_notes` | Bounded evidence shaping and plain-language notes | Parsing alternatives or comparison rules |
| `interfaces.mcp_server` | MCP SDK v2 stdio tool registration | Domain logic or filesystem policy beyond its service |
| `web/` | Read-only rendering of a Python report | Its own parity algorithm |

## Data flow

1. A recorder writes one `run` record followed by `observation` records, or the
   JSONL reader validates a supplied trace with size limits.
2. `compare_runs` compares run metadata, builds exact indexes, then walks
   deterministically sorted keys.
3. A safely aligned pair is checked for provenance, timestamps, features,
   score, decision, and state. A duplicate key receives no field-level claim.
4. The application layer derives a verdict from classifications and mode.
5. Writers serialize the finished `ComparisonReport`; the viewer only renders it.

## Important trade-offs

- There is no fuzzy time matching: a false pair is worse than an explicit
  missing event.
- There is no clock conversion: timestamps without an external mapping are not
  comparable.
- `TraceRecorder` flushes every record but does not promise atomic multi-record
  durability and is not thread-safe.
- The API uses frozen dataclasses and plain functions instead of a plugin
  hierarchy because v0.1 has no demonstrated need for a generic framework.

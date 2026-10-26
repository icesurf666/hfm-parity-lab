# CSV Quick Compare implementation report

## Scope and architecture

CSV Quick Compare is a diagnostic adapter, not a second comparator. `adapters/csv_quick.py` validates a bounded,
UTF-8 CSV and an explicit JSON mapping, produces in-memory `Trace` objects, and calls `application.compare.compare_runs`.
Existing event alignment, type-safe nested comparison, strict/regression verdict precedence, report serialization and
viewer schema therefore remain the single source of truth.

The public Python surface is `CsvMapping`, `load_csv_mapping`, `csv_trace`, and `compare_csv`. The CLI surface is:

```bash
hfm-parity quick-diff BACKTEST.csv LIVE.csv --mapping mapping.json \
  [--output report.html] [--json-output report.json]
```

No MCP CSV tool was added. The four existing MCP tools stay read-only and JSONL-focused; a CSV MCP tool would duplicate
mapping and output-boundary behavior already provided by the CLI. The agent skill tells Claude Code/Codex to inspect CSV
headers and a small local sample, make identity/type assumptions explicit, run the CLI, and only then inspect source.

## Mapping and evidence contract

A mapping declares exact baseline/candidate columns, an event identity, canonical feature names, and explicit scalar
types. It can set a constant stage or declare a stage column. Identity is either one string event-id column or an ordered
explicit composite; duplicate identities, empty identity parts, duplicate headers, missing columns, malformed values,
invalid Unicode, oversized files and excessive rows are rejected before comparison.

There is no numeric type inference. Integer parsing preserves arbitrary supported integer precision and rejects `001`;
boolean and integer stay distinct; float parsing rejects non-finite values. An empty string remains a string unless the
mapping explicitly marks a typed field `nullable`, where it becomes JSON `null`.

The CSV adapter never fabricates an input hash, source provenance, a model version or a data source. Thus, equal mapped
CSV observations normally yield `UNVERIFIABLE` in strict mode. An observed mismatch yields `FAIL`. A strict verified
`PASS` still requires genuine instrumentation through `TraceRecorder`. Raw exchange OHLCV, trade and book exports are
not strategy execution evidence and Quick Compare does not reconstruct signals from them.

## External example and observed result

`examples/csv_quick/` contains only synthetic data: independently understandable `backtest.csv`, `live.csv`,
`mapping.json`, and `make_csv_logs.py`. The logs use different source column names and intentionally diverge.

Running the documented command produced:

```text
HFM Parity Lab — Quick Compare
Aligned observations: 3; findings: 15
First observed difference: evt-001 / decision / run_frac
Parity verification: not verified; CSV mapping does not establish unrecorded provenance.
```

The JSON/HTML output is the existing report format, so the existing viewer consumes it without a CSV-specific path.

## Security and limits

The adapter uses Python's standard CSV reader; it performs no network access, telemetry, evaluation of formulas,
strategy execution or report upload. It applies the existing 32 MiB file and 100,000-row ceilings, rejects malformed
CSV/mapping input with row-and-column context, and report outputs retain the existing relative-path and HTML escaping
rules. Mapping JSON is data, not code.

## Verification and limitations

The focused CSV tests cover valid mappings, renamed columns, large integers, mismatches, missing events, reordered
input, BOM/quoted cells, composite identity, invalid/missing/duplicate identities and headers, invalid Unicode,
boolean/integer confusion, empty-string versus explicit null, CLI report generation, regression behavior, and the
absence of a false verified PASS. Actual local verification: **242 Python tests passed**, Ruff and strict mypy were
clean, all handwritten source files met the 200-line check, viewer tests/build passed, and wheel/sdist builds passed.
A fresh wheel installation generated the CSVs through `make_csv_logs.py`, ran Quick Compare, wrote HTML/JSON and the
existing viewer parser accepted the resulting `FAIL` report. The sdist included all four CSV-example files.

The implementation does not infer mappings, parse nested JSON embedded in CSV cells, support arbitrary CSV dialects,
or prove that a selected composite key represents the same market event. It has not been run through a real Claude Code
or Codex client in this change; the documented skill workflow was reviewed and existing MCP stdio tests remain the
coverage for the MCP server.

## Git state

No commit, tag, remote, push, publication or deployment is part of this work. The repository retains the pre-existing
uncommitted audit/P0 remediation changes plus this CSV onboarding implementation.

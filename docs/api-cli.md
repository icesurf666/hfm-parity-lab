# Python SDK and CLI

## Public Python API

For the ordinary workflow, import only from `hfm_parity` (typed package, `py.typed`;
`hfm_parity.__version__` reports the installed version). Result types such as `ComparisonReport`,
`Finding`, `Classification` and `ResultState` are exported there too:

```python
from hfm_parity import compare_runs, read_jsonl, write_html, write_json

report = compare_runs(read_jsonl("baseline.jsonl"), read_jsonl("candidate.jsonl"))
print(report.state, report.first_divergence)
write_html(report, "report.html")
write_json(report, "report.json")
```

`read_jsonl`, writers, and `TraceRecorder` accept `str` or `pathlib.Path`.
`read_jsonl` raises `TraceValidationError` for invalid or oversized JSONL.
`compare_runs` accepts immutable `Trace` objects and an optional
`CompareConfig`. Writers require a relative path within the current working
directory; absolute paths, `..`, and symlink escapes are rejected.

For instrumentation, use `RunMeta`, `TraceRecorder`, and `feature`. Strict *verified* parity needs
`data_source` in `RunMeta` and `input_hash` on every observation (see [comparison semantics](comparison-semantics.md)).
Every record is validated with the reader's rules before it is written; invalid input (empty ids, non-integer
timestamps, non-finite or unsupported values, over-limit sizes) raises `TraceValidationError` and writes nothing.
`TraceRecorder` is a context manager; it never overwrites an existing file, is
not thread-safe, and flushes after each record. A complete executable example:

```bash
python examples/sdk_compare.py examples/baseline.jsonl examples/candidate.jsonl \
  --output-dir sdk-report
```

## CLI

```text
hfm-parity validate TRACE
hfm-parity diff --baseline TRACE --candidate TRACE --output REPORT.html
                [--json-output REPORT.json] [--abs-tol N] [--rel-tol N]
                [--mode strict|regression]
hfm-parity demo
```

## CSV Quick Compare

```bash
hfm-parity quick-diff BACKTEST.csv LIVE.csv --mapping mapping.json \
  [--output report.html] [--json-output report.json] [--abs-tol N] [--rel-tol N] [--mode strict|regression]
```

This reads bounded UTF-8 signal/execution CSVs with an explicit mapping, converts them to in-memory traces and calls
the ordinary comparison service. It does not write JSONL, execute a strategy or infer types. Output files use the same
safe relative-path rule as `diff`. See [CSV Quick Compare](csv-quick-compare.md) for the mapping format and its
provenance limitation.

| Code | Meaning |
|---:|---|
| 0 | PASS, or a successful intentional demo |
| 1 | FAIL: observations differ |
| 2 | NOT_COMPARABLE or UNVERIFIABLE |
| 3 | Invalid trace or CSV input |
| 4 | IO, invalid argument, or unexpected boundary error |

`demo` writes `parity-demo.html` and `parity-demo.json` in the current working
directory and intentionally contains a synthetic mismatch. `validate` does not
write a report. `diff` requires relative output names, so first change into the
directory where you want reports saved.

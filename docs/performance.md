# Representative performance measurement

This is not a latency target or marketing benchmark. It is one reproducible
sanity check at the maximum supported record count, run on 2026-10-25.

| Parameter | Value |
|---|---|
| Host | macOS 26.3, arm64 |
| Python | 3.14.6 |
| Shape | 100,000 observations per trace; one stage and one finite feature |
| Result | Identical traces, `PASS`, 100,000 aligned |
| Wall time | 1.833 s |
| Peak Python allocations | 42.21 MiB (`tracemalloc`, comparison phase only) |

Method: both immutable in-memory traces were constructed before
`tracemalloc.start()`, then one `compare_runs` was measured. The number excludes
JSON parsing, trace construction, operating-system memory, and frontend work.
It shows no confirmed quadratic path in exact indexing for this representative
100k shape. Repeat it on another Python version or host before making a
performance decision.

**Re-measured after the audit remediation (2026-10-25, Apple M5, Python 3.14.6):** two traces of 100,000 observations
(2 features each, 30.6 MiB, compact JSON): parsing both 1.7 s; `compare_runs` 0.42 s (identical) and 0.87 s (every
observation differs, 100,001 findings); peak process RSS 289 MiB and 437 MiB; each MCP call 2.0-2.5 s because it re-parses
both traces. Observations of about 400 bytes or more (three features) exceed the 32 MiB file limit before reaching 100,000.

The reader additionally limits public JSONL to 32 MiB, 512 KiB per line, and
100,000 observations so malformed input cannot become an unbounded parse.

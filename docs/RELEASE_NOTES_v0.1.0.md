# HFM Parity Lab v0.1.0

The first public release of a small offline tool that compares two versioned
JSONL traces and localizes the first observable recorded difference.

## Included

- `hfm-parity validate`, `diff`, and a reproducible `demo`;
- `TraceRecorder` with no runtime dependencies;
- strict parity and explicitly marked regression mode;
- HTML/JSON reports and an optional static viewer;
- synthetic fixtures, an external recorder example, and adversarial tests;
- an optional read-only MCP server (`hfm-parity-mcp`) and the `hfm-parity-debug` agent skill
  for Claude Code and Codex, with a reproducible synthetic example.

## Release-slice changes

- Removed real and derived HFM numerical artifacts.
- Clearly labeled all public examples as synthetic.
- Added an independent install → record → diff → viewer workflow to the README.
- Added bounded JSONL input plus metadata and clock-domain checks.

## Important limits

A strict PASS checks supplied comparable records only. It does not prove another
recorder correct, establish causality or economic value, or secure a production
system. Regression mode is never called deterministic parity.

## Strict parity contract (behaviour to know)

A verified strict `PASS` now needs recorded evidence: `data_source` in the run record and `input_hash` on every
observation (plus `model_version` when `model_score` is recorded). Without it the verdict is `UNVERIFIABLE`.
Differing `symbol`/`venue`/`data_source` are `NOT_COMPARABLE`; integers are compared exactly; event order within a stage is
compared; MCP results have a total size budget. Details: [comparison semantics](comparison-semantics.md).

## Not included

Nothing is published to PyPI in v0.1.0; install from a source checkout. See
[final-release-audit.md](final-release-audit.md) for the verification record.

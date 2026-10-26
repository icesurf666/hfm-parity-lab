# Demo: finding a mislabelled feature

Synthetic scenario, inspired by a historical feature-definition defect. It uses
no market data and nothing from the private HFM research repository.

**Problem.** A backtest and a live-style pipeline produce different decisions on the same events.
**Cause (hidden in code).** Both define `run_frac`; the backtest computes `longest_run / n_trades`,
the live module computes `buy_volume / total_volume`.

## Reproduce without an agent

```bash
python examples/synthetic_pipeline/make_demo.py --output-dir demo-traces
# defect: FAIL
# fixed: PASS
```

Committed, byte-for-byte reproducible outputs (a test regenerates and compares them):
[baseline](baseline.jsonl), [defective candidate](candidate.jsonl), [fixed candidate](candidate-fixed.jsonl),
[defect report](report-defect.html) ([json](report-defect.json)), [fixed report](report-fixed.html) ([json](report-fixed.json)).
`python examples/mcp_client_demo.py` drives the same files through the real stdio MCP server.

## With Claude Code

[transcript-claude-code.md](transcript-claude-code.md) records two real headless runs: an
investigation (agent finds the first divergence at `evt-001/features/run_frac`, reads both
implementations, explains the formula difference, proposes the fix) and a run where the fix, a
regression test and a re-recorded trace were permitted (strict comparison: `PASS`, 0 findings).
It is generated from the client logs, not written by hand. Codex was not run.

## Storyboard for a 30-45 s screen recording

No recording is shipped: capturing one needs an interactive terminal session. Record one with the
steps below and do not edit the agent's output.

1. (0-5 s) Terminal: `hfm-parity diff ...` on the two traces shows `FAIL` (the symptom: different decisions).
2. (5-12 s) Claude Code with the server connected (`claude mcp list`) and the skill installed. Type the prompt from the README.
3. (12-25 s) Let the tool calls scroll: `validate_trace`, `compare_traces`, `inspect_event`, then source reads.
4. (25-35 s) Final message: first divergence `evt-001 / run_frac 0.6 vs 0.4`, two different formulas, proposed fix.
5. (35-45 s) Apply the fix, re-record, `compare_traces` returns `PASS`. Close on the caption: *"evidence from the engine, cause from the code."*

Use a fresh directory (`make_demo.py` output only), a narrow terminal font, and check that no personal paths show.

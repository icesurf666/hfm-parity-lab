# Observed Claude Code runs (synthetic `run_frac` pipeline)

Generated mechanically from `claude -p --output-format stream-json` logs of two real headless runs on 2026-10-25;
only the tool-call list and the agent's final message are kept, paths are shortened to `<workspace>`.
Client: Claude Code 2.1.187, model reported by the session: `claude-sonnet-4-6`. Codex was not run.

Setup per run: clean directory with `bot/` (the four Python modules), `traces/` (the recorded traces),
`.claude/skills/hfm-parity-debug/` (copy of `skills/hfm-parity-debug`) and a project `.mcp.json` created with
`claude mcp add --transport stdio --scope project hfm-parity -- hfm-parity-mcp --root <workspace>/traces`.
Tools were pre-approved with `--allowedTools`; no manual intervention happened during either run.

## Run A: investigation only

Prompt: *I have a Python trading bot (code in ./bot, recorded traces already exist). Backtest and live produce different signals. Can you help me find the problem? Do not edit any files.*

Tool calls in order:

1. `Skill` {"skill": "hfm-parity-debug"}
2. `Bash` {"command": "find <workspace> -type f | sort"}
3. `Read` {"file": "bot/backtest_features.py"}
4. `Read` {"file": "bot/live_features.py"}
5. `Read` {"file": "bot/events.py"}
6. `Read` {"file": "bot/record_traces.py"}
7. `ToolSearch` (loads the four MCP tool schemas)
8. `hfm-parity:validate_trace` {"trace_path": "baseline.jsonl"}
9. `hfm-parity:validate_trace` {"trace_path": "candidate.jsonl"}
10. `hfm-parity:compare_traces` {"baseline_path": "baseline.jsonl", "candidate_path": "candidate.jsonl", "mode": "strict"}
11. `hfm-parity:inspect_event` {"baseline_path": "baseline.jsonl", "candidate_path": "candidate.jsonl", "event_id": "evt-001", "stage": "features"}

Observed: no tool errors or retries; the agent did not call `summarize_findings` although the skill lists it; its first `Bash` call was a read-only `find` listing.

Final message of the agent:

> I now have enough evidence to confirm the root cause from the code. Let me verify the numbers manually against the input data.
> 
> For `evt-001`: `(("B",1), ("B",1), ("B",1), ("S",6), ("B",1))` — 5 trades, quantities 1,1,1,6,1.
> 
> **Backtest** (`backtest_features.py:7–15`): counts the *longest run of same-side trades* divided by total trade count.
> - Runs: BBB (3), S (1), B (1) → longest = 3, total = 5 → **3/5 = 0.6** ✓ matches baseline
> 
> **Live** (`live_features.py:7–9`): computes *buy volume / total volume* (completely ignores runs).
> - Buy qty: 1+1+1+1 = 4, total qty: 1+1+1+6+1 = 10 → **4/10 = 0.4** ✓ matches candidate
> 
> ---
> 
> ## Findings — *verified*
> 
> | | Backtest | Live |
> |---|---|---|
> | `run_frac` definition | Longest same-side run ÷ trade **count** | Buy volume ÷ total **volume** |
> | evt-001 | 0.6 → **BUY** | 0.4 → **HOLD** |
> | evt-002 | 0.5 | 0.333… |
> | evt-003 | 0.75 | 0.909… |
> 
> **Root cause (verified):** `run_frac` in `live_features.py` is a completely different formula from `backtest_features.py`. Both functions share the same name but measure different things — one is a streak-length ratio (ignores quantity), the other is a volume-weighted buy fraction (ignores streak structure). This is not a parameter drift or a rounding issue; it is a wholesale formula substitution.
> 
> **Downstream effect (verified):** Because live produces 0.4 on evt-001 instead of 0.6, it falls below the 0.6 threshold in `record_traces.py:31`, flipping the decision from `BUY` to `HOLD`.
> 
> **Fix:** `live_features.py:run_frac` needs to be corrected to match the backtest definition — longest same-side run divided by total trade count — or, if the volume-weighted formula was intentional, the backtest must be updated to match and the threshold recalibrated. The fix should not be made just to make the numbers match; the correct formula needs to be agreed upon first.

## Run B: fix and verification permitted

Prompt: *(same problem; the agent may fix the live code, add a regression test in ./bot, re-record with `python bot/record_traces.py live_features traces/candidate-fixed.jsonl` and compare)*

Tool calls in order:

1. `Skill` {"skill": "hfm-parity-debug"}
2. `Glob` 
3. `Read` {"file": "bot/backtest_features.py"}
4. `Read` {"file": "bot/live_features.py"}
5. `Read` {"file": "bot/events.py"}
6. `Read` {"file": "bot/record_traces.py"}
7. `ToolSearch` (loads the four MCP tool schemas)
8. `hfm-parity:validate_trace` {"trace_path": "baseline.jsonl"}
9. `hfm-parity:validate_trace` {"trace_path": "candidate.jsonl"}
10. `hfm-parity:compare_traces` {"baseline_path": "baseline.jsonl", "candidate_path": "candidate.jsonl", "mode": "strict"}
11. `hfm-parity:inspect_event` {"baseline_path": "baseline.jsonl", "candidate_path": "candidate.jsonl", "event_id": "evt-001", "stage": "features"}
12. `Read` {"file": "bot/live_features.py"}
13. `Edit` {"file": "bot/live_features.py"}
14. `Write` {"file": "bot/test_live_features.py"}
15. `Bash` {"command": "python -m pytest bot/test_live_features.py -v 2>&1"}
16. `Bash` {"command": "python bot/record_traces.py live_features traces/candidate-fixed.jsonl 2>&1"}
17. `hfm-parity:compare_traces` {"baseline_path": "baseline.jsonl", "candidate_path": "candidate-fixed.jsonl", "mode": "strict"}

Observed: no tool errors or retries; `Edit`, `Write` and `Bash(python:*)` were allowed in this scratch workspace only.

Final message of the agent:

> **PASS** — zero findings, full parity restored across all 6 observations.
> 
> ---
> 
> ## Summary
> 
> **Root cause** *(verified)*: `live_features.py::run_frac` computed **buy-volume fraction** (`buy_volume / total_volume`) instead of the intended **longest same-side run fraction** (`longest_run / total_trades`). These formulas agree only by accident; on `evt-001` the live code produced `0.4` vs the correct `0.6`, flipping the BUY decision to HOLD.
> 
> **What changed**:
> 
> | File | Change |
> |---|---|
> | `bot/live_features.py` | Replaced buy-volume formula with the correct longest-run logic (matching `backtest_features.py`) |
> | `bot/test_live_features.py` | New regression test — asserts parity with backtest on all shared events, plus three known-value checks |
> 
> **Trace comparison**: `candidate.jsonl` (before) → `FAIL` with 3 feature mismatches and 1 decision mismatch; `candidate-fixed.jsonl` (after) → `PASS` with 0 findings.

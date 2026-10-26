# Synthetic `run_frac` pipeline (demo)

A fully synthetic example, inspired by a historical feature-definition defect.
It contains no market data and nothing from the private HFM repository.

| File | Role |
|---|---|
| `events.py` | Shared input events (identical for both runs) |
| `backtest_features.py` | Reference: `run_frac = longest_consecutive_run / n_trades` |
| `live_features.py` | **Deliberately defective** (unlabelled in the source): `run_frac = buy_volume / total_volume` |
| `live_features_fixed.py` | Corrected live implementation |
| `record_traces.py` | Runs a feature module and records a trace with `TraceRecorder` |
| `test_run_frac.py` | Regression test for the feature definition |

```bash
python examples/synthetic_pipeline/record_traces.py backtest_features traces/baseline.jsonl
python examples/synthetic_pipeline/record_traces.py live_features traces/candidate.jsonl
python examples/synthetic_pipeline/record_traces.py live_features_fixed traces/candidate-fixed.jsonl
hfm-parity diff --baseline traces/baseline.jsonl --candidate traces/candidate.jsonl --output traces/report.html
```

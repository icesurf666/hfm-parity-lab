# CSV Quick Compare

This is a fully synthetic signal-log example. It compares recorded strategy observations; it does
not reconstruct a strategy from OHLCV, trades or order-book data.

```bash
cd examples/csv_quick
python make_csv_logs.py
hfm-parity quick-diff backtest.csv live.csv --mapping mapping.json \
  --output report.html --json-output report.json
```

The first observed difference is `evt-001 / decision / run_frac`. `backtest.csv` calls the column
`run_frac`; `live.csv` calls it `run_fraction`. `mapping.json` makes that correspondence explicit.
The two CSVs deliberately disagree on that feature, the score and the decision.
`make_csv_logs.py` is the paired synthetic implementation to inspect after the report identifies the field.

The command reports `FAIL`, not a strict verified result. CSV rows do not establish that both
pipelines consumed identical source events, model versions or inputs. Add `TraceRecorder` at the
execution boundary when full strict-parity evidence is needed.

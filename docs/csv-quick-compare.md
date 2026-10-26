# CSV Quick Compare

Quick Compare is the shortest path from two strategy **execution or signal logs** to an HFM Parity Lab report.
It accepts UTF-8 CSV, maps each side's columns explicitly into the existing trace schema, and then calls the normal
comparison engine. It does not reimplement alignment, value comparison or verdicts.

## Run the bundled example

```bash
pip install .
hfm-parity quick-diff examples/csv_quick/backtest.csv examples/csv_quick/live.csv \
  --mapping examples/csv_quick/mapping.json --output report.html --json-output report.json
```

The generated files are synthetic. The command exits `1` because `evt-001` has an observed `run_frac` mismatch;
the two CSVs call the source columns `run_frac` and `run_fraction`. The report also records the downstream score and
decision differences. Open `report.html` or load `report.json` in the local viewer.

## Mapping format

Mappings are UTF-8 JSON and are intended to live beside the CSV exports. Every mapped value has an explicit type:
`string`, `boolean`, `integer`, or `float`. There is no type inference.

```json
{
  "identity": {"event_id": {"baseline": "event_id", "candidate": "event_id", "type": "string"}},
  "stage": {"default": "decision"},
  "features": {
    "run_frac": {"baseline": "run_frac", "candidate": "run_fraction", "type": "float", "unit": "ratio"}
  },
  "model_score": {"baseline": "score", "candidate": "prediction", "type": "float"},
  "decision": {"baseline": "decision", "candidate": "signal", "type": "string"}
}
```

`identity.event_id` is the preferred exact key. When no durable identifier exists, use explicit composites:

```json
"identity": {"composite": {"baseline": ["symbol", "timeframe", "bar_ts"],
                              "candidate": ["ticker", "interval", "timestamp"]}}
```

Composite parts are preserved as strings and encoded without rounding or fuzzy matching. Duplicate keys and blank
identity parts are rejected. Selecting identity columns is a user-supplied alignment assumption, not proof that the
two rows arose from the same market input.

## Conversion and limits

- UTF-8 (including a BOM) and normal quoted CSV cells are supported.
- Headers must be unique and every mapped column must exist.
- Integers are parsed exactly; `001` is rejected as an integer, and `true` is not an integer.
- Float conversion rejects `NaN` and infinities. Empty text remains an empty string for a string mapping; for another
  type it fails unless the mapping sets `"nullable": true`, in which case an empty cell is JSON `null`.
- CSVs are bounded by the trace limits: 32 MiB, 100,000 rows, and bounded row fields. No data is uploaded or executed.

## What the verdict proves

Quick Compare is an observational diagnostic. It can show that mapped values match or differ and identify the first
recorded difference. It never invents `input_hash`, a source event, model version or data source merely because a CSV
has a row. Therefore matching CSVs normally return `UNVERIFIABLE` in strict mode; a discrepancy returns `FAIL`.

Use `TraceRecorder` at ingestion, feature and decision boundaries when you need a genuinely verifiable strict parity
claim. Raw Binance trades, klines and book updates are market observations, not strategy execution evidence: Quick
Compare will not fabricate features, predictions or decisions from them.

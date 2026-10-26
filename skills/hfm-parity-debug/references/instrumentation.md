# Instrumenting a pipeline with TraceRecorder

Use only the public API (the installed `hfm_parity` package):

```python
from hfm_parity import RunMeta, TraceRecorder, feature

meta = RunMeta(run_id="live-2026-01-01", schema_version="1.0", pipeline_version="app@1.4",
               feature_schema_hash="features-v3", config_hash="<hash of effective config>",
               clock_domain="unix_epoch_ns", data_source="<where the input events come from>",
               model_version="model-7")  # model_version only if a model_score is recorded
with TraceRecorder("traces/live.jsonl", meta) as trace:      # refuses to overwrite
    trace.record(event_id, "features", sequence=n, source="feed", event_ts_ns=ts,
                 input_hash=hash_of_raw_input, decision_ts_ns=now_ns,
                 features={"run_frac": feature(value, "ratio", available_at_ns=ts)})
    trace.record(event_id, "decision", sequence=n + 1, ..., model_score=score, decision="BUY")
```

Rules:
- `event_id` must be identical for the same logical event in both runs.
- Record after the value is computed; do not change what is computed.
- Fill `data_source`, `input_hash`, `available_at_ns` and `decision_ts_ns` honestly; absent
  evidence makes a strict comparison `UNVERIFIABLE` rather than passing it. Never invent a hash.
- Record observations in processing order: order within each stage is compared.
- Values must be JSON types (int, finite float, str, bool, None, list, dict). The recorder raises
  `TraceValidationError` otherwise; convert NumPy scalars first.
- Both runs must share `pipeline_version`, `config_hash`, `feature_schema_hash`,
  `model_version` and `clock_domain` for a strict comparison.
- Write traces to a directory you will give to the server as `--root`.

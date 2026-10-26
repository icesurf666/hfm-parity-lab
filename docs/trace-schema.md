# Trace schema v1

A trace is UTF-8 JSONL. The first record is exactly one `run` record; every
later record is an `observation`. `TraceRecorder` and `read_jsonl` share one validator
(`hfm_parity.domain.schema`): whatever the recorder accepts, the reader accepts with the same values,
and what the reader rejects the recorder refuses with `TraceValidationError` before writing anything.

**Limits** (reader and recorder): 32 MiB per file, 512 KiB per line, 100,000 observations, integers of at most
100 digits, values nested at most 16 levels. The byte limit usually binds first: a compact observation with two
features is about 300 bytes, so about 100,000 of them fit; larger records reach 32 MiB sooner.

```json
{"record_type":"run","run_id":"replay-1","schema_version":"1.0","pipeline_version":"abc","feature_schema_hash":"def","config_hash":"123","clock_domain":"unix_epoch_ns","data_source":"synthetic-feed-v1"}
{"record_type":"observation","event":{"id":"evt-1","sequence":1,"source":"wal","event_ts_ns":1,"input_hash":"sha256"},"stage":"features","features":{"run_frac":{"value":0.8,"unit":"ratio","available_at_ns":1}},"model_score":0.7,"decision":"BUY","decision_ts_ns":2}
```

## Contracts

- `event.id` plus `stage` is the exact alignment key. The tool never performs
  implicit nearest-time matching.
- `sequence` gives deterministic ordering and is checked for decreases within
  a trace.
- `input_hash` should identify raw input consumed by both observations. A
  mismatch prevents a strict deterministic parity claim.
- Features preserve a typed `value`, a `unit`, and the timestamp at which the
  value became available.
- `clock_domain` declares timestamp semantics. A monotonic and an epoch trace
  require an explicit external mapping and are not automatically aligned.
- Required run fields: `run_id`, `schema_version`, `pipeline_version`,
  `feature_schema_hash`, `config_hash`, and `clock_domain`. Optional strings:
  `model_version`, `venue`, `symbol`, and `data_source` (the last one is required for *verified* parity).
- Required observation fields: `event.id` and `stage`. Optional event fields:
  `sequence`, `source`, `event_ts_ns`, and `input_hash`. Optional observation
  fields: `features`, `model_score`, `decision`, `decision_ts_ns`, and
  `state_hash`.
- Timestamps and `sequence` are integers or null. A boolean is never an integer.
- **Accepted value types** for a feature value, `model_score` and `decision`: `null`, bool, int, finite float,
  string, list and string-keyed object (nested at most 16 levels). Tuples, sets, bytes, NumPy scalars and
  non-finite floats are rejected, never silently coerced: convert them first (`int(x)`, `float(x)`, `list(x)`).
  Strings in optional run metadata and the identity fields must be non-empty if given.

## What strict verification needs recorded

A trace can be valid yet not *verifiable*. For a strict `PASS` record: `data_source` (origin of the input data) in the
run record; `input_hash` (and ideally `source`) on every observation; `decision_ts_ns` and `available_at_ns` on features;
`model_version` when `model_score` is recorded; `symbol`/`venue` when the pipeline has a market identity (both runs or neither).
See [comparison semantics](comparison-semantics.md) for the exact verdict for each gap.

## Missingness and compatibility

An absent feature differs from a present feature with `value: null`. The JSONL
reader and recorder reject `NaN` and infinities because they are not portable
JSON. Unknown fields are ignored by the v1 reader and must not carry comparison
semantics.

With strict metadata, the default, differences in config, feature schema,
pipeline, model version, or declared identity (`symbol`, `venue`, `data_source`) yield `NOT_COMPARABLE`. The report still lists
observable differences but does not claim a deterministic defect.

`schema_version` is compared as declared metadata. A future parser may add a
supported schema version; v1 consumers must not assume unknown fields alter
current semantics.

## Comparison modes

`strict` is the default and the only mode in which
`deterministic_parity_verified: true` can appear. Metadata incompatibility
prevents that claim.

`regression` is for deliberate old-versus-new comparison. It reports metadata
differences and sets `mode: "regression"` plus
`deterministic_parity_verified: false`, even if individual feature values match.

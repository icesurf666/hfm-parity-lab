# Reading results

| Verdict | Meaning | You may say |
|---|---|---|
| `PASS` (strict) | No recorded difference; parity verified for this evidence | "Parity verified for the recorded events" |
| `PASS` (regression) | No difference found; `deterministic_parity_verified` is false | "No regression observed", not "identical" |
| `FAIL` | Recorded differences between aligned events | "Observed mismatch at <event/stage/field>" |
| `NOT_COMPARABLE` | Config, model, schema, declared symbol/venue/data source, input fingerprint or clock differ | The runs cannot be compared as-is |
| `UNVERIFIABLE` | Evidence is missing (`data_source`, `input_hash`, decision timestamps, nothing to compare) | What is missing (see `summary.unverifiable`), not a pass or fail |

`first_divergence` is the earliest recorded difference at an event, in trace order; a later duplicate or reordering
finding does not outrank it. A result with `truncation` entries was shortened: use `inspect_event` for detail.

Finding `evidence_kind`: `verified_invariant_violation` (e.g. a feature available
after the decision), `observed_mismatch` (values differ; cause unknown),
`missing_evidence`. A mismatch is a symptom: confirm the cause in source code.

Tool errors start with a stable code: `INVALID_PATH`, `TRACE_NOT_FOUND`,
`TRACE_INVALID`, `EVENT_NOT_FOUND`, `INVALID_ARGUMENT`.

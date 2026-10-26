# Comparison semantics

## What a strict `PASS` means

`deterministic_parity_verified` is `true` only for **strict mode + `PASS`**, and it is a statement about
the *recorded and declared scope*: the aligned observations, the recorded features/score/decision/state,
and the declared run contract. It does not mean every internal behaviour was identical. A strict `PASS` requires all of:

| Requirement | Missing or violated → |
|---|---|
| Same `schema_version`, `pipeline_version`, `feature_schema_hash`, `config_hash`, same `model_version` | `NOT_COMPARABLE` |
| Same declared `symbol`, `venue`, `data_source` when both sides declare them | `NOT_COMPARABLE` |
| `data_source` declared by both runs; `symbol`/`venue` declared by both or by neither | `UNVERIFIABLE` |
| `model_version` declared by at least one run, if any `model_score` is recorded (not required for pipelines without a model) | `UNVERIFIABLE` |
| `input_hash` present on both sides of every aligned observation, and equal (`source` too, if both give one) | `UNVERIFIABLE` if absent, `NOT_COMPARABLE` if different |
| Same clock domain | `NOT_COMPARABLE` (both modes) |
| At least one aligned observation records features, a score, a decision or a state | `UNVERIFIABLE` |
| `decision_ts_ns` and feature `available_at_ns` present, no feature available after the decision | `UNVERIFIABLE` if absent, `FAIL` (`CAUSALITY_VIOLATION`) if violated |
| No missing, extra or duplicated event/stage, and the same event order within each stage | `FAIL` |
| Every compared value equal (see below) | `FAIL` |

Nothing is invented: if a recorder does not supply `data_source` or `input_hash`, the answer is
`UNVERIFIABLE` and `summary.unverifiable` (MCP) / the report findings say what to record.

## Modes

| Mode | Purpose | Verified parity possible |
|---|---|---|
| `strict` | Reproduce one declared run contract | Only on `PASS` |
| `regression` | Deliberate old-vs-new comparison | Never |

Regression mode reports contract and identity differences as findings (`FAIL`), does not demand the evidence
above (so provenance gaps do not turn it into `UNVERIFIABLE`), and always has `deterministic_parity_verified: false`.
A clock-domain mismatch is `NOT_COMPARABLE` in both modes because the engine never invents a clock mapping.

## Verdict precedence

1. No findings → `PASS`.
2. Strict and a contract mismatch (config, model, schema, input/identity), or a clock-domain mismatch → `NOT_COMPARABLE`.
3. Only missing-evidence findings → `UNVERIFIABLE`.
4. Anything else, i.e. an observed difference (possibly together with missing evidence) → `FAIL`.

`ERROR` is reserved for external boundaries; the CLI exits `3`/`4` instead of emitting a report.

## Identity, order and `first_divergence`

An observation is identified by the exact pair `event.id + stage`. Time proximity never creates identity.
A duplicate pair is ambiguous: it is reported (`EVENT_MISMATCH` error, plus an `INSUFFICIENT_EVIDENCE` warning),
the first occurrence is kept only for indexing, and no field comparison is made for it. The verdict is then `FAIL`.

**Order.** Record order in the trace is authoritative. Within each stage, the events present in both traces must
appear in the same order; one `EVENT_MISMATCH` (`field: order`) is reported per stage whose order differs.
Interleaving of different stages is not compared. `sequence`, when recorded, must match between aligned
observations and must not decrease within a trace. Reordering can therefore never produce a verified `PASS`.

**Report order.** Run-level findings first, then event-level findings by chronological position: baseline record
order, then events only the candidate has. Severity never reorders findings.

**`first_divergence`** is the earliest *event-level error* in that order (for example a feature mismatch at the first
event), regardless of whether a structural finding such as a duplicate occurs later. If the runs are `NOT_COMPARABLE`,
or no event-level error exists, it is the first finding that is not a missing-evidence warning, else the first finding.
It is the first **recorded** difference, not proof of a root cause: an earlier stage may be uninstrumented, and a
decision difference can be downstream of a feature difference. Events that exist only in the candidate are placed after
all baseline events, so an extra event early in the candidate does not appear as "first".

## Numbers, units and time

- `null`, bool, integer, float and string are distinct type classes; bool is never an integer.
- **Integers are compared exactly**, whatever their size. An integer and a float are a type mismatch, even if
  their mathematical values happen to match (`1` does not equal `1.0`).
- A tolerance applies only to two finite floats. It uses
  `|a-b| <= max(rel_tol*max(|a|,|b|), abs_tol)`, inclusively. The same rule applies to `model_score`
  and a numeric `decision` when both recorded values are floats.
- Lists compare in order and objects compare by key, recursively. The first unequal nested leaf is reported
  with its JSON-like path; a missing key differs from a key whose value is `null`.
- `0.0` equals `-0.0`; `NaN` equals `NaN` in memory (JSON cannot carry non-finite numbers).
- A unit mismatch takes priority over numeric tolerance.
- Causality is checked only when the declared clock domains match.

## What a result does not mean

`FAIL` does not identify the correct side. `PASS` covers the supplied records and declared contracts only, not
instrumentation completeness, recorder correctness, causality outside the recorded stages, or financial performance.

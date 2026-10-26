# Engineering review — 2026-10-25

The public HFM Parity Lab branch was reviewed without access to the original
HFM source. Confirmed defects are separated from deliberate v0.1 limits below.

## P1 — fix before public release

### ER-001: non-standard JSON numbers enter a trace

- **Files:** `src/hfm_parity/adapters/recorder.py:60`,
  `src/hfm_parity/adapters/jsonl.py:105` before the correction.
- **Observed behavior:** recorder used `allow_nan=True`; `json.loads` accepted
  `NaN` and `Infinity`, which are not standard JSON.
- **Why it matters:** a trace produced by the library might not load in an
  ordinary JSON tool; `NaN` semantics are not portable across producers.
- **Reproduction:** record `feature(float("nan"))`; the old file contained bare
  `NaN`.
- **Correction:** recorder and reader reject non-finite JSON values. Direct
  in-memory comparison remains defined for SDK users.
- **Verification:** focused tests reject `NaN` and `Infinity` during writing
  and parsing.

### ER-002: a different input fingerprint received the wrong strict verdict

- **Files:** `src/hfm_parity/domain/checks.py:32-34`,
  `src/hfm_parity/application/compare.py:42-58` before the correction.
- **Observed behavior:** a different `input_hash` or `source` produced
  `EVENT_MISMATCH`, then strict mode returned `FAIL` rather than
  `NOT_COMPARABLE`.
- **Why it matters:** different input is not evidence of an implementation
  regression; FAIL could be misread as a parity defect.
- **Reproduction:** compare otherwise identical observations with different
  `input_hash` values.
- **Correction:** dedicated `INPUT_MISMATCH`; strict returns
  `NOT_COMPARABLE`, regression retains diagnostic `FAIL`.
- **Verification:** tests cover both modes and prove strict PASS is impossible.

### ER-003: a relative output path could escape through a symlink

- **File:** `src/hfm_parity/adapters/reports.py:31-34` before the correction.
- **Observed behavior:** only `is_absolute()` and `..` were checked; a directory
  inside cwd could be a symlink to an external path.
- **Why it matters:** CLI could write outside cwd despite its stated path guard.
- **Reproduction:** create `out -> /tmp`, then write `out/report.html`.
- **Correction:** resolve the target and require it to remain under resolved cwd
  before writing.
- **Verification:** a symlink test and an ordinary nested-output test.

## P2 — high-value corrections

### ER-004: duplicate key overwrote an earlier observation

- **File:** `src/hfm_parity/domain/align.py:12-15` before the correction.
- **Observed behavior:** a duplicate `(event_id, stage)` was reported but the
  dictionary replaced the first observation with the last one.
- **Why it matters:** “first divergence” became uninterpretable on an ambiguous
  trace.
- **Correction:** retain the first item for deterministic indexing, mark the
  key ambiguous, and skip field-level conclusions for it.
- **Verification:** a conflicting duplicate cannot produce a false feature
  mismatch and is excluded from aligned count.

### ER-005: parser accepted bool as feature availability timestamp

- **File:** `src/hfm_parity/adapters/jsonl.py:66-67` before the correction.
- **Observed behavior:** `bool` is an `int` subclass; event timestamps excluded
  it but `available_at_ns` did not.
- **Why it matters:** `true` acquired the implicit meaning of 1 ns.
- **Correction and verification:** reject bool in every timestamp field;
  focused JSONL fixture covers it.

### ER-006: HTML report hid zero/false values and mode context

- **File:** `src/hfm_parity/adapters/reports.py:21-28` before the correction.
- **Observed behavior:** `value or "—"` rendered `0` and `False` as missing; the
  report omitted strict/regression and verification context.
- **Correction and verification:** only `None` becomes an em dash; HTML adds
  mode/verification summary and is tested with zero.

### ER-007: viewer trusted the JSON shape at runtime

- **File:** `web/src/App.tsx:3-12` before the correction.
- **Observed behavior:** fetched JSON was only cast with a TypeScript type;
  malformed data could fail during rendering.
- **Correction:** a small type guard moves malformed payload to an error state
  without recomputing Python conclusions.
- **Verification:** TypeScript build passes. No frontend test runner was added
  solely for this one guard.

### ER-008: recorder example produced an extra timestamp divergence

- **File:** `examples/record_two_traces.py:10` before the correction.
- **Observed behavior:** each trace called its own `time_ns()`.
- **Why it matters:** the example promised a feature mismatch but first reported
  an event timestamp mismatch.
- **Correction:** one timestamp is made in `main` and passed to both traces.
- **Verification:** subprocess regression test expects
  `FEATURE_VALUE_MISMATCH` first.

## P3 — recorded but not refactored

- Public dataclasses allow a manually created trace that the JSONL reader would
  reject. This is useful for the in-memory SDK and tests; parser contracts are
  documented separately.
- The viewer deliberately remains a read-only demo without a file picker or
  independent comparison logic.
- Fuzzy matching, clock conversion, and streaming are v0.1 limitations, not
  defects.

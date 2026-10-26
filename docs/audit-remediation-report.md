# Audit remediation report

Starting point: commit `225578a`. Input: the independent engineering audit of that commit (verdict *NEEDS WORK*).
All changes below are **uncommitted** in the working tree for independent review. Dates: 2026-10-25.

## P0. Nested JSON equality (post-audit correction)

An additional independent check found a release-blocking false verified `PASS`: the old scalar type check was
followed by ordinary Python equality for lists and objects. Python considers `[1] == [True]` and
`{"x": 1} == {"x": 1.0}` true, so those structurally different JSON values could pass inside a feature.

`domain/values.py` now has one recursive, type-safe comparison that returns the first unequal leaf. It distinguishes
`null`, bool, integer, float, string, list, object and a missing object key; it never uses container equality.
Only float-vs-float uses the documented tolerance. Consequently, `1` versus `1.0` is now a type mismatch in strict
comparison, both at the top level and inside JSON. Findings preserve the leaf path, types, values and key-presence
evidence. The new `test_nested_values.py` covers the six reported counterexamples, exact large integers, tolerance,
ordering and first-divergence behaviour; `test_equivalence.py` records `[1]` versus `[true]` through the SDK, CLI
and MCP service. This is a compatibility change from the prior documented mixed int/float tolerance rule.

Local verification of this correction: the prior counterexamples now fail through the SDK; the recorder-backed
SDK/CLI/MCP-service case and a real stdio-MCP case both return `FAIL` with
`deterministic_parity_verified: false`; the complete suite reports **227 passed**; Ruff, strict mypy, the 200-line
check, viewer tests/build, wheel/sdist build, and a clean-wheel installation all pass. A clean `git+file` install
also works, but necessarily installs `HEAD` (`225578a`) rather than these uncommitted changes. This correction has
**not** been approved by the independent auditor.

## A. Reproduced findings

Before changing any code I wrote regression tests for the audit's findings. Run against `225578a`'s code,
**77 of them failed** (F1 10, F3/F4 12, F5/F6 3, F7 34, F8 18) and one raised an uncaught `ValueError`; the audit's own counterexamples
(`cx.py`, Hypothesis properties, hostile MCP traces) were reproduced first.

| Finding | Original problem | Correction | Regression tests | Observed now |
|---|---|---|---|---|
| **F1** exact integers | `equal()` converted ints to `float`: `2**53+1` equalled `2**53`; `10**400` raised `OverflowError`. | `domain/values.py`: ints compare exactly, bool stays distinct, and tolerance applies only to float-vs-float. | `test_exact_numbers.py` (parametrized + Hypothesis); `test_equivalence.py` (SDK = CLI = MCP) | Distinct integers never `PASS`; huge ints neither crash nor round. |
| **F2** MCP response size | Per-container bounds only: 10 MB trace → 17.7 MB `compare_traces`, 805 KB `inspect_event`. | `mcp_views.fit`: total budget of 56 KiB (pretty JSON; ≈ 2.3× on the wire), staged shortening, tail-drop of findings, `truncation` notes, exact totals kept; error text capped at 1000 chars. | `test_mcp_budget.py` (real client, measured wire size, determinism, boundaries, error bound) | Same traces now: `compare_traces` 3.6 KB, `summarize_findings` 71.8 KB, `inspect_event` 73.9 KB on the wire (limit 128 KiB). |
| **F3** identity | `symbol`/`venue`/`data_source` never compared. | Both declared and different → `INPUT_MISMATCH` (strict `NOT_COMPARABLE`, regression `FAIL`). | `test_strict_contract.py` | BTC vs ETH run no longer verifies. |
| **F4** vacuous PASS | `None == None` counted as agreement. | Strict requires `data_source` (both), `symbol`/`venue` both-or-neither, `model_version` iff a `model_score` is recorded, `input_hash` on every aligned observation, at least one recorded output; otherwise `UNVERIFIABLE`. | `test_strict_contract.py` | See section B. |
| **F5** first divergence | Findings were ordered by discovery phase; a late duplicate outranked an earlier value mismatch; ties sorted by id string. | `domain/align.positions` (baseline record order); all event findings sorted by position; `first_divergence` = earliest event-level error. | `test_ordering.py` (incl. `evt-10` vs `evt-2`, run-level findings first) | Mismatch at `e1` is first even with a duplicate at `e9`. |
| **F6** reordering | Order was checked only through optional `sequence`. | Record order is authoritative: aligned events must appear in the same order within each stage (`field: order`). | `test_ordering.py` (incl. Hypothesis over permutations) | No permutation ever verifies. |
| **F7** recorder/reader | Recorder wrote empty ids, string `sequence`, float timestamps, empty `run_id`, oversized lines. | `domain/schema.py` is the one contract; recorder validates before writing, never writes a partial record, enforces the reader's line/file/record limits. | `test_recorder_contract.py` (20 invalid records, 4 invalid run-metadata cases, reader parity, Hypothesis round trip) | Accepted ⇒ readable with equal values and types. |
| **F8** hostile input | `RecursionError`, `ValueError` (4300-digit limit), `OverflowError` escaped; CLI `INTERNAL_ERROR`. | Reader: integer-literal limit (100 digits), non-finite float literals rejected, `RecursionError` caught at the parse boundary, value depth ≤ 16. | `test_parser_limits.py` (reader, CLI exit 3, MCP `INVALID`/`TRACE_INVALID`) | All entry points return a typed validation error. |
| **F9** viewer | Fetched only `./demo-report.json`. | `web/src/report.ts` runtime validation (also rejects an inconsistent "verified" claim); file picker, local only, 20 MiB limit, 500 findings rendered, demo/user source banner. | `web/test/report.test.ts` (7 tests, including real engine reports) | `npm test` 7/7, `npm run build` OK. |

Documentation inconsistencies (duplicate events, 100k-observation claim, "bounded" claim, viewer claim) are corrected;
`docs/comparison-semantics.md` was rewritten.

## B. Strict parity semantics

`deterministic_parity_verified` is a statement about the **recorded and declared scope**, not universal identity.
Verified strict `PASS` needs (details and table in [comparison-semantics.md](comparison-semantics.md)):
equal contracts; declared identity (`data_source` always; `symbol`/`venue` both or neither); `model_version` only when a `model_score` is
recorded; `input_hash` on both sides of every aligned observation; at least one recorded output; causality evidence; no missing,
extra, duplicate or reordered events; all values equal.
Precedence: `NOT_COMPARABLE` > `FAIL` > `UNVERIFIABLE`. Regression mode never verifies and does not demand provenance.

**Compatibility-breaking changes** (documented in the release notes): traces without `data_source` or `input_hash` now give
`UNVERIFIABLE` in strict mode (fixtures and examples declare `data_source` honestly: `synthetic-fixture`, `synthetic-events-v1`, ...);
`TraceRecorder` raises `TraceValidationError` (a `ValueError`) for input it used to write; `RunMeta` optional strings must be non-empty if given;
NumPy scalars/tuples are rejected rather than coerced; an integer and a float are now different JSON types even when
their values match; reordering within a stage is now a `FAIL`; a one-sided `source`/`input_hash` is
missing evidence rather than a mismatch; report `findings` order changed (chronological); `first_divergence` can now differ from `findings[0]`.
Design choices to review: record order is authoritative (stage interleaving is not compared); events only the candidate has are ranked after
baseline events; tolerance applies to float scores and float decisions only, never to integers, mixed numeric types, lists or objects.

## C. Architecture review

New code: `domain/schema.py` (pure validators and limits, no IO), `application` unchanged in shape. Dependency graph rechecked: `domain` imports only
`domain`; `adapters` and `application` import `domain`; `interfaces` import below them; no cycles (AST check). `compare_runs` remains the only comparison;
MCP only shapes and bounds results. Largest module 160 lines; every handwritten file ≤ 200 (check below). `jsonl.py` and `recorder.py` now share
`schema.py` instead of duplicating rules.

## D. Security

Parser: 32 MiB file, 512 KiB line, 100,000 observations, 100-digit integers, 16 nesting levels, no non-finite numbers (including `1e999`), duplicate keys
rejected; applied identically by reader and recorder. MCP: allowed-root checks unchanged (relative only, no `..`/NUL/URL, symlink-resolved containment); total
result size budget; errors bounded and without absolute paths. Trust boundary unchanged: trace strings still reach the AI client as data (bounded); the skill
says to treat them as data; one earlier injection experiment is not a guarantee. TOCTOU between path resolution and reading is unaddressed (local-attacker only).

## E. External usability (executed)

- Wheel and sdist built; wheel installed in a fresh venv: `hfm-parity demo` (FAIL, as designed), `hfm-parity-mcp` without the extra prints the install hint (exit 1), README SDK snippet prints `FAIL imbalance False`. sdist installed with `[dev,mcp]`, its bundled test suite run (section F).
- Real MCP client E2E (`examples/mcp_client_demo.py`) on regenerated strict fixtures: `FAIL` on the defect, `PASS` / `parity_verified = True` on the fix.
- Claude Code 2.1.187 (headless, model reported `claude-sonnet-4-6`), current server and skill:
  **Run A** (strict fixtures): `validate`×2 → `compare` → `summarize` → `inspect_event`; first divergence `evt-001/features/run_frac` 0.6 vs 0.4; formulas read from source and explained; no tool errors.
  **Run C** (same traces, `data_source` stripped): verdict `FAIL` (real mismatches outrank missing evidence); agent also listed `data_source` as an unverifiable gap.
  **Run D** (fixed live code, equal values, `data_source` stripped): tool verdict `UNVERIFIABLE`; the agent reported "not proven equivalent" and asked for `data_source`. Its prose was imperfect: it invented a token (`PARITY_VERIFIED`) and suspected a recorder bug (my test setup had removed the field from the files). The skill now says to quote verdicts exactly and never invent names; this wording was not re-run. One sample per scenario; not a statistical result. Codex was not run (not installed).
- Viewer: unit tests and production build only; the file-picker interaction was **not** exercised in a real browser.

## F. Test evidence (final state, Apple M5, macOS)

| Command | Result |
|---|---|
| `python -m pytest` (Python 3.14.6) | 227 passed (including P0 nested-value and real-stdio-MCP tests) |
| Same suite, `ruff` and `mypy` on Python 3.11.0 and 3.13.14 (fresh venvs, `mcp` 2.3.0) | Historical pre-P0 result: 216 passed on each; not re-run after P0 |
| `ruff check .`, `mypy src` (strict, 21 files) | clean |
| `python tools/check_file_lengths.py` | OK (longest file 161 lines) |
| `cd web && npm test && npm run build` | 7 passed, built |
| Mutation check, 28 hand-written mutants of the new mechanisms | 25 killed; 3 survived at first: two were real gaps (first_divergence vs run-level findings, error-size cap), both now killed by new tests; the third (`1e999` literal check) is equivalent because the schema rejects non-finite floats anyway |
| Audit counterexamples re-run (`cx.py` 30 cases, 10 Hypothesis properties) | every false PASS/crash case now yields the intended verdict; the two audit tests that asserted the old recorder defect now fail because the recorder correctly raises |
| Performance, 100,000 observations × 2 traces (30.6 MiB each) | parse both 1.7 s; compare 0.42 s identical / 0.87 s with 100,001 findings; peak RSS 289 / 437 MiB (was 271 / 363); each MCP call 2.0-2.5 s |

## G. Remaining issues

| Sev | Issue |
|---|---|
| P2 | Record-order authority may flag legitimate asynchronous reordering within one stage as `FAIL`; there is no order-insensitive mode (deliberately not added). |
| P2 | Viewer file picker and accessibility not verified in a browser; renders at most 500 findings. |
| P3 | Decision-before-event timestamps are still unchecked (audit F10). |
| P3 | `matched_event_keys` in MCP `compare_traces` counts duplicate keys while `comparable_events` excludes them (F13). |
| P3 | Per-observation `INSUFFICIENT_EVIDENCE` warnings for missing decision timestamps can be numerous in the engine (MCP bounds them). |
| P3 | Shallow immutability of `Observation.features`/`Finding.evidence`; missing file vs invalid file share one error type (F18). |
| P3 | Some source lines are long (up to 539 characters) (F15). |
| P3 | CI changes (3.11/3.13 matrix, `npm test`) have never run on GitHub; Codex end to end and Windows/Linux unverified. |
| P3 | Residual TOCTOU on the allowed root; prompt-injection resistance of any client is not guaranteed. |

## H. Release verdict

**NOT READY FOR RELEASE UNTIL AN INDEPENDENT RE-AUDIT COMPLETE.** P0 quality gates and the external installation
surface passed locally, but the nested comparison changes the strict numeric contract. No independent auditor has
approved this correction.

## I. Git status

No commit, amend, tag, remote, push, publish or deploy occurred. `HEAD` is still `225578a`, there are no tags, remotes or stashes; all work is in the working tree.

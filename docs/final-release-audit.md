# Final release audit — v0.1.0 (earlier state)

> **Superseded in part.** This records the state at commit `225578a`, before the independent audit found false
> verified `PASS` results and unbounded MCP responses. See [audit-remediation-report.md](audit-remediation-report.md).

Date: 2026-10-25 · Python 3.14.6 (macOS arm64) · `mcp` 2.3.0 · Claude Code 2.1.187 · Node/npm as installed locally.
Everything below was re-run or re-observed in this audit; earlier reports were not trusted.

## A. Baseline (before changes)

`pytest` 82 passed, `ruff` clean, `mypy --strict` clean, file-length check OK, wheel builds, web builds.
The repository was an untracked directory inside an unrelated parent Git repository with no commits.
Stray files were present: `out.html` (written by a test into the working directory), `.coverage`, `dist/`, `build/`.

## B. Findings

| Sev | Finding | Where |
|---|---|---|
| P1 | README and `docs/mcp.md` told users to install the package by name from PyPI, where it is not published. The clone URL was a placeholder, and `hfm-parity` was not on `PATH` after `.venv/bin/python -m pip`. | README.md, docs/mcp.md, docs/api-cli.md |
| P1 | Agents wasted calls on `traces/x.jsonl` although the root already was `traces`: path arguments had no description and `TRACE_NOT_FOUND` was generic. | `interfaces/mcp_server.py`, `interfaces/mcp_paths.py` |
| P1 | sdist omitted `docs/demo/*.json|html|jsonl` and parts of the test suite that need them. | MANIFEST.in |
| P1 (found earlier, fixed, re-tested) | A parser message embedded the absolute trace path and was forwarded to MCP clients. | `interfaces/mcp_service.py` (`_clean`), `tests/test_mcp_service.py` |
| P2 | Test suite wrote `out.html` into the repository root. | `tests/test_mcp_service.py` |
| P2 | Demo was easy to "solve": the defective module said `DEFECT` and the fixed module sat in the agent workspace. Run 1 quoted it. | `examples/synthetic_pipeline/live_features.py` |
| P2 | No `py.typed`; `Finding`, `Observation`, `Feature` not exported; MCP server version hard-coded. | `src/hfm_parity/__init__.py`, `mcp_server.py` |
| P2 | Redundant or stale docs (`release-readiness.md` said "GO", two MCP reports, a second quality report). | docs/ |
| P3 | `.gitignore` lacked `.coverage`, `.DS_Store`, demo output. | .gitignore |

No P0 correctness failure was found. Engine invariants spot-checked directly: empty/empty → `UNVERIFIABLE`;
feature available after decision → `CAUSALITY_VIOLATION`; regression PASS → `deterministic_parity_verified=False`;
missing event → `FAIL`; NaN/Infinity rejected in JSONL and recorder (`docs/engineering-review.md`).

## C. Corrections

- **Install docs**: source-checkout install, `git clone <repository-url>`, activated venv, `"$(command -v hfm-parity-mcp)"`; a test fails if docs tell users to install the package by name. The missing-extra message now says `pip install '.[mcp]'`.
- **Path semantics**: every `*_path` parameter carries a schema description ("RELATIVE TO THE SERVER ROOT, e.g. `baseline.jsonl`; do not prefix the root's name"); server instructions say the same; `TRACE_NOT_FOUND` explains root-relativity, names a redundant leading root directory, and lists ≤10 `.jsonl` files found below the root (no symlink following). Nothing is auto-corrected, nothing outside the root is searched. Tests: `test_redundant_root_prefix_is_rejected_with_a_helpful_hint`, `test_not_found_lists_only_traces_inside_the_root`, schema-description assertion in `test_mcp_protocol.py`.
- **Packaging**: MANIFEST.in includes demo artifacts, tests and tools; `py.typed` shipped; public exports and `__version__` added; the server reports the package version.
- **Demo**: `make_demo.py` generates traces and both reports deterministically; `docs/demo/` holds them; `test_demo_artifacts.py` regenerates and compares byte for byte. Source is unlabelled; fixed module is not in the agent workspace.
- **Docs**: README rewritten (positioning, three quick starts, verdict table, limits); `docs/demo/README.md` (narrative, storyboard); `docs/mcp.md` updated; four redundant docs removed; `tests/test_docs.py` checks local links and private paths.

## D. Developer experience (executed in fresh venvs under a scratch directory)

1. `python -m build` produced wheel and sdist; the sdist was installed into a new venv.
2. `hfm-parity demo` from an unrelated directory wrote `parity-demo.html/json` (`FAIL … not-verified`, as designed); `import hfm_parity` resolves to site-packages, not the checkout.
3. Without the extra, `hfm-parity-mcp --root .` printed the install hint and exited 1 (no traceback).
4. README path 3 snippet ran with `python -I`: prints `FAIL imbalance False`.
5. With `[mcp]`: `make_demo.py` printed `defect: FAIL` / `fixed: PASS`; `mcp_client_demo.py` listed the four tools and completed.
6. The test suite unpacked from the sdist was run against the installed package: it exposed a test bug (fixed). Its only failure after the fix is the link check for this file, which did not yet exist at that time.

## E. Claude Code verification (real, headless `claude -p`)

Client 2.1.187, session model `claude-sonnet-4-6`. Clean workspaces with `bot/`, `traces/`, the skill under `.claude/skills/`, and a `.mcp.json` created by `claude mcp add --transport stdio --scope project`. Full logs-derived record: [docs/demo/transcript-claude-code.md](demo/transcript-claude-code.md).

- **Run A (read-only)**: server connected, skill loaded, `validate_trace` ×2 → `compare_traces` → `inspect_event`; read both modules; reported first divergence `evt-001/features/run_frac` 0.6 vs 0.4, the two different formulas, a fix, and noted that the intended formula must be agreed. No tool errors, no path retries. It did not call `summarize_findings`.
- **Run B (fix allowed)**: same discovery, then `Edit` of `live_features.py`, a new regression test (passed), re-recorded trace, `compare_traces` → `PASS`, 0 findings.
- Earlier runs on the same day (before the `TRACE_NOT_FOUND`/description changes, and with the spoiler docstring) are not used as evidence.
- Manual intervention: none. Limits: tools pre-approved via `--allowedTools`; headless only; one model; two runs, not a statistical sample. The server code was unchanged between these runs and the final commit except the wording of the missing-extra message.

## F. Codex verification

**Codex was not run** (`codex` is not installed here; I did not install it). Verified instead: current OpenAI documentation for `codex mcp add NAME -- COMMAND`, `codex mcp list`, `[mcp_servers.NAME]` in `~/.codex/config.toml`, skills in `$HOME/.agents/skills` or `.agents/skills`, required `name`/`description` frontmatter; our `SKILL.md` has exactly those fields (tested); the generic stdio MCP client E2E passes. Codex agent E2E is unverified.

## G. Security and provenance

- Scan of all 95 files that would be committed (`git ls-files -o -c --exclude-standard`): no home-directory or temp-directory paths, e-mail addresses, personal names, tokens, keys or private-key blocks (the only hit is the regex inside `tests/test_docs.py`). No file over 100 KB except `web/package-lock.json`.
- All fixtures, traces and reports are generated by committed scripts from synthetic data; the demo is labelled synthetic and "inspired by" a historical defect, with no HFM data.
- MCP: read-only, stdio-only, no network/subprocess/writes; paths relative, no `..`/NUL/URL scheme, symlink-resolved below root, bounded parser (32 MiB, 512 KiB/line, 100k observations) and bounded output; error messages carry no absolute paths (tested). The connected AI client processes tool results under its own privacy policy.
- Licenses: project MIT. Optional runtime deps: `mcp` MIT, `pydantic` MIT, `anyio` MIT, `starlette`/`uvicorn` BSD-3. `web/package-lock.json` packages: 32 MIT, 22 Apache-2.0, 12 MPL-2.0, 1 ISC, 1 BSD-3-Clause (lockfile metadata, not a legal review). `npm ci` reported 0 vulnerabilities.
- CI actions use major-version tags (`actions/checkout@v4`, `setup-python@v5`, `setup-node@v4`), not commit SHAs.

## H. Documentation executed

README paths 1, 2 (up to server registration) and 3; `docs/demo/README.md` reproduce command; `mcp_client_demo.py`; `claude mcp add --scope project` and `--allowedTools` run; `claude mcp add --help` checked. `codex mcp add` and skill paths were checked against documentation only. Links and private paths are covered by `tests/test_docs.py`.

## I. Build and quality checks (final run, after the last code change)

| Command | Result |
|---|---|
| `python -m pytest` | 87 passed |
| `ruff check .` | All checks passed |
| `mypy src` (strict) | no issues in 20 files |
| `python tools/check_file_lengths.py` | OK, longest `mcp_service.py` 160 lines |
| `python -m build --outdir dist` | wheel + sdist built |
| clean-venv wheel/sdist install, CLI, MCP entry | as in section D |
| `python examples/mcp_client_demo.py` | 4 tools, FAIL then PASS |
| `npm ci && npm run build` (web) | built, 0 vulnerabilities |

## J. Git state

See the final message of the release session or run `git log -1`; the commit is local only: no remote, no push, no tag, no PyPI upload.
The repository was initialised at `hfm-parity-lab/` (previously it sat untracked inside an unrelated parent repository).
Commit identity is the existing global Git configuration, unchanged.

## K. Remaining limitations

1. Codex agent E2E not run. 2. Claude Code verified headless on two runs with one model. 3. No PyPI release: install is from a source checkout. 4. MCP has no pagination or report-file input; each call re-parses both traces (bounded by parser limits). 5. `first_divergence` is a recorded difference, not a proven cause. 6. No screen recording is shipped; a storyboard is provided. 7. CI was not executed here (no remote); its commands were run locally one by one.

## L. Release verdict

**READY WITH DOCUMENTED LIMITATIONS.** No correctness, security, licensing or installation blocker remains in what was tested; the open items above are disclosed rather than hidden. Publication (GitHub, PyPI) is left to the owner.

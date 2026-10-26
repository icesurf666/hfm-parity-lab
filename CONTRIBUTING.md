# Contributing

Keep changes small, deterministic, and offline-testable. Do not add exchange
credentials, private traces, model files, or trading execution.

The dependency direction is `domain → application → adapters/interfaces`.
Domain code must not import filesystem, CLI, or frontend code. Preserve public
imports from `hfm_parity`, document behavioral changes in `docs/`, and add a
focused test. Breaking changes are allowed before 1.0 only when correctness
requires them and the migration is documented.

Before opening a pull request, run (`pip install -e '.[dev,mcp]'` first):

```bash
python -m pytest
python tools/check_file_lengths.py
ruff check .
mypy src
(cd web && npm ci && npm test && npm run build)   # when you touch the viewer
```

The MCP modules (`interfaces/mcp_*`) are adapters: they may shape, bound and describe results of
`read_jsonl` and `compare_runs`, never compare events themselves.

Every handwritten Python, TypeScript, TSX, JavaScript, shell, and test file
must remain at or below 200 physical lines. Split only by meaningful
responsibility, not to game the limit.

New public regression fixtures must be synthetic, named after their mechanism
rather than a customer, and documented in `docs/fixture-provenance.md`. Do not
add a comparator solely to increase abstraction. A fixture should test an
externally meaningful invariant; update `docs/comparison-semantics.md` whenever
it changes verdict or compatibility semantics.

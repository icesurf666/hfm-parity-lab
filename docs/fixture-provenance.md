# Public fixture provenance

All JSONL fixtures, demo reports, and examples in this repository are synthetic
and written for tests. They contain no market records, model weights,
credentials, private paths, or derived values from closed systems.

| Fixture mechanism | What it tests |
|---|---|
| Different scale for a numeric value | Values are not comparable without a unit and contract. |
| Feature semantic difference | A report localizes the first feature difference. |
| Lost direction | Comparison detects sign and magnitude. |
| Clock-domain or availability error | A feature after decision time violates causality; absent time is unverifiable. |

Fixtures test HFM Parity Lab behavior. They do not reproduce someone else's
bug, a market event, strategy performance, or a historical result.

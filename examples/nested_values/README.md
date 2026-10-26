# Nested JSON type mismatch

Synthetic regression fixture for the strict-comparison boundary. The two traces
have matching execution metadata and differ only at `features.payload[0]`:
an integer `1` in the baseline and a boolean `true` in the candidate.

```bash
hfm-parity diff --baseline examples/nested_values/baseline.jsonl \
  --candidate examples/nested_values/candidate.jsonl \
  --output nested-report.html --json-output nested-report.json
```

The expected state is `FAIL`; this fixture must never receive a verified strict
`PASS`.

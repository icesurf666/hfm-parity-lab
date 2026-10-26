import assert from "node:assert/strict";
import test from "node:test";
import { parseReport } from "../src/report.ts";

const good = {
  state: "FAIL", mode: "strict", deterministic_parity_verified: false, aligned_events: 2,
  baseline_run_id: "a", candidate_run_id: "b", first_divergence: null,
  findings: [{ classification: "FEATURE_VALUE_MISMATCH", message: "feature values differ", event_id: "e1", stage: "s", field: "f" }],
};
const error = (value: unknown) => { const r = parseReport(typeof value === "string" ? value : JSON.stringify(value)); return "error" in r ? r.error : null; };

test("accepts a report as written by the Python engine", () => {
  const result = parseReport(JSON.stringify(good));
  assert.ok("report" in result && result.report.findings.length === 1);
});

test("rejects invalid JSON and non-objects", () => {
  assert.match(error("{nope")!, /not valid JSON/);
  assert.match(error([])!, /not a JSON object/);
  assert.match(error("null")!, /not a JSON object/);
});

test("rejects unknown verdicts and modes with a specific message", () => {
  assert.match(error({ ...good, state: "GREAT" })!, /"state"/);
  assert.match(error({ ...good, mode: "fuzzy" })!, /"mode"/);
});

test("refuses a report that claims verified parity outside a strict PASS", () => {
  assert.match(error({ ...good, deterministic_parity_verified: true })!, /Inconsistent/);
  assert.match(error({ ...good, state: "PASS", mode: "regression", deterministic_parity_verified: true })!, /Inconsistent/);
  assert.equal(error({ ...good, state: "PASS", findings: [], deterministic_parity_verified: true }), null);
});

test("names the offending finding", () => {
  assert.match(error({ ...good, findings: [good.findings[0], { message: "x" }] })!, /Finding 2 has no classification/);
  assert.match(error({ ...good, first_divergence: { classification: "X" } })!, /first_divergence/);
});

test("keeps hostile text as inert data", () => {
  const r = parseReport(JSON.stringify({ ...good, findings: [{ classification: "<img src=x onerror=alert(1)>", message: "<script>" }] }));
  assert.ok("report" in r && r.report.findings[0].message === "<script>");
});

test("accepts the bundled demo and the reports the Python engine actually writes", async () => {
  const { readFileSync } = await import("node:fs");
  for (const path of ["../public/demo-report.json", "../../docs/demo/report-defect.json", "../../docs/demo/report-fixed.json"]) {
    const result = parseReport(readFileSync(new URL(path, import.meta.url), "utf8"));
    assert.ok("report" in result, `${path}: ${"error" in result ? result.error : ""}`);
  }
});

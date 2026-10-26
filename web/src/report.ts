// Runtime validation of a report produced by the Python engine. The viewer never computes verdicts.
export type Finding = {
  classification: string; event_id?: string | null; stage?: string | null; field?: string | null; message: string;
  severity?: string; baseline?: unknown; candidate?: unknown; evidence?: Record<string, unknown>;
};
export type Report = {
  state: string; mode: string; deterministic_parity_verified: boolean; aligned_events: number;
  baseline_run_id: string; candidate_run_id: string; findings: Finding[]; first_divergence: Finding | null;
};

export const MAX_REPORT_BYTES = 20 * 1024 * 1024;
export const MAX_RENDERED_FINDINGS = 500;
const STATES = ["PASS", "FAIL", "NOT_COMPARABLE", "UNVERIFIABLE", "ERROR"];
const MODES = ["strict", "regression"];

const isObject = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
const optionalText = (value: unknown) => value === undefined || value === null || typeof value === "string";

function findingProblem(value: unknown): string | null {
  if (!isObject(value)) return "is not an object";
  if (typeof value.classification !== "string") return "has no classification";
  if (typeof value.message !== "string") return "has no message";
  return ["event_id", "stage", "field"].every((key) => optionalText(value[key])) ? null : "has a non-text event_id, stage or field";
}

export function reportProblem(value: unknown): string | null {
  if (!isObject(value)) return "The file is not a JSON object.";
  if (typeof value.state !== "string" || !STATES.includes(value.state)) return `"state" must be one of ${STATES.join(", ")}.`;
  if (typeof value.mode !== "string" || !MODES.includes(value.mode)) return `"mode" must be strict or regression.`;
  if (typeof value.deterministic_parity_verified !== "boolean") return `"deterministic_parity_verified" must be true or false.`;
  if (value.deterministic_parity_verified && !(value.mode === "strict" && value.state === "PASS")) {
    return "Inconsistent report: verified parity requires strict mode and a PASS verdict.";
  }
  if (typeof value.aligned_events !== "number") return `"aligned_events" must be a number.`;
  if (typeof value.baseline_run_id !== "string" || typeof value.candidate_run_id !== "string") return "Run ids must be text.";
  if (!Array.isArray(value.findings)) return `"findings" must be a list.`;
  for (const [index, finding] of value.findings.entries()) {
    const problem = findingProblem(finding);
    if (problem) return `Finding ${index + 1} ${problem}.`;
  }
  if (value.first_divergence !== null && value.first_divergence !== undefined) {
    const problem = findingProblem(value.first_divergence);
    if (problem) return `"first_divergence" ${problem}.`;
  }
  return null;
}

export function parseReport(text: string): { report: Report } | { error: string } {
  let data: unknown;
  try { data = JSON.parse(text); } catch { return { error: "The file is not valid JSON." }; }
  const problem = reportProblem(data);
  if (problem) return { error: problem };
  const report = data as Report;
  return { report: { ...report, first_divergence: report.first_divergence ?? null } };
}

// Plain-language wording for the engine's verdicts. Wording only: the viewer never decides a verdict.
export type Tone = "good" | "info" | "bad" | "warn";
export type Verdict = { tone: Tone; headline: string; meaning: string; next: string };

export function describe(state: string, mode: string, verified: boolean): Verdict {
  if (state === "PASS" && verified) {
    return { tone: "good", headline: "The two runs match", meaning: "Every recorded value, decision and event order is identical, and the evidence needed for strict parity is present.", next: "Nothing to fix for the recorded scope. Parity covers only what was recorded." };
  }
  if (state === "PASS") {
    return { tone: "info", headline: "No difference found (regression mode)", meaning: "Nothing differed, but regression mode never claims verified parity.", next: "Re-run with --mode strict if both runs are meant to be identical." };
  }
  if (state === "FAIL") {
    return { tone: "bad", headline: "The runs diverge", meaning: "At least one recorded value, event or event order differs between the runs.", next: "Start at the first divergence below, then read the code that produces that field on both sides." };
  }
  if (state === "NOT_COMPARABLE") {
    return { tone: "warn", headline: "These runs can't be compared strictly", meaning: "Their contracts differ (config, model, schema, data source, input or clock), so a parity verdict would mean nothing.", next: mode === "strict" ? "Fix the metadata that differs, or compare with --mode regression on purpose." : "Clock domains differ; timestamps can't be compared." };
  }
  if (state === "UNVERIFIABLE") {
    return { tone: "warn", headline: "Not enough evidence to decide", meaning: "Nothing differs, but required evidence is missing, so parity cannot be claimed. This is neither a pass nor a failure.", next: "Record what the findings below list (for example data_source or input_hash) and compare again." };
  }
  return { tone: "bad", headline: "The comparison could not complete", meaning: "The engine reported an error.", next: "Check the inputs with hfm-parity validate." };
}

export const TONE_STYLES: Record<Tone, { bar: string; chip: string; icon: string }> = {
  good: { bar: "bg-emerald-500", chip: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300", icon: "text-emerald-500" },
  info: { bar: "bg-sky-500", chip: "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300", icon: "text-sky-500" },
  bad: { bar: "bg-rose-500", chip: "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300", icon: "text-rose-500" },
  warn: { bar: "bg-amber-500", chip: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300", icon: "text-amber-500" },
};

export function shorten(value: unknown, limit = 120): string {
  const text = typeof value === "string" ? JSON.stringify(value) : JSON.stringify(value) ?? "—";
  return text.length > limit ? `${text.slice(0, limit)}…` : text;
}

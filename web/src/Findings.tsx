import { ArrowRight, Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import type { Finding } from "./report";
import { MAX_RENDERED_FINDINGS } from "./report";
import { shorten } from "./verdicts";

const place = (f: Finding) => [f.event_id, f.stage, f.field].filter(Boolean);
const hasValues = (f: Finding) => f.baseline !== undefined && f.baseline !== null || f.candidate !== undefined && f.candidate !== null;

function Location({ finding }: { finding: Finding }) {
  const parts = place(finding);
  if (!parts.length) return <span className="text-sm text-slate-500">run metadata</span>;
  return <span className="flex flex-wrap items-center gap-1 text-sm">{parts.map((part, i) => <span key={i} className="flex items-center gap-1">
    {i > 0 && <span className="text-slate-400" aria-hidden>›</span>}<code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs dark:bg-slate-800">{part}</code></span>)}</span>;
}

function Values({ finding }: { finding: Finding }) {
  if (!hasValues(finding)) return null;
  const delta = finding.evidence?.delta;
  const box = "min-w-0 flex-1 rounded-lg border px-3 py-2";
  return <div className="mt-3 flex flex-col items-stretch gap-2 sm:flex-row sm:items-center">
    <div className={`${box} border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/50`}>
      <div className="text-xs text-slate-500">Baseline</div><div className="break-all font-mono text-sm">{shorten(finding.baseline)}</div></div>
    <ArrowRight className="mx-auto size-4 shrink-0 rotate-90 text-slate-400 sm:rotate-0" aria-hidden />
    <div className={`${box} border-rose-200 bg-rose-50 dark:border-rose-900 dark:bg-rose-950/40`}>
      <div className="text-xs text-rose-600 dark:text-rose-400">Candidate{typeof delta === "number" ? ` (Δ ${Number(delta.toPrecision(4))})` : ""}</div>
      <div className="break-all font-mono text-sm">{shorten(finding.candidate)}</div></div>
  </div>;
}

export function FirstDivergence({ finding }: { finding: Finding | null }) {
  return <section aria-labelledby="first" className="first-finding mt-6 rounded-3xl p-6 sm:p-7">
    <p className="eyebrow">Investigation start</p><h2 id="first" className="mt-1 text-xl font-semibold tracking-tight">First observable divergence</h2>
    {finding ? <>
      <div className="mt-4 flex flex-wrap items-center gap-3"><Location finding={finding} />
        <span className="classification-pill">{finding.classification}</span></div>
      <p className="mt-3 text-[15px] leading-6">{finding.message}</p><Values finding={finding} />
      <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">This is the earliest recorded difference, not proof of the cause. Open the code that computes this field on each side.</p>
    </> : <p className="mt-2 text-slate-600 dark:text-slate-400">No difference was recorded.</p>}
  </section>;
}

export function FindingList({ findings }: { findings: Finding[] }) {
  const [only, setOnly] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const counts = useMemo(() => [...findings.reduce((m, f) => m.set(f.classification, (m.get(f.classification) ?? 0) + 1), new Map<string, number>())], [findings]);
  const visible = findings.filter((f) => (!only || f.classification === only) && search(f, query));
  const shown = visible.slice(0, MAX_RENDERED_FINDINGS);
  if (!findings.length) return null;
  return <section aria-labelledby="all" className="mt-10">
    <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="eyebrow">Evidence log</p><h2 id="all" className="mt-1 text-2xl font-semibold tracking-tight">All findings <span className="font-normal text-slate-500">({findings.length})</span></h2></div><p className="text-sm text-slate-500">Filter by classification</p></div>
    <div className="finding-toolbar mt-5">
      <label className="search-box"><Search className="size-4" aria-hidden /><span className="sr-only">Search findings</span><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search event, field, or message" />
        {query && <button type="button" onClick={() => setQuery("")} aria-label="Clear search"><X className="size-4" aria-hidden /></button>}</label>
      <p aria-live="polite" className="text-sm text-slate-500">Showing {visible.length} of {findings.length}</p>
    </div>
    <div className="finding-filter mt-3 flex flex-wrap gap-2" role="group" aria-label="Filter by type">
      <button type="button" onClick={() => setOnly(null)} aria-pressed={!only} className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${!only ? "border-slate-900 bg-slate-900 text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-950" : "border-slate-200 bg-white/70 hover:border-sky-400 dark:border-slate-700 dark:bg-slate-900"}`}>All <span className="ml-1 opacity-70">{findings.length}</span></button>
      {counts.map(([name, n]) => <button key={name} type="button" aria-pressed={only === name} onClick={() => setOnly(only === name ? null : name)}
        className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${only === name ? "border-sky-600 bg-sky-600 text-white shadow-sm shadow-sky-500/25" : "border-slate-200 bg-white/70 hover:border-sky-400 dark:border-slate-700 dark:bg-slate-900"}`}>{name} <span className="ml-1 opacity-70">{n}</span></button>)}
    </div>
    <ul className="mt-4 space-y-3">{shown.map((f, i) => <li key={`${f.event_id}-${f.stage}-${f.field}-${i}`} className="finding-card rounded-2xl p-5">
      <div className="flex flex-wrap items-center justify-between gap-2"><Location finding={f} /><span className="text-xs text-slate-500">{f.classification}</span></div>
      <p className="mt-1 text-sm">{f.message}</p><Values finding={f} /></li>)}</ul>
    {!visible.length && <p className="empty-state mt-4 rounded-2xl p-6 text-sm text-slate-500">No findings match this filter. Clear the search or choose another classification.</p>}
    {shown.length < visible.length && <p className="mt-3 text-sm text-slate-500">Showing the first {shown.length} of {visible.length}; the JSON report has all of them.</p>}
  </section>;
}

function search(finding: Finding, query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (!needle) return true;
  return [finding.classification, finding.event_id, finding.stage, finding.field, finding.message]
    .some((value) => value?.toLowerCase().includes(needle));
}

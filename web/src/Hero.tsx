import { AlertTriangle, CheckCircle2, CircleHelp, XCircle } from "lucide-react";
import type { Report } from "./report";
import { TONE_STYLES, describe } from "./verdicts";

const ICONS = { good: CheckCircle2, info: CheckCircle2, bad: XCircle, warn: AlertTriangle };

export function Hero({ report }: { report: Report }) {
  const verdict = describe(report.state, report.mode, report.deterministic_parity_verified);
  const style = TONE_STYLES[verdict.tone];
  const Icon = report.state === "UNVERIFIABLE" ? CircleHelp : ICONS[verdict.tone];
  const stats: [string, string][] = [
    ["Events compared", String(report.aligned_events)],
    ["Findings", String(report.findings.length)],
    ["Mode", report.mode],
    ["Parity", report.deterministic_parity_verified ? "verified" : "not verified"],
  ];
  return <section className="hero-card overflow-hidden rounded-3xl">
    <div className={`h-1.5 ${style.bar}`} />
    <div className="p-6 sm:p-8">
      <div className="grid gap-7 lg:grid-cols-[1fr_12rem] lg:items-start">
        <div className="flex items-start gap-4">
        <Icon className={`mt-1 size-9 shrink-0 ${style.icon}`} aria-hidden />
        <div>
          <span className={`rounded-full px-2.5 py-1 text-[11px] font-bold tracking-[0.12em] ${style.chip}`}>{report.state}</span>
          <h1 className="mt-3 text-3xl font-semibold tracking-[-0.035em] sm:text-4xl">{verdict.headline}</h1>
          <p className="mt-3 max-w-2xl leading-6 text-slate-600 dark:text-slate-400">{verdict.meaning}</p>
          <p className="next-step mt-5 text-sm"><span className="font-semibold">Recommended next step</span>{verdict.next}</p>
        </div>
      </div>
        <div className="run-pair"><span>Baseline</span><b>{report.baseline_run_id}</b><i>→</i><span>Candidate</span><b>{report.candidate_run_id}</b></div>
      </div>
      <dl className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {stats.map(([label, value]) => <div key={label} className="metric-card rounded-2xl px-4 py-3.5">
          <dt className="text-xs font-medium text-slate-500 dark:text-slate-400">{label}</dt><dd className="mt-1 font-mono text-lg font-semibold tracking-tight">{value}</dd></div>)}
      </dl>
    </div>
  </section>;
}

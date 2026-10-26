import { FileUp, GitCompareArrows } from "lucide-react";
import { useEffect, useState } from "react";
import { FindingList, FirstDivergence } from "./Findings";
import { Hero } from "./Hero";
import { MAX_REPORT_BYTES, parseReport, type Report } from "./report";

type Source = { kind: "demo" } | { kind: "file"; name: string };
const STEPS: [string, string][] = [
  ["1. Record both runs", "Instrument the pipeline with TraceRecorder (backtest and live write one JSONL trace each)."],
  ["2. Compare", "hfm-parity diff --baseline baseline.jsonl --candidate candidate.jsonl --output report.html --json-output report.json"],
  ["3. Open the JSON here", "Use “Open report” above. The file is read in your browser; nothing is uploaded."],
];

function App() {
  const [report, setReport] = useState<Report | null>(null);
  const [source, setSource] = useState<Source>({ kind: "demo" });
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);

  const loadDemo = () => {
    fetch("./demo-report.json").then((res) => res.ok ? res.text() : Promise.reject(res.status)).then((text) => {
      const parsed = parseReport(text);
      if ("error" in parsed) { setError(`Bundled demo report is invalid: ${parsed.error}`); return; }
      setReport(parsed.report); setSource({ kind: "demo" }); setError("");
    }).catch(() => setError("Could not load the bundled demo report."));
  };
  useEffect(loadDemo, []);

  const openFile = async (file: File | undefined) => {
    if (!file) return;
    if (file.size > MAX_REPORT_BYTES) { setError(`"${file.name}" is larger than ${MAX_REPORT_BYTES / 1024 / 1024} MiB.`); return; }
    const parsed = parseReport(await file.text());
    if ("error" in parsed) { setError(`"${file.name}" is not a usable report: ${parsed.error}`); return; }
    setReport(parsed.report); setSource({ kind: "file", name: file.name }); setError("");
  };

  return <div className={`parity-shell min-h-screen ${dragging ? "is-dragging" : ""}`}
    onDragOver={(e) => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)}
    onDrop={(e) => { e.preventDefault(); setDragging(false); void openFile(e.dataTransfer.files[0]); }}>
    <header className="parity-header">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-3">
        <div className="flex items-center gap-3"><span className="brand-mark"><GitCompareArrows className="size-4" aria-hidden /></span><div><div className="brand-name">HFM Parity Lab</div><div className="brand-kicker">evidence-first debugger</div></div></div>
        <div className="flex items-center gap-2">
          {source.kind === "file" && <button type="button" onClick={loadDemo} className="rounded-lg px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800">Back to demo</button>}
          <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-sky-600 px-3.5 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-sky-500 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-sky-500">
            <FileUp className="size-4" aria-hidden />Open report
            <input type="file" accept=".json,application/json" className="sr-only" onChange={(e) => { void openFile(e.target.files?.[0]); e.target.value = ""; }} />
          </label>
        </div>
      </div>
    </header>
    <main className="mx-auto max-w-5xl px-4 py-9 sm:py-12">
      {error && <p role="alert" className="mb-4 rounded-xl border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-800 dark:border-rose-900 dark:bg-rose-950/50 dark:text-rose-200">{error}</p>}
      {report ? <>
        <p role="status" className="source-line mb-4 text-sm">
          {source.kind === "demo" ? "Showing the bundled synthetic demo. Drop your own report.json anywhere on this page." : `Showing your report: ${source.name}`}</p>
        <div className="workspace-label"><span>Comparison report</span><span>Read-only evidence</span></div>
        <Hero report={report} /><FirstDivergence finding={report.first_divergence} /><FindingList findings={report.findings} />
      </> : !error && <p>Loading report…</p>}
      <section aria-labelledby="how" className="how-to mt-12 rounded-3xl p-6 sm:p-8">
        <p className="eyebrow">Workflow</p><h2 id="how" className="mt-1 text-xl font-semibold tracking-tight">From two runs to one answer.</h2>
        <ol className="mt-6 grid gap-5 text-sm sm:grid-cols-3">{STEPS.map(([title, text], index) => <li key={title}><div className="step-number">0{index + 1}</div><div className="mt-3 font-semibold">{title}</div>
          <div className="mt-0.5 break-words text-slate-600 dark:text-slate-400">{text.startsWith("hfm-") ? <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs dark:bg-slate-800">{text}</code> : text}</div></li>)}</ol>
      </section>
      <footer className="mt-10 border-t border-slate-200/80 pt-5 text-xs text-slate-500 dark:border-slate-800">This viewer only displays a finished report. Only the Python engine compares traces.</footer>
    </main>
  </div>;
}

export default App;

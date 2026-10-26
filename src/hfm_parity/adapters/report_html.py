"""Self-contained HTML rendering of a report dictionary (no JavaScript, no external assets).

Wording only: the verdict comes from the engine and is merely explained here. Every value is escaped.
"""
from __future__ import annotations

import html
import json
from typing import Any

CSS = """
:root{--bg:#f8fafc;--card:#fff;--ink:#0f172a;--mute:#64748b;--line:#e2e8f0;--chip:#f1f5f9;--bad:#e11d48;--good:#10b981;--warn:#f59e0b;--info:#0ea5e9}
@media(prefers-color-scheme:dark){:root{--bg:#020617;--card:#0f172a;--ink:#f1f5f9;--mute:#94a3b8;--line:#1e293b;--chip:#1e293b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,sans-serif}
main{max-width:56rem;margin:0 auto;padding:2rem 1rem 4rem}.brand{font-weight:600;color:var(--mute);margin-bottom:1rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:1rem;padding:1.5rem;margin-bottom:1.25rem;box-shadow:0 1px 2px #0001}
.hero{border-top:6px solid var(--tone)}.chip{display:inline-block;border-radius:99px;padding:.1rem .65rem;font-size:.75rem;font-weight:700;background:var(--tone);color:#fff}
h1{margin:.5rem 0 .25rem;font-size:1.75rem;letter-spacing:-.02em}h2{font-size:.8rem;text-transform:uppercase;letter-spacing:.06em;color:var(--bad);margin:0 0 .75rem}
.mute{color:var(--mute)}.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(9rem,1fr));gap:.75rem;margin:1.25rem 0 0}
.stats div{background:var(--chip);border-radius:.75rem;padding:.6rem .9rem}.stats small{display:block;color:var(--mute);font-size:.75rem}
code,.v{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.82rem}code{background:var(--chip);border-radius:.3rem;padding:.1rem .4rem}
.pair{display:flex;gap:.6rem;align-items:center;flex-wrap:wrap;margin-top:.75rem}.box{flex:1;min-width:10rem;border:1px solid var(--line);border-radius:.6rem;padding:.5rem .75rem;word-break:break-all}
.box small{display:block;color:var(--mute)}.box.cand{border-color:var(--bad);background:#e11d4810}.box.cand small{color:var(--bad)}
table{width:100%;border-collapse:collapse;font-size:.85rem}th,td{text-align:left;padding:.5rem .6rem;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--mute);font-weight:600;font-size:.75rem;text-transform:uppercase}.scroll{overflow-x:auto}
"""
TONES = {"good": "var(--good)", "info": "var(--info)", "bad": "var(--bad)", "warn": "var(--warn)"}


def _verdict(state: str, verified: bool) -> tuple[str, str, str, str]:
    """(tone, headline, meaning, next step)"""
    if state == "PASS" and verified:
        return ("good", "The two runs match", "Every recorded value, decision and event order is identical and the evidence strict parity needs is present.",
                "Parity covers only what was recorded.")
    if state == "PASS":
        return ("info", "No difference found (regression mode)", "Nothing differed, but regression mode never claims verified parity.",
                "Re-run with --mode strict if both runs are meant to be identical.")
    texts = {
        "FAIL": ("bad", "The runs diverge", "At least one recorded value, event or event order differs.",
                 "Start at the first divergence, then read the code that produces that field on both sides."),
        "NOT_COMPARABLE": ("warn", "These runs can't be compared strictly", "Their contracts differ (config, model, schema, data source, input or clock).",
                           "Fix the metadata that differs, or compare with --mode regression on purpose."),
        "UNVERIFIABLE": ("warn", "Not enough evidence to decide", "Nothing differs, but required evidence is missing. This is neither a pass nor a failure.",
                         "Record what the findings list (for example data_source or input_hash) and compare again."),
    }
    return texts.get(state, ("bad", "The comparison could not complete", "The engine reported an error.", "Check the inputs with hfm-parity validate."))


def _text(value: Any) -> str:
    return html.escape("—" if value is None else str(value))


def _value(value: Any) -> str:
    shown = json.dumps(value, ensure_ascii=False) if value is not None else "—"
    return html.escape(shown if len(shown) <= 120 else shown[:120] + "…")


def _location(finding: dict[str, Any]) -> str:
    parts = [finding.get(key) for key in ("event_id", "stage", "field") if finding.get(key)]
    return " › ".join(f"<code>{html.escape(str(part))}</code>" for part in parts) or "run metadata"


def _pair(finding: dict[str, Any]) -> str:
    if finding.get("baseline") is None and finding.get("candidate") is None:
        return ""
    return (f'<div class="pair"><div class="box"><small>Baseline</small><span class="v">{_value(finding.get("baseline"))}</span></div>'
            f'<span class="mute">→</span><div class="box cand"><small>Candidate</small><span class="v">{_value(finding.get("candidate"))}</span></div></div>')


def render(report: dict[str, Any], row: Any) -> str:
    state, verified = str(report["state"]), bool(report["deterministic_parity_verified"])
    tone, headline, meaning, step = _verdict(state, verified)
    first = report.get("first_divergence")
    stats = [("Events compared", report["aligned_events"]), ("Findings", len(report["findings"])), ("Mode", report["mode"]),
             ("Parity", "verified" if verified else "not verified")]
    cards = "".join(f"<div><small>{label}</small><b>{_text(value)}</b></div>" for label, value in stats)
    divergence = ""
    if first:
        divergence = (f'<section class="card"><h2>Start here: first divergence</h2><p>{_location(first)} '
                      f'<span class="mute">{_text(first["classification"])}</span></p><p>{_text(first["message"])}</p>{_pair(first)}'
                      '<p class="mute">The earliest recorded difference, not proof of the cause. Read the code that computes this field on each side.</p></section>')
    head = "<tr><th>Type</th><th>Where</th><th>Baseline</th><th>Candidate</th><th>Message</th></tr>"
    table = ("<p class=\"mute\">No findings.</p>" if not report["findings"] else
             f'<div class="scroll"><table>{head}{"".join(row(f) for f in report["findings"])}</table></div>')
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Parity report: {html.escape(state)}</title><style>{CSS}</style></head><body><main><div class="brand">HFM Parity Lab</div>'
            f'<section class="card hero" style="--tone:{TONES[tone]}"><span class="chip">{html.escape(state)}</span><h1>{html.escape(headline)}</h1>'
            f'<p class="mute">{html.escape(meaning)}</p><p><b>Next:</b> {html.escape(step)}</p><div class="stats">{cards}</div>'
            f'<p class="mute">Baseline <code>{_text(report["baseline_run_id"])}</code> → candidate <code>{_text(report["candidate_run_id"])}</code></p></section>'
            f'{divergence}<section class="card"><h2 style="color:var(--mute)">All findings ({len(report["findings"])})</h2>{table}</section>'
            '<p class="mute">Generated by hfm-parity. A report shows recorded differences; it does not prove their cause.</p></main></body></html>')

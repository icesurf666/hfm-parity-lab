"""Record the three synthetic traces and write both comparison reports (deterministic)."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from hfm_parity import compare_runs, read_jsonl, write_html, write_json

sys.path.insert(0, str(Path(__file__).resolve().parent))
from record_traces import record

TRACES = (("backtest_features", "baseline"), ("live_features", "candidate"),
          ("live_features_fixed", "candidate-fixed"))
REPORTS = (("candidate", "defect"), ("candidate-fixed", "fixed"))


def build(directory: Path) -> dict[str, str]:
    """Write traces and reports into a new ``directory``; return each report's verdict."""
    directory.mkdir(parents=True, exist_ok=True)
    for module, name in TRACES:
        record(module, directory / f"{name}.jsonl")
    verdicts = {}
    previous = Path.cwd()
    os.chdir(directory)  # report writers only accept paths below the current directory
    try:
        for candidate, label in REPORTS:
            report = compare_runs(read_jsonl("baseline.jsonl"), read_jsonl(f"{candidate}.jsonl"))
            write_html(report, f"report-{label}.html")
            write_json(report, f"report-{label}.json")
            verdicts[label] = report.state.value
    finally:
        os.chdir(previous)
    return verdicts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="directory that must not hold traces yet")
    args = parser.parse_args()
    for label, verdict in build(args.output_dir).items():
        print(f"{label}: {verdict}")


if __name__ == "__main__":
    main()

"""Compare two traces through only the public hfm_parity import path."""
from __future__ import annotations

import argparse
from pathlib import Path

from hfm_parity import ResultState, compare_runs, read_jsonl, write_html, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare traces with the Python SDK.")
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("sdk-report"))
    args = parser.parse_args()
    report = compare_runs(read_jsonl(args.baseline), read_jsonl(args.candidate))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_html(report, args.output_dir / "report.html")
    write_json(report, args.output_dir / "report.json")
    print(f"{report.state}; first={report.first_divergence}")
    return 0 if report.state is ResultState.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())

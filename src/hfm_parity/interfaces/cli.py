"""Stable CLI interface for CI and local diagnosis."""
from __future__ import annotations

import argparse
from importlib.resources import as_file, files
from pathlib import Path

from hfm_parity.adapters.csv_quick import compare_csv, load_csv_mapping
from hfm_parity.adapters.jsonl import TraceValidationError, read_jsonl
from hfm_parity.adapters.reports import write_html, write_json
from hfm_parity.application.compare import compare_runs
from hfm_parity.domain.models import CompareConfig, ComparisonMode, ResultState

EXIT_CODES = {ResultState.PASS: 0, ResultState.FAIL: 1, ResultState.NOT_COMPARABLE: 2, ResultState.UNVERIFIABLE: 2, ResultState.ERROR: 4}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hfm-parity", description="Compare recorded decision traces")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("input", type=Path)
    diff = commands.add_parser("diff")
    diff.add_argument("--baseline", required=True, type=Path)
    diff.add_argument("--candidate", required=True, type=Path)
    diff.add_argument("--output", required=True, type=Path, help="relative HTML output path")
    diff.add_argument("--json-output", type=Path, help="relative JSON output path")
    diff.add_argument("--abs-tol", type=float, default=0.0)
    diff.add_argument("--rel-tol", type=float, default=0.0)
    diff.add_argument("--mode", choices=[item.value for item in ComparisonMode], default="strict")
    quick = commands.add_parser("quick-diff", help="diagnose two mapped CSV signal logs")
    quick.add_argument("baseline", type=Path)
    quick.add_argument("candidate", type=Path)
    quick.add_argument("--mapping", required=True, type=Path)
    quick.add_argument("--output", type=Path, help="optional relative HTML report path")
    quick.add_argument("--json-output", type=Path, help="optional relative JSON report path")
    quick.add_argument("--abs-tol", type=float, default=0.0)
    quick.add_argument("--rel-tol", type=float, default=0.0)
    quick.add_argument("--mode", choices=[item.value for item in ComparisonMode], default="strict")
    commands.add_parser("demo")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            trace = read_jsonl(args.input)
            print(f"VALID: {trace.meta.run_id}; observations={len(trace.observations)}")
            return 0
        if args.command == "demo":
            args.output = Path("parity-demo.html")
            args.json_output = Path("parity-demo.json")
            args.abs_tol, args.rel_tol = 0.0, 0.0
            args.mode = ComparisonMode.STRICT.value
            bundled = files("hfm_parity").joinpath("examples")
            with as_file(bundled.joinpath("baseline.jsonl")) as baseline, \
                    as_file(bundled.joinpath("candidate.jsonl")) as candidate:
                report = compare_runs(read_jsonl(Path(baseline)), read_jsonl(Path(candidate)))
        elif args.command == "quick-diff":
            config = CompareConfig(args.abs_tol, args.rel_tol, ComparisonMode(args.mode))
            report = compare_csv(args.baseline, args.candidate, load_csv_mapping(args.mapping), config)
            _quick_summary(report)
            if args.output:
                write_html(report, args.output)
            if args.json_output:
                write_json(report, args.json_output)
            return EXIT_CODES[report.state]
        else:
            report = compare_runs(read_jsonl(args.baseline), read_jsonl(args.candidate),
                                  CompareConfig(args.abs_tol, args.rel_tol, ComparisonMode(args.mode)))
        write_html(report, args.output)
        if args.json_output:
            write_json(report, args.json_output)
        verified = "verified" if report.deterministic_parity_verified else "not-verified"
        print(f"{report.state}: mode={report.mode}; {verified}; aligned={report.aligned_events}; findings={len(report.findings)}")
        return 0 if args.command == "demo" else EXIT_CODES[report.state]
    except TraceValidationError as exc:
        print(f"INVALID_INPUT: {exc}")
        return 3
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 4
    except Exception as exc:  # noqa: BLE001 - CLI boundary maps unforeseen faults.
        print(f"INTERNAL_ERROR: {type(exc).__name__}: {exc}")
        return 4


def _quick_summary(report: object) -> None:
    """Human-facing context; the canonical report is still the engine's report."""
    from hfm_parity.domain.models import ComparisonReport
    assert isinstance(report, ComparisonReport)
    first = report.first_divergence
    print("HFM Parity Lab — Quick Compare")
    print(f"Aligned observations: {report.aligned_events}; findings: {len(report.findings)}")
    if first is not None:
        print(f"First observed difference: {first.event_id} / {first.stage} / {first.field}")
    if not report.deterministic_parity_verified:
        print("Parity verification: not verified; CSV mapping does not establish unrecorded provenance.")


if __name__ == "__main__":
    raise SystemExit(main())

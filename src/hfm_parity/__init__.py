"""HFM Parity Lab public API."""

from importlib.metadata import PackageNotFoundError, version

from hfm_parity.adapters.csv_quick import CsvMapping, compare_csv, csv_trace, load_csv_mapping
from hfm_parity.adapters.jsonl import TraceValidationError, read_jsonl
from hfm_parity.adapters.recorder import TraceRecorder, feature
from hfm_parity.adapters.reports import write_html, write_json
from hfm_parity.application.compare import compare_runs
from hfm_parity.domain.models import (
    Classification,
    CompareConfig,
    ComparisonMode,
    ComparisonReport,
    Feature,
    Finding,
    Observation,
    ResultState,
    RunMeta,
    Trace,
)

try:
    __version__ = version("hfm-parity-lab")
except PackageNotFoundError:  # running from a source tree that is not installed
    __version__ = "0.0.0+unknown"

__all__ = [
    "Classification", "CompareConfig", "ComparisonMode", "ComparisonReport", "CsvMapping", "Feature", "Finding",
    "Observation", "ResultState", "RunMeta", "Trace", "TraceRecorder", "TraceValidationError",
    "__version__", "compare_csv", "compare_runs", "csv_trace", "feature", "load_csv_mapping",
    "read_jsonl", "write_html", "write_json",
]

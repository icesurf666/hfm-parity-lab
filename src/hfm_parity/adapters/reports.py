"""Safe JSON and HTML report writers."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from hfm_parity.adapters.report_html import _location, _text, _value, render
from hfm_parity.domain.models import ComparisonReport


def write_json(report: ComparisonReport, path: Path | str) -> None:
    target = _safe_output(path)
    target.write_text(json.dumps(_json_safe(report.as_dict()), indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_html(report: ComparisonReport, path: Path | str) -> None:
    target = _safe_output(path)
    target.write_text(render(_json_safe(report.as_dict()), _row), encoding="utf-8")


def _row(finding: dict[str, Any]) -> str:
    """One findings-table row; every cell is escaped."""
    where = _location(finding) if "event_id" in finding or "stage" in finding or "field" in finding else "run metadata"
    cells = [_text(finding.get("classification")), where, _value(finding.get("baseline")), _value(finding.get("candidate")),
             _text(finding.get("message"))]
    return "<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>"


def _safe_output(path: Path | str) -> Path:
    path = Path(path)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("output path must be relative and must not contain '..'")
    root = Path.cwd().resolve()
    target = (root / path).resolve()
    if root not in target.parents:
        raise ValueError("output path must remain inside the current directory")
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return {"numeric_kind": "nan" if math.isnan(value) else "infinity", "sign": "+" if value > 0 else "-"}
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value

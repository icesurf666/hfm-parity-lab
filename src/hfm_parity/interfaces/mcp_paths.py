"""Single choke point for tool-supplied paths: relative, below one root, no symlink escape."""
from __future__ import annotations

import os
from pathlib import Path

MAX_PATH_CHARS = 1024
MAX_LISTED = 10


class ToolFailure(ValueError):
    """An anticipated, client-visible failure with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def resolve_trace(root: Path, requested: str) -> Path:
    """Return a readable file below ``root``; messages never echo private paths."""
    path = Path(requested)
    if (not requested or "\x00" in requested or len(requested) > MAX_PATH_CHARS
            or path.is_absolute() or ".." in path.parts or "://" in requested):
        raise ToolFailure("INVALID_PATH", "Path must be a non-empty relative path below the configured root.")
    target = (root / path).resolve()
    if root not in target.parents:
        raise ToolFailure("INVALID_PATH", "Path is outside the configured root.")
    if not target.is_file():
        raise ToolFailure("TRACE_NOT_FOUND", _not_found(root, path))
    return target


def available_traces(root: Path) -> list[str]:
    """Up to ``MAX_LISTED`` ``*.jsonl`` names below ``root``; symlinked directories are not followed."""
    found: list[str] = []
    for folder, dirs, names in os.walk(root, followlinks=False):
        dirs.sort()
        for name in sorted(names):
            if name.endswith(".jsonl"):
                found.append(str((Path(folder) / name).relative_to(root))[:120])
    return found[:MAX_LISTED]


def _not_found(root: Path, path: Path) -> str:
    message = "Trace file not found. Paths are relative to the server root, not the working directory."
    if path.parts and path.parts[0] == root.name:
        message += f" Drop the leading '{root.name}/': the root already is that directory."
    listed = available_traces(root)
    return message + (f" Available traces: {', '.join(listed)}." if listed else " The root contains no .jsonl files.")

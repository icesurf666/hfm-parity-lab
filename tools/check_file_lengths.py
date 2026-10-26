"""Fail CI when a handwritten source file grows beyond the reviewable limit."""
from __future__ import annotations

import sys
from pathlib import Path

LIMIT = 200
EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx"}
SKIP = {".git", ".venv", "node_modules", "dist", "build", "__pycache__"}


def files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*") if path.suffix in EXTENSIONS and not (set(path.parts) & SKIP)]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    offenders = [(path.relative_to(root), len(path.read_text(encoding="utf-8").splitlines()))
                for path in files(root)]
    offenders = [(path, count) for path, count in offenders if count > LIMIT]
    for path, count in offenders:
        print(f"{path}: {count} lines (maximum {LIMIT})")
    return 1 if offenders else 0


if __name__ == "__main__":
    sys.exit(main())

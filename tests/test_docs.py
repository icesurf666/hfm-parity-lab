from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = [ROOT / "README.md", ROOT / "CONTRIBUTING.md", *sorted((ROOT / "docs").rglob("*.md")),
        *sorted((ROOT / "skills").rglob("*.md")), *sorted((ROOT / "examples").rglob("*.md"))]
PRIVATE = re.compile(r"/Users/|/private/tmp|/home/\w+|C:\\\\Users")


def test_local_markdown_links_resolve() -> None:
    for doc in DOCS:
        for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", doc.read_text()):
            if "://" not in target and not target.startswith("mailto:"):
                assert (doc.parent / target).exists(), f"{doc.relative_to(ROOT)} -> {target}"


def test_docs_contain_no_private_paths_or_unpublished_install_commands() -> None:
    for doc in DOCS:
        text = doc.read_text()
        assert not PRIVATE.search(text), doc.name
        assert not re.search(r"pip install '?hfm-parity-lab", text), doc.name  # not on PyPI in v0.1.0

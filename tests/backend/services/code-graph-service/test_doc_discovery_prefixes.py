"""Docs discovery walks only literal match prefixes (sshfs-safe)."""

from __future__ import annotations

import time
from pathlib import Path

from code_graph_service.domain.doc_discovery import (
    discover_documentation_files,
    literal_dir_prefixes,
)


def test_literal_dir_prefixes_from_match_globs():
    assert literal_dir_prefixes(["docs/**/*.md", "backend/docs/**/*.md"]) == [
        "docs",
        "backend/docs",
    ]
    assert literal_dir_prefixes(["**/*.md"]) is None
    assert literal_dir_prefixes(["*.md"]) is None


def test_discover_docs_skips_unmatched_trees(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("# a\n", encoding="utf-8")
    junk = tmp_path / "frontend" / "node_modules" / "pkg"
    junk.mkdir(parents=True)
    (junk / "README.md").write_text("# junk\n", encoding="utf-8")

    found = discover_documentation_files(
        tmp_path,
        match_globs=["docs/**/*.md"],
        exclude_dirs=[],
        exclude_globs=["**/node_modules/**"],
    )
    rels = {item.relative_path for item in found}
    assert rels == {"docs/a.md"}
    assert "frontend/node_modules/pkg/README.md" not in rels


def test_discover_docs_respects_deadline(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    for i in range(20):
        (docs / f"f{i}.md").write_text(f"# {i}\n", encoding="utf-8")

    found = discover_documentation_files(
        tmp_path,
        match_globs=["docs/**/*.md"],
        deadline_monotonic=time.monotonic() - 1.0,
    )
    assert found == []

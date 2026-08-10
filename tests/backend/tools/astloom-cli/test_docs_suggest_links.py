"""Tests for evidence-only docs-suggest-links (hybrid write path)."""

from __future__ import annotations

from pathlib import Path

from astloom_cli.docs_link_suggest import (
    apply_suggested_links,
    extract_evidence_link_tokens,
    primary_symbol_name,
    suggest_links_for_markdown,
    suggest_links_for_tree,
)


def test_extract_evidence_from_path_citation(tmp_path: Path):
    py = tmp_path / "backend" / "pkg" / "mod.py"
    py.parent.mkdir(parents=True)
    py.write_text("def login():\n    return True\n", encoding="utf-8")
    body = "See `backend/pkg/mod.py` for login.\n"
    tokens = extract_evidence_link_tokens(body, repo=tmp_path)
    assert tokens == ["backend/pkg/mod.py::login"]


def test_primary_symbol_prefers_test_fn_in_test_files(tmp_path: Path):
    py = tmp_path / "tests" / "backend" / "test_hybrid.py"
    py.parent.mkdir(parents=True)
    py.write_text(
        "def check_password():\n    return True\n\n"
        "def test_build_coverage():\n    assert True\n",
        encoding="utf-8",
    )
    assert primary_symbol_name(py) == "test_build_coverage"
    # Path-only citations under tests/ are ignored (require path::Symbol).
    body = "See `tests/backend/test_hybrid.py`.\n"
    assert extract_evidence_link_tokens(body, repo=tmp_path) == []
    explicit = "See `tests/backend/test_hybrid.py::test_build_coverage`.\n"
    assert extract_evidence_link_tokens(explicit, repo=tmp_path) == [
        "tests/backend/test_hybrid.py::test_build_coverage"
    ]


def test_extract_evidence_from_loose_path(tmp_path: Path):
    py = tmp_path / "backend" / "pkg" / "loose.py"
    py.parent.mkdir(parents=True)
    py.write_text("async def run():\n    return 1\n", encoding="utf-8")
    body = "See backend/pkg/loose.py in prose without backticks.\n"
    tokens = extract_evidence_link_tokens(body, repo=tmp_path)
    assert tokens == ["backend/pkg/loose.py::run"]


def test_extract_skips_missing_files(tmp_path: Path):
    body = "See `backend/missing/nope.py` and `backend/missing/nope.py::Ghost`.\n"
    assert extract_evidence_link_tokens(body, repo=tmp_path) == []


def test_suggest_links_reports_missing_only(tmp_path: Path):
    py = tmp_path / "backend" / "pkg" / "a.py"
    py.parent.mkdir(parents=True)
    py.write_text("def alpha():\n    pass\n", encoding="utf-8")
    text = """---
doc_id: as.doc.test.x
title: X
linked_symbols: []
---

# X

## Purpose

Uses `backend/pkg/a.py`.
"""
    row = suggest_links_for_markdown(relative_path="docs/x.md", text=text, repo=tmp_path)
    assert row["suggested_new"] == ["backend/pkg/a.py::alpha"]
    assert row["already_linked"] == []
    assert row["has_frontmatter"] is True
    assert row["mode"] == "hybrid_evidence_suggest"


def test_suggest_links_already_linked_not_re_suggested(tmp_path: Path):
    py = tmp_path / "backend" / "pkg" / "b.py"
    py.parent.mkdir(parents=True)
    py.write_text("def beta():\n    pass\n", encoding="utf-8")
    text = """---
doc_id: as.doc.test.y
title: Y
linked_symbols:
- backend/pkg/b.py::beta
---

# Y

## Purpose

Uses `backend/pkg/b.py`.
"""
    row = suggest_links_for_markdown(relative_path="docs/y.md", text=text, repo=tmp_path)
    assert row["suggested_new"] == []
    assert row["already_linked"] == ["backend/pkg/b.py::beta"]


def test_apply_skips_without_frontmatter(tmp_path: Path):
    path = tmp_path / "notes.md"
    path.write_text("# No FM\n\nSee `backend/x.py`.\n", encoding="utf-8")
    result = apply_suggested_links(path, ["backend/x.py::x"])
    assert result["status"] == "skipped_no_frontmatter"
    assert path.read_text(encoding="utf-8").startswith("# No FM")


def test_apply_merges_linked_symbols(tmp_path: Path):
    path = tmp_path / "docs" / "z.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        "---\ndoc_id: as.doc.test.z\ntitle: Z\nlinked_symbols: []\n---\n\n# Z\n",
        encoding="utf-8",
    )
    result = apply_suggested_links(path, ["backend/pkg/z.py::z"])
    assert result["status"] == "applied"
    assert "backend/pkg/z.py::z" in path.read_text(encoding="utf-8")


def test_suggest_tree_include_all_and_docs_root(tmp_path: Path):
    py = tmp_path / "backend" / "pkg" / "c.py"
    py.parent.mkdir(parents=True)
    py.write_text("def gamma():\n    pass\n", encoding="utf-8")
    docs = tmp_path / "backend" / "docs"
    docs.mkdir(parents=True)
    (docs / "with.md").write_text(
        "---\ndoc_id: a\ntitle: A\nlinked_symbols: []\n---\n\n# A\n\n"
        "`backend/pkg/c.py`\n",
        encoding="utf-8",
    )
    (docs / "empty.md").write_text(
        "---\ndoc_id: b\ntitle: B\nlinked_symbols: []\n---\n\n# B\n\nNo paths.\n",
        encoding="utf-8",
    )
    report = suggest_links_for_tree(
        tmp_path, docs_root="backend/docs", include_all=True
    )
    assert report["scanned_count"] == 2
    assert report["files_with_suggestions"] == 1
    assert report["suggested_total"] == 1
    assert len(report["files"]) == 2


def test_cmd_docs_suggest_links_json_apply(tmp_path: Path, monkeypatch):
    import argparse

    from astloom_cli.commands.docs_suggest_links import cmd_docs_suggest_links

    py = tmp_path / "backend" / "pkg" / "d.py"
    py.parent.mkdir(parents=True)
    py.write_text("def delta():\n    pass\n", encoding="utf-8")
    md = tmp_path / "docs" / "d.md"
    md.parent.mkdir(parents=True)
    md.write_text(
        "---\ndoc_id: d\ntitle: D\nlinked_symbols: []\n---\n\n# D\n\n"
        "`backend/pkg/d.py`\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "astloom_cli.commands.docs_suggest_links.repo_root",
        lambda: tmp_path,
    )
    args = argparse.Namespace(
        path=str(md),
        apply=True,
        json=True,
        docs_root="docs",
        include_all=False,
    )
    code = cmd_docs_suggest_links(args)
    assert code == 1
    assert "backend/pkg/d.py::delta" in md.read_text(encoding="utf-8")

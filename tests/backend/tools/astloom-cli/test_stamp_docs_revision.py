"""Tests for bulk doc_version / updated_at stamping."""

from __future__ import annotations

from pathlib import Path

from astloom_cli.commands.docs_standards.stamp_revision import (
    stamp_revision_frontmatter,
    stamp_revision_tree,
)


def test_stamp_revision_frontmatter_sets_fields():
    raw = """---
doc_id: as.doc.test.a
title: A
---

# A
"""
    out, changed = stamp_revision_frontmatter(
        raw, doc_version="1.0.0", updated_at="2026-07-24"
    )
    assert changed is True
    assert "doc_version: 1.0.0" in out or 'doc_version: "1.0.0"' in out
    assert "updated_at: '2026-07-24'" in out or 'updated_at: "2026-07-24"' in out or "updated_at: 2026-07-24" in out


def test_stamp_revision_frontmatter_noop_when_same():
    raw = """---
doc_id: as.doc.test.a
doc_version: 1.0.0
updated_at: "2026-07-24"
---

body
"""
    out, changed = stamp_revision_frontmatter(
        raw, doc_version="1.0.0", updated_at="2026-07-24"
    )
    assert changed is False
    assert out == raw


def test_stamp_revision_frontmatter_skips_no_fm():
    raw = "# No frontmatter\n"
    out, changed = stamp_revision_frontmatter(
        raw, doc_version="1.0.0", updated_at="2026-07-24"
    )
    assert changed is False
    assert out == raw


def test_stamp_revision_tree(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text(
        "---\ndoc_id: as.doc.x.a\ntitle: A\n---\n\n# A\n",
        encoding="utf-8",
    )
    (docs / "bare.md").write_text("# Bare\n", encoding="utf-8")
    result = stamp_revision_tree(
        [docs],
        repo=tmp_path,
        doc_version="1.0.0",
        updated_at="2026-07-24",
        write=True,
    )
    assert result["summary"]["changed"] == 1
    assert result["summary"]["skipped_no_frontmatter"] == 1
    text = (docs / "a.md").read_text(encoding="utf-8")
    assert "1.0.0" in text
    assert "2026-07-24" in text

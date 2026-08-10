"""Tests for astloom docs-standards."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from astloom_cli.commands.docs_standards import (
    cmd_docs_standards,
    format_detail_text,
    parse_docs_standards_words,
)
from astloom_cli.commands.docs_standards.check import check_markdown_doc
from astloom_cli.commands.docs_standards.collect import build_docs_standards_report
from astloom_cli.commands.docs_standards.remediate import remediate_markdown_doc
from astloom_cli.parser import build_parser
from astloom_cli.util import repo_root

GOOD_DOC = """---
doc_id: as.doc.test.good
title: "01 - Good Doc"
doc_type: standard
status: active
schema_version: "1.0"
owner: platform-docs
summary: A conforming test document.
tags:
  - test
phase: "00-master-plan"
canonical_path: docs/00-master-plan/01-good-doc.md
lifecycle_lane: current
concern_lane: standard
audience_lane:
  - platform-engineering
authority: normative
visibility: internal
doc_version: "1.0.0"
updated_at: "2026-07-24"
---

# 01 - Good Doc

## Purpose

This document owns the good-doc fixture for CLI tests.

## Related Documents

- none
"""


def test_parser_docs_standards_word_modes():
    parser = build_parser()
    args = parser.parse_args(["docs-standards"])
    assert args.command == "docs-standards"
    assert args.words == []

    detailed = parser.parse_args(["docs-standards", "detail"])
    assert detailed.words == ["detail"]

    saved = parser.parse_args(["docs-standards", "save", "/tmp/out.txt"])
    assert saved.words == ["save", "/tmp/out.txt"]

    both = parser.parse_args(["docs-standards", "detail", "save", "/tmp/out.txt"])
    assert both.words == ["detail", "save", "/tmp/out.txt"]


def test_parse_docs_standards_words():
    assert parse_docs_standards_words([]) == (False, "")
    assert parse_docs_standards_words(["detail"]) == (True, "")
    assert parse_docs_standards_words(["save", "/tmp/a.txt"]) == (False, "/tmp/a.txt")
    assert parse_docs_standards_words(["detail", "save", "/tmp/a.txt"]) == (True, "/tmp/a.txt")
    with pytest.raises(SystemExit):
        parse_docs_standards_words(["save"])
    with pytest.raises(SystemExit):
        parse_docs_standards_words(["--detail"])


def test_check_markdown_doc_ok_and_fail():
    ok = check_markdown_doc(
        relative_path="docs/00-master-plan/01-good-doc.md",
        text=GOOD_DOC,
    )
    assert ok["ok"] is True
    assert ok["issue_count"] == 0
    assert ok["warning_count"] == 0

    bad = check_markdown_doc(relative_path="docs/x.md", text="# Only H1\n\nNo frontmatter.\n")
    assert bad["ok"] is False
    assert "missing_or_invalid_frontmatter" in bad["issues"]


def test_check_revision_fields_warn_and_reject_invalid():
    # Missing revision → warnings only (soft migration; does not fail ok).
    missing = check_markdown_doc(
        relative_path="docs/00-master-plan/01-good-doc.md",
        text=GOOD_DOC.replace("doc_version: \"1.0.0\"\n", "").replace(
            "updated_at: \"2026-07-24\"\n", ""
        ),
    )
    assert missing["ok"] is True
    assert "missing_recommended:doc_version" in missing["warnings"]
    assert "missing_recommended:updated_at" in missing["warnings"]

    invalid = check_markdown_doc(
        relative_path="docs/00-master-plan/01-good-doc.md",
        text=GOOD_DOC.replace("doc_version: \"1.0.0\"", 'doc_version: "v1"').replace(
            "updated_at: \"2026-07-24\"", 'updated_at: "yesterday"'
        ),
    )
    assert invalid["ok"] is False
    assert "invalid_doc_version" in invalid["issues"]
    assert "invalid_updated_at" in invalid["issues"]


def test_remediate_markdown_doc_makes_body_tier_conforming():
    raw = "# 01 - Sample Topic\n\nThis sample owns a topic for remediation unit tests.\n"
    rel = "docs/00-master-plan/01-sample-topic.md"
    fixed = remediate_markdown_doc(relative_path=rel, text=raw)
    row = check_markdown_doc(relative_path=rel, text=fixed)
    assert row["ok"] is True, row["issues"]
    assert "doc_id: as.doc.master.sample-topic" in fixed
    assert "## Purpose" in fixed
    assert "doc_version:" in fixed
    assert "updated_at:" in fixed


def test_remediate_markdown_doc_adds_mermaid_for_design_types():
    raw = """---
doc_id: as.doc.ckg.sample-hld
title: Sample HLD
doc_type: design
status: proposed
schema_version: "1.0"
owner: platform-docs
summary: Sample high-level design for remediation.
tags: [test]
phase: "07-code-knowledge-graph"
canonical_path: docs/07-code-knowledge-graph/99-sample-hld.md
---

# Sample HLD

Body without purpose or diagram.
"""
    rel = "docs/07-code-knowledge-graph/99-sample-hld.md"
    fixed = remediate_markdown_doc(relative_path=rel, text=raw)
    row = check_markdown_doc(relative_path=rel, text=fixed)
    assert row["ok"] is True, row["issues"]
    assert "```mermaid" in fixed.lower()
    assert "| Step | Actor | Action | Outcome |" in fixed
    assert "doc_type: hld" in fixed
    assert "status: draft" in fixed


def test_remediate_normalizes_concern_and_keeps_evidence_links(tmp_path: Path):
    code = tmp_path / "backend" / "packages" / "demo" / "mod.py"
    code.parent.mkdir(parents=True)
    code.write_text("def sync_repo():\n    return 1\n", encoding="utf-8")
    raw = """---
doc_id: as.doc.ckg.sample-link
title: Sample Link Doc
doc_type: standard
status: active
schema_version: "1.0"
owner: platform-docs
summary: Sample document that cites an implementation symbol for graph linking tests.
tags: [test]
phase: "07-code-knowledge-graph"
canonical_path: docs/07-code-knowledge-graph/99-sample-link.md
concern_lane: architecture
---

# Sample Link Doc

## Purpose

Sample document that cites an implementation symbol for graph linking tests.

See `backend/packages/demo/mod.py` during ingest.
"""
    rel = "docs/07-code-knowledge-graph/99-sample-link.md"
    fixed = remediate_markdown_doc(relative_path=rel, text=raw, repo=tmp_path)
    assert "concern_lane: design" in fixed
    assert "backend/packages/demo/mod.py::sync_repo" in fixed
    row = check_markdown_doc(relative_path=rel, text=fixed)
    assert row["ok"] is True, row["issues"]


def test_repo_docs_tree_meets_docs_standards():
    # Canonical product trees stay clean; sync-mode may include extra service docs.
    from astloom_cli.commands.docs_standards.scope import DEFAULT_DOC_ROOTS

    root = repo_root()
    report = build_docs_standards_report(
        roots=[root / name for name in DEFAULT_DOC_ROOTS],
        repo=root,
    )
    assert report["summary"]["total"] > 0
    assert report["summary"]["nonconforming_count"] == 0, report["top_nonconforming"][:20]
    assert report.get("scan_mode") == "roots"


def test_service_api_contract_docs_pass_full_tier():
    """Service-local API contracts are official product docs and must pass Full-tier."""
    root = repo_root()
    paths = sorted((root / "backend" / "services").glob("*/docs/*api*.md"))
    assert paths, "expected service API contract Markdown"
    from astloom_cli.commands.docs_standards.check import check_file

    failures = []
    for path in paths:
        rel = str(path.relative_to(root)).replace("\\", "/")
        row = check_file(path, root=root)
        if not row.get("ok"):
            failures.append((rel, row.get("issues")))
    assert not failures, failures[:5]


def test_check_ignores_h1_inside_fences():
    text = GOOD_DOC.replace(
        "## Related Documents\n\n- none\n",
        "## Related Documents\n\n```yaml\n# NN - Example Title\n```\n\n- none\n",
    )
    row = check_markdown_doc(
        relative_path="docs/00-master-plan/01-good-doc.md",
        text=text,
    )
    assert row["ok"] is True
    assert "multiple_h1" not in row["issues"]


def test_build_report_percent(tmp_path: Path):
    docs = tmp_path / "docs" / "00-master-plan"
    docs.mkdir(parents=True)
    (docs / "01-good-doc.md").write_text(GOOD_DOC, encoding="utf-8")
    (docs / "02-bad.md").write_text("# Bad\n", encoding="utf-8")
    report = build_docs_standards_report(roots=[tmp_path / "docs"], repo=tmp_path)
    assert report["summary"]["total"] == 2
    assert report["summary"]["conforming_count"] == 1
    assert report["summary"]["nonconforming_count"] == 1
    assert report["summary"]["percent_nonconforming"] == 50.0
    assert report["summary"]["revision_debt_count"] == 0
    assert report["nonconforming"][0]["file"] == "docs/00-master-plan/02-bad.md"


def test_build_report_revision_debt(tmp_path: Path):
    docs = tmp_path / "docs" / "00-master-plan"
    docs.mkdir(parents=True)
    missing = GOOD_DOC.replace("doc_version: \"1.0.0\"\n", "").replace(
        "updated_at: \"2026-07-24\"\n", ""
    )
    invalid = GOOD_DOC.replace('doc_version: "1.0.0"', 'doc_version: "not-a-semver"')
    (docs / "01-missing-rev.md").write_text(missing, encoding="utf-8")
    (docs / "02-bad-rev.md").write_text(invalid, encoding="utf-8")
    report = build_docs_standards_report(roots=[tmp_path / "docs"], repo=tmp_path)
    assert report["summary"]["revision_debt_count"] == 2
    files = {r["file"] for r in report["revision_debt"]}
    assert "docs/00-master-plan/01-missing-rev.md" in files
    assert "docs/00-master-plan/02-bad-rev.md" in files
    text = format_detail_text(report)
    assert "Revision debt" in text
    assert "missing_recommended:doc_version" in text or "invalid_doc_version" in text


def test_format_detail_text_and_save(tmp_path: Path, monkeypatch, capsys):
    report = {
        "repo": str(tmp_path),
        "roots": [str(tmp_path / "docs")],
        "summary": {
            "total": 2,
            "conforming_count": 1,
            "nonconforming_count": 1,
            "percent_conforming": 50.0,
            "percent_nonconforming": 50.0,
            "revision_debt_count": 1,
            "percent_revision_debt": 50.0,
        },
        "nonconforming": [
            {
                "file": "docs/a.md",
                "ok": False,
                "issue_count": 1,
                "issues": ["missing_or_invalid_frontmatter"],
                "doc_id": None,
                "doc_type": None,
                "status": None,
            }
        ],
        "conforming": [{"file": "docs/b.md", "ok": True, "issue_count": 0, "issues": []}],
        "revision_debt": [
            {
                "file": "docs/b.md",
                "ok": True,
                "warnings": ["missing_recommended:doc_version"],
                "issues": [],
                "doc_version": None,
                "updated_at": None,
            }
        ],
        "top_revision_debt": [
            {
                "file": "docs/b.md",
                "ok": True,
                "warnings": ["missing_recommended:doc_version"],
                "issues": [],
                "doc_version": None,
                "updated_at": None,
            }
        ],
        "top_nonconforming": [
            {
                "file": "docs/a.md",
                "ok": False,
                "issue_count": 1,
                "issues": ["missing_or_invalid_frontmatter"],
                "doc_id": None,
                "doc_type": None,
                "status": None,
            }
        ],
        "top_n": 10,
    }
    text = format_detail_text(report)
    assert "50.0%" in text
    assert "docs/a.md" in text
    assert "missing_or_invalid_frontmatter" in text
    assert "Revision debt" in text
    assert "docs/b.md" in text

    monkeypatch.setattr(
        "astloom_cli.commands.docs_standards.cmd.build_docs_standards_report",
        lambda: report,
    )
    out = tmp_path / "details.txt"
    args = argparse.Namespace(words=["detail", "save", str(out)])
    assert cmd_docs_standards(args) == 0
    saved = out.read_text(encoding="utf-8")
    assert "docs/a.md" in saved
    captured = capsys.readouterr().out
    assert "Docs standards" in captured
    assert "Saved" in captured

"""Tests for pre-sync standards gate (skip nonconforming docs)."""

from __future__ import annotations

from pathlib import Path

import pytest

from astloom_cli.parser import build_parser
from astloom_cli.sync_standards_gate import (
    apply_nonconforming_excludes,
    list_nonconforming_docs,
    path_to_exclude_glob,
    resolve_standards_gate,
)

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
canonical_path: docs/good.md
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

BAD_DOC = """# Missing frontmatter

Just a title and no Full-tier metadata.
"""


def _write_sync_yaml(root: Path) -> None:
    (root / "astloom.sync.yaml").write_text(
        "code:\n  exclude: []\ndocs:\n  match:\n    - '**/*.md'\n  exclude: []\n",
        encoding="utf-8",
    )


def test_parser_standards_gate_flags():
    parser = build_parser()
    assert parser.parse_args(["sync"]).skip_nonconforming is False
    assert parser.parse_args(["sync"]).sync_nonconforming is False
    assert parser.parse_args(["sync", "--skip-nonconforming"]).skip_nonconforming is True
    assert parser.parse_args(["sync", "--sync-nonconforming"]).sync_nonconforming is True


def test_path_to_exclude_glob_normalizes():
    assert path_to_exclude_glob("./docs/a.md") == "docs/a.md"
    assert path_to_exclude_glob("docs\\b.md") == "docs/b.md"


def test_apply_nonconforming_excludes_dedupes():
    filters = {
        "doc_exclude_globs": ["docs/keep.md"],
        "exclude_globs": ["src/a.py"],
    }
    out = apply_nonconforming_excludes(
        filters,
        docs=["docs/keep.md", "docs/bad.md"],
        code=["src/a.py", "src/b.py"],
    )
    assert out["doc_exclude_globs"] == ["docs/keep.md", "docs/bad.md"]
    assert out["exclude_globs"] == ["src/a.py", "src/b.py"]
    assert filters["doc_exclude_globs"] == ["docs/keep.md"]


def test_list_nonconforming_docs(tmp_path: Path):
    _write_sync_yaml(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "good.md").write_text(GOOD_DOC, encoding="utf-8")
    (docs / "bad.md").write_text(BAD_DOC, encoding="utf-8")
    # Package README is Phase-2-discoverable but never Full-tier-audited.
    pkg = tmp_path / "backend" / "apps" / "api-gateway"
    pkg.mkdir(parents=True)
    (pkg / "README.md").write_text(BAD_DOC, encoding="utf-8")
    skill = tmp_path / "skills"
    skill.mkdir()
    (skill / "demo.md").write_text(
        "---\nname: demo\ndescription: skill frontmatter\n---\n\n# Demo\n",
        encoding="utf-8",
    )
    filters = {
        "docs_enabled": True,
        "doc_match_globs": ["**/*.md"],
        "doc_exclude_dirs": [],
        "doc_exclude_globs": [],
        "doc_audit_exclude_globs": [],
        "doc_paths": [],
        "max_files": 100,
    }
    bad = list_nonconforming_docs(root_path=tmp_path, filters=filters)
    assert "docs/bad.md" in bad
    assert "docs/good.md" not in bad
    assert "backend/apps/api-gateway/README.md" not in bad
    # Non-README Markdown under sync match is audited unless audit.exclude says so.
    assert "skills/demo.md" in bad
    filters["doc_audit_exclude_globs"] = ["skills/**"]
    bad2 = list_nonconforming_docs(root_path=tmp_path, filters=filters)
    assert "skills/demo.md" not in bad2
    assert "docs/bad.md" in bad2


def test_is_docs_audit_path_skips_readme_and_custom_globs():
    from astloom_cli.commands.docs_standards.scope import (
        is_docs_audit_basename_skipped,
        is_docs_audit_path,
    )

    assert is_docs_audit_basename_skipped("backend/x/README.md") is True
    assert is_docs_audit_path("docs/a.md") is True
    assert is_docs_audit_path("backend/apps/api-gateway/README.md") is False
    assert is_docs_audit_path("AGENTS.md") is False
    assert is_docs_audit_path(
        "vendor/notes.md",
        audit_exclude_globs=["vendor/**"],
    ) is False
    assert is_docs_audit_path("backend/services/memory-service/docs/api.md") is True


def test_resolve_sync_filters_merges_docs_audit_exclude(tmp_path: Path):
    from astloom_cli.sync_config import resolve_sync_filters

    (tmp_path / "astloom.sync.yaml").write_text(
        "code:\n  exclude: []\n"
        "docs:\n  match: ['**/*.md']\n  exclude: []\n"
        "  audit:\n    exclude:\n      - 'vendor/**'\n",
        encoding="utf-8",
    )
    filters = resolve_sync_filters(root=tmp_path)
    assert "**/README.md" in filters["doc_audit_exclude_globs"]
    assert "vendor/**" in filters["doc_audit_exclude_globs"]



def test_resolve_skip_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _write_sync_yaml(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "bad.md").write_text(BAD_DOC, encoding="utf-8")
    filters = {
        "docs_enabled": True,
        "doc_match_globs": ["**/*.md"],
        "doc_exclude_dirs": [],
        "doc_exclude_globs": [],
        "doc_paths": [],
        "exclude_globs": [],
        "max_files": 100,
        "sources": [],
    }
    monkeypatch.setattr(
        "astloom_cli.sync_standards_gate.list_nonconforming_docs",
        lambda **_kwargs: ["docs/bad.md"],
    )
    out, result = resolve_standards_gate(
        root_path=tmp_path,
        filters=filters,
        skip_nonconforming=True,
    )
    assert result.skipped is True
    assert result.skipped_docs == ["docs/bad.md"]
    assert "docs/bad.md" in out["doc_exclude_globs"]


def test_resolve_sync_nonconforming_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    filters = {
        "docs_enabled": True,
        "doc_match_globs": ["**/*.md"],
        "doc_exclude_globs": [],
        "exclude_globs": [],
    }
    monkeypatch.setattr(
        "astloom_cli.sync_standards_gate.list_nonconforming_docs",
        lambda **_kwargs: ["docs/bad.md"],
    )
    out, result = resolve_standards_gate(
        root_path=tmp_path,
        filters=filters,
        sync_nonconforming=True,
    )
    assert result.skipped is False
    assert out["doc_exclude_globs"] == []


def test_resolve_ask_default_no(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    filters = {
        "docs_enabled": True,
        "doc_match_globs": ["**/*.md"],
        "doc_exclude_globs": [],
        "exclude_globs": [],
    }
    monkeypatch.setattr(
        "astloom_cli.sync_standards_gate.list_nonconforming_docs",
        lambda **_kwargs: ["docs/bad.md"],
    )
    answers = iter([""])  # default N = include (do not skip)
    out, result = resolve_standards_gate(
        root_path=tmp_path,
        filters=filters,
        input_fn=lambda _prompt: next(answers),
        stdin_isatty=True,
    )
    assert result.mode == "ask"
    assert result.skipped is False
    assert out["doc_exclude_globs"] == []


def test_resolve_ask_yes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    filters = {
        "docs_enabled": True,
        "doc_match_globs": ["**/*.md"],
        "doc_exclude_globs": [],
        "exclude_globs": [],
    }
    monkeypatch.setattr(
        "astloom_cli.sync_standards_gate.list_nonconforming_docs",
        lambda **_kwargs: ["docs/bad.md"],
    )
    out, result = resolve_standards_gate(
        root_path=tmp_path,
        filters=filters,
        input_fn=lambda _prompt: "y",
        stdin_isatty=True,
    )
    assert result.mode == "ask"
    assert result.skipped is True
    assert "docs/bad.md" in out["doc_exclude_globs"]


def test_resolve_ask_no(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    filters = {
        "docs_enabled": True,
        "doc_match_globs": ["**/*.md"],
        "doc_exclude_globs": [],
        "exclude_globs": [],
    }
    monkeypatch.setattr(
        "astloom_cli.sync_standards_gate.list_nonconforming_docs",
        lambda **_kwargs: ["docs/bad.md"],
    )
    out, result = resolve_standards_gate(
        root_path=tmp_path,
        filters=filters,
        input_fn=lambda _prompt: "n",
        stdin_isatty=True,
    )
    assert result.skipped is False
    assert out["doc_exclude_globs"] == []


def test_resolve_non_tty_includes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    filters = {
        "docs_enabled": True,
        "doc_match_globs": ["**/*.md"],
        "doc_exclude_globs": [],
        "exclude_globs": [],
    }
    monkeypatch.setattr(
        "astloom_cli.sync_standards_gate.list_nonconforming_docs",
        lambda **_kwargs: ["docs/bad.md"],
    )
    out, result = resolve_standards_gate(
        root_path=tmp_path,
        filters=filters,
        stdin_isatty=False,
    )
    assert result.mode == "include"
    assert result.skipped is False
    assert out["doc_exclude_globs"] == []


def test_conflicting_flags_exit(tmp_path: Path):
    with pytest.raises(SystemExit, match="only one of"):
        resolve_standards_gate(
            root_path=tmp_path,
            filters={"docs_enabled": False},
            skip_nonconforming=True,
            sync_nonconforming=True,
        )


def test_code_nonconforming_applied_when_skip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "astloom_cli.sync_standards_gate.list_nonconforming_docs",
        lambda **_kwargs: [],
    )
    filters = {"doc_exclude_globs": [], "exclude_globs": []}
    out, result = resolve_standards_gate(
        root_path=tmp_path,
        filters=filters,
        skip_nonconforming=True,
        code_nonconforming=["src/bad.py"],
    )
    assert result.skipped_code == ["src/bad.py"]
    assert "src/bad.py" in out["exclude_globs"]

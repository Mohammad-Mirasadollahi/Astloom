"""Tests for quality-audit MCP payload + sync follow-up tasks + linking hard gate."""

from __future__ import annotations

from pathlib import Path

from astloom_cli.commands.docs_standards.check import check_markdown_doc
from astloom_cli.commands.quality_audit.mcp_payload import compact_quality_audit_payload
from astloom_cli.sync_followup_tasks import create_sync_followup_tasks
from astloom_cli.sync_standards_gate import StandardsGateResult


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


def test_compact_quality_audit_payload_marks_must_remediate():
    report = {
        "repo": "/tmp/r",
        "generated_at": "t",
        "summary": {"findings_total": 1},
        "categories": [],
        "findings": [
            {
                "category": "docs.size_soft",
                "severity": "medium",
                "title": "soft",
                "path": "docs/a.md",
                "detail": "body_over_soft_budget:410",
                "evidence": [],
                "fix_hint": "split",
            }
        ],
    }
    payload = compact_quality_audit_payload(report, top_n=10)
    assert payload["must_remediate"] is True
    assert payload["actionable_count"] == 1
    assert payload["findings"][0]["path"] == "docs/a.md"
    assert "astloom-quality-audit" in payload["agent_instruction"]


def test_linking_gap_is_hard_issue_when_repo_provided(tmp_path: Path):
    code = tmp_path / "backend" / "packages" / "demo" / "mod.py"
    code.parent.mkdir(parents=True)
    code.write_text("def sync_repo():\n    return 1\n", encoding="utf-8")
    docs = tmp_path / "docs" / "00-master-plan"
    docs.mkdir(parents=True)
    text = GOOD_DOC.replace(
        "## Related Documents\n\n- none\n",
        "## Related Documents\n\nSee `backend/packages/demo/mod.py` for sync.\n",
    ).replace(
        'canonical_path: docs/00-master-plan/01-good-doc.md',
        'canonical_path: docs/00-master-plan/01-good-doc.md',
    )
    without_repo = check_markdown_doc(
        relative_path="docs/00-master-plan/01-good-doc.md",
        text=text,
    )
    assert without_repo["ok"] is True
    with_repo = check_markdown_doc(
        relative_path="docs/00-master-plan/01-good-doc.md",
        text=text,
        repo=tmp_path,
    )
    assert with_repo["ok"] is False
    assert any(str(i).startswith("missing_linked_symbols") for i in with_repo["issues"])


def test_create_sync_followup_tasks_writes_mirror(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "astloom_cli.sync_followup_tasks.repo_root",
        lambda: tmp_path,
    )

    def _boom(scope):
        raise RuntimeError("skip core create in mirror-only test")

    monkeypatch.setattr(
        "astloom_cli.sync_followup_tasks.open_platform_backends",
        _boom,
    )
    gate = StandardsGateResult(
        mode="skip",
        skipped=True,
        docs_nonconforming=["docs/a.md"],
        skipped_docs=["docs/a.md"],
    )

    class _Scope:
        tenant_id = "t"
        workspace_id = "w"
        project_id = "p"

    out = create_sync_followup_tasks(
        scope=_Scope(),
        standards_gate=gate,
        include_code_audit=False,
    )
    assert out["specs_count"] == 1
    mirror = Path(out["mirror_path"])
    assert mirror.is_file()
    assert "docs/a.md" in mirror.read_text(encoding="utf-8")


def test_ensure_platform_imports_exposes_core_data():
    """Regression: follow-up tasks need core-data on sys.path (was silent created=0)."""
    import sys

    from astloom_cli.followup_task_lifecycle import ensure_platform_imports

    ensure_platform_imports()
    assert any("core-data-service" in p for p in sys.path)
    assert any("mcp-gateway-service" in p for p in sys.path)
    import core_data_service  # noqa: F401
    import mcp_gateway_service  # noqa: F401


def test_create_sync_followup_surfaces_create_errors(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "astloom_cli.sync_followup_tasks.repo_root",
        lambda: tmp_path,
    )

    def _boom(scope):
        raise RuntimeError("platform down")

    monkeypatch.setattr(
        "astloom_cli.sync_followup_tasks.open_platform_backends",
        _boom,
    )
    gate = StandardsGateResult(
        mode="skip",
        skipped=True,
        skipped_docs=["docs/a.md"],
        docs_nonconforming=["docs/a.md"],
    )

    class _Scope:
        tenant_id = "t"
        workspace_id = "w"
        project_id = "p"

    out = create_sync_followup_tasks(
        scope=_Scope(),
        standards_gate=gate,
        include_code_audit=False,
    )
    assert out["tasks_created_count"] == 0
    assert out["create_errors"]
    assert "platform down" in out["create_errors"][0]

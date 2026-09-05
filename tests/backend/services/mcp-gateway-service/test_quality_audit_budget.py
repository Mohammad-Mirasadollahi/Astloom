"""quality_audit MCP soft budget + deadline."""

from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from mcp_gateway_service.backends.quality import (
    _quality_audit_budget_seconds,
    quality_audit,
)


def test_quality_audit_budget_leaves_headroom_under_tool_timeout(monkeypatch):
    monkeypatch.setenv("ASTLOOM_MCP_TOOL_TIMEOUT_SECONDS", "25")
    monkeypatch.setenv("ASTLOOM_MCP_QUALITY_AUDIT_BUDGET_SECONDS", "40")
    assert _quality_audit_budget_seconds() == 19.0


def test_quality_audit_passes_deadline_to_collect(tmp_path: Path, monkeypatch):
    app = tmp_path / "app"
    app.mkdir()
    monkeypatch.setattr(
        "astloom_cli.software_paths.software_paths_for_project",
        lambda *a, **k: [str(app)],
    )
    seen: dict[str, float | None] = {"deadline": None}

    def _fake_report(*, repos=None, args=None, deadline_monotonic=None, scope=None):
        seen["deadline"] = deadline_monotonic
        seen["scope"] = scope
        return {
            "ok": True,
            "degraded": True,
            "truncated_phases": ["code"],
            "repo": str(Path(repos[0]).resolve()),
            "repos": [str(Path(repos[0]).resolve())],
            "generated_at": "2026-09-05T00:00:00Z",
            "summary": {"findings_total": 0, "degraded": True},
            "categories": [],
            "findings": [],
        }

    monkeypatch.setattr(
        "astloom_cli.commands.quality_audit.collect.build_quality_audit_report",
        _fake_report,
    )
    backends = SimpleNamespace(docs=None, docs_scope=lambda _s: None)
    t0 = time.monotonic()
    out = quality_audit(
        backends,
        {"create_tasks": False, "top_n": 3},
        scope={"tenant_id": "t", "workspace_id": "w", "project_id": "p"},
        correlation_id=str(uuid4()),
        base={"maps_to": "quality.audit"},
    )
    assert out["ok"] is True
    assert out.get("degraded") is True
    assert seen["deadline"] is not None
    assert seen["deadline"] > t0
    assert seen["deadline"] < t0 + 30

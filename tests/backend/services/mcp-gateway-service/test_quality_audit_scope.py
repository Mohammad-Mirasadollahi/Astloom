"""Quality-audit MCP binds to project software paths, not the Astloom install."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from mcp_gateway_service.backends.quality import quality_audit


def test_quality_audit_errors_when_project_has_no_paths(monkeypatch):
    monkeypatch.setattr(
        "astloom_cli.software_paths.software_paths_for_project",
        lambda *a, **k: [],
    )
    backends = SimpleNamespace(docs=None, docs_scope=lambda _s: None)
    out = quality_audit(
        backends,
        {"create_tasks": False, "top_n": 3},
        scope={"tenant_id": "mir", "workspace_id": "dev", "project_id": "demo-app"},
        correlation_id=str(uuid4()),
        base={"maps_to": "quality.audit"},
    )
    assert out["ok"] is False
    assert out["repo"] is None
    assert "no software paths" in out["error"]


def test_quality_audit_uses_pinned_project_root(tmp_path: Path, monkeypatch):
    app = tmp_path / "demo-app"
    app.mkdir()
    monkeypatch.setattr(
        "astloom_cli.software_paths.software_paths_for_project",
        lambda *a, **k: [str(app)],
    )

    def _fake_report(*, repos=None, args=None, deadline_monotonic=None, scope=None):
        assert repos is not None
        assert Path(repos[0]) == app.resolve()
        return {
            "ok": True,
            "repo": str(Path(repos[0]).resolve()),
            "repos": [str(Path(repos[0]).resolve())],
            "generated_at": "2026-09-04T00:00:00Z",
            "summary": {"findings_total": 0},
            "categories": [],
            "findings": [],
        }

    monkeypatch.setattr(
        "astloom_cli.commands.quality_audit.collect.build_quality_audit_report",
        _fake_report,
    )
    backends = SimpleNamespace(docs=None, docs_scope=lambda _s: None)
    out = quality_audit(
        backends,
        {"create_tasks": False, "top_n": 3},
        scope={"tenant_id": "mir", "workspace_id": "dev", "project_id": "demo-app"},
        correlation_id=str(uuid4()),
        base={"maps_to": "quality.audit"},
    )
    assert out["ok"] is True
    assert out["repo"] == str(app.resolve())
    assert "astloom_cli" not in (out.get("repo") or "").lower()


def test_quality_audit_passes_mcp_graph_scope(tmp_path: Path, monkeypatch):
    app = tmp_path / "demo-app"
    app.mkdir()
    monkeypatch.setattr(
        "astloom_cli.software_paths.software_paths_for_project",
        lambda *a, **k: [str(app)],
    )
    seen: dict[str, object] = {}

    def _fake_report(*, repos=None, args=None, deadline_monotonic=None, scope=None):
        seen["scope"] = scope
        return {
            "ok": True,
            "repo": str(Path(repos[0]).resolve()),
            "repos": [str(Path(repos[0]).resolve())],
            "generated_at": "2026-09-05T00:00:00Z",
            "summary": {"findings_total": 0},
            "categories": [],
            "findings": [],
        }

    monkeypatch.setattr(
        "astloom_cli.commands.quality_audit.collect.build_quality_audit_report",
        _fake_report,
    )
    graph_scope = SimpleNamespace(tenant_id="mir", workspace_id="dev", project_id="demo-app")
    backends = SimpleNamespace(
        docs=None,
        docs_scope=lambda _s: None,
        graph_scope=lambda _s: graph_scope,
    )
    out = quality_audit(
        backends,
        {"create_tasks": False, "top_n": 3},
        scope={"tenant_id": "mir", "workspace_id": "dev", "project_id": "demo-app"},
        correlation_id=str(uuid4()),
        base={"maps_to": "quality.audit"},
    )
    assert out["ok"] is True
    assert seen["scope"] is graph_scope

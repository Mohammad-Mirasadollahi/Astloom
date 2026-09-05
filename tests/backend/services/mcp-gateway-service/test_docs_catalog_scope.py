"""docs_catalog MCP binds to pinned software paths, not the Astloom install."""

from __future__ import annotations

from pathlib import Path

from mcp_gateway_service.backends.docs import docs_catalog


def test_docs_catalog_fail_closed_when_pin_not_visible(tmp_path: Path, monkeypatch):
    missing = tmp_path / "ThinkingSOC"
    monkeypatch.setattr(
        "astloom_cli.software_paths.software_paths_for_project",
        lambda *a, **k: [str(missing)],
    )
    monkeypatch.setattr("astloom_cli.util.repo_root", lambda: "/opt/Astloom")
    out = docs_catalog(
        {"refresh": False},
        base={"maps_to": "docs_sync.catalog"},
        scope={"tenant_id": "mir", "workspace_id": "dev", "project_id": "ThinkingSOC"},
    )
    assert out["ok"] is False
    assert "/opt/Astloom" not in str(out.get("repo") or "")
    assert "ThinkingSOC" in str(out.get("repo") or "")
    assert "does not exist" in str(out.get("error") or "").lower() or "not visible" in str(
        out.get("error") or ""
    ).lower()
    assert out["documents"] == []


def test_docs_catalog_uses_visible_pin(tmp_path: Path, monkeypatch):
    app = tmp_path / "ThinkingSOC"
    app.mkdir()
    (app / "README.md").write_text("# app\n", encoding="utf-8")
    monkeypatch.setattr(
        "astloom_cli.software_paths.software_paths_for_project",
        lambda *a, **k: [str(app)],
    )
    monkeypatch.setattr("astloom_cli.util.repo_root", lambda: "/opt/Astloom")
    captured: list[Path] = []

    def _fake_catalog(root, *, refresh=False, roots=None):
        captured.append(Path(root).resolve())
        return {
            "mode": "docs_catalog",
            "repo": str(Path(root).resolve()),
            "documents": [],
            "entries": [],
            "stats": {"document_count": 0},
        }

    monkeypatch.setattr("astloom_cli.docs_catalog.get_docs_catalog", _fake_catalog)
    monkeypatch.setattr(
        "astloom_cli.docs_catalog.filter_docs_catalog",
        lambda catalog, **_k: catalog,
    )
    out = docs_catalog(
        {"refresh": False},
        base={"maps_to": "docs_sync.catalog"},
        scope={"tenant_id": "mir", "workspace_id": "dev", "project_id": "ThinkingSOC"},
    )
    assert captured
    assert captured[0] == app.resolve()
    assert "/opt/Astloom" not in str(out.get("repo") or captured[0])

"""Unit: explore MCP redacts bodies when disk hash differs / file missing."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from code_graph_service.domain.hashing import content_hash
from code_graph_service.domain.models import Scope
from mcp_gateway_service.backends.code_graph.query import _apply_disk_freshness_to_explore


def test_explore_redacts_stale_and_missing_bodies(tmp_path: Path, monkeypatch):
    app = tmp_path / "app"
    app.mkdir()
    rel = "src/milky.py"
    path = app / rel
    path.parent.mkdir(parents=True)
    path.write_text("def live():\n    return 1\n", encoding="utf-8")
    stored_hash = content_hash("def old():\n    return 0\n", "python")["hash"]
    missing_rel = "src/gone.py"

    scope = Scope("mir", "dev", "demo")
    file_sym = SimpleNamespace(file_path=rel, hash_value=stored_hash)

    monkeypatch.setattr(
        "astloom_cli.software_paths.software_paths_for_project",
        lambda *a, **k: [str(app)],
    )
    monkeypatch.setattr(
        "code_graph_service.domain.ports.list_file_symbols_for_paths",
        lambda store, sc, paths: [file_sym],
    )

    backends = SimpleNamespace(
        graph=SimpleNamespace(store=object()),
        graph_scope=lambda s: scope,
    )
    payload = {
        "sections": [
            {
                "file_path": rel,
                "skeletonized": False,
                "symbols": [
                    {
                        "id": "sym:1",
                        "name": "old",
                        "body": "def old():\n    return 0\n",
                    }
                ],
            },
            {
                "file_path": missing_rel,
                "skeletonized": False,
                "symbols": [{"id": "sym:2", "name": "gone", "body": "def gone():\n    pass\n"}],
            },
        ],
        "notes": [],
        "freshness": {"status": "ok", "is_stale": False},
    }
    out = _apply_disk_freshness_to_explore(
        backends,
        {"tenant_id": "mir", "workspace_id": "dev", "project_id": "demo"},
        payload,
    )
    assert out["freshness"]["is_stale"] is True
    assert out["freshness"]["must_sync"] is True
    assert out["freshness"]["bodies_redacted"] is True
    assert out["sections"][0]["symbols"][0]["body"] == ""
    assert out["sections"][0]["symbols"][0]["body_redacted"] is True
    assert out["sections"][1]["disk_freshness"] == "missing_on_disk"
    assert "Graph stale vs disk" in (out["freshness"].get("banner") or "")

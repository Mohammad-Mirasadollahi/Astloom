"""MCP code_graph.sync forwards embedding_refresh_mode (CLI sync heal parity)."""

from __future__ import annotations

from types import SimpleNamespace

from mcp_gateway_service.backends.code_graph.write import sync_repo


class _Graph:
    def __init__(self) -> None:
        self.payloads: list[dict] = []

    def sync_repo(self, scope, actor_id, correlation_id, idempotency_key, payload):
        self.payloads.append(dict(payload))
        return SimpleNamespace(
            to_dict=lambda: {
                "mode": "noop",
                "embedding_refresh": {"state": "complete", "refreshed": 0},
            }
        )


class _Backends:
    graph_mode = "memory"
    actor_id = "test-actor"

    def __init__(self) -> None:
        self.graph = _Graph()

    def graph_scope(self, scope):
        return SimpleNamespace(**scope)


def test_mcp_sync_repo_forwards_embedding_refresh_mode_full():
    backends = _Backends()
    out = sync_repo(
        backends,
        {
            "root_path": "/tmp/repo",
            "embedding_refresh_mode": "full",
            "max_files": 10,
        },
        scope={"tenant_id": "t", "workspace_id": "w", "project_id": "p"},
        correlation_id="c1",
        base={"ok": True},
    )
    assert backends.graph.payloads
    assert backends.graph.payloads[0]["embedding_refresh_mode"] == "full"
    assert out["sync"]["embedding_refresh_mode"] == "full"


def test_mcp_sync_repo_ignores_unknown_embedding_refresh_mode():
    backends = _Backends()
    sync_repo(
        backends,
        {"root_path": "/tmp/repo", "embedding_refresh_mode": "force-all"},
        scope={"tenant_id": "t", "workspace_id": "w", "project_id": "p"},
        correlation_id="c2",
        base={"ok": True},
    )
    assert "embedding_refresh_mode" not in backends.graph.payloads[0]

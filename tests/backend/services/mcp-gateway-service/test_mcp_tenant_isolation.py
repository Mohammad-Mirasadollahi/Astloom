"""MCP code-graph scope isolation (backlog 34 D1 / GAP-005)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from mcp_gateway_service.backends import PlatformBackends, dispatch_capability
from mcp_gateway_service.store_factory import build_stores


def test_mcp_code_graph_search_isolated_by_tenant_and_project(monkeypatch):
    monkeypatch.setenv("ASTLOOM_MCP_GRAPH_SEED", "false")
    backends = PlatformBackends(
        build_stores({"ASTLOOM_MCP_STORE_MODE": "memory", "ASTLOOM_MCP_GRAPH_MODE": "memory"})
    )
    scope_a = {"tenant_id": "tenant-a", "workspace_id": "w", "project_id": "p"}
    scope_b = {"tenant_id": "tenant-b", "workspace_id": "w", "project_id": "p"}
    scope_c = {"tenant_id": "tenant-a", "workspace_id": "w", "project_id": "other"}

    dispatch_capability(
        backends,
        "code_graph.ingest_file",
        {
            "file_path": "src/secret.py",
            "language": "python",
            "source": "def tenant_a_only():\n    return 42\n",
        },
        scope=scope_a,
        usage_profile="programming-cursor-mcp",
        correlation_id=str(uuid4()),
    )

    found_a = dispatch_capability(
        backends,
        "code_graph.hybrid_search",
        {"query": "tenant_a_only", "top_k": 5},
        scope=scope_a,
        usage_profile="programming-cursor-mcp",
        correlation_id=str(uuid4()),
    )
    hits_a = found_a.get("hits") or []
    assert any("tenant_a_only" in str(h.get("qualified_name") or "") for h in hits_a)

    for foreign in (scope_b, scope_c):
        found = dispatch_capability(
            backends,
            "code_graph.hybrid_search",
            {"query": "tenant_a_only", "top_k": 5},
            scope=foreign,
            usage_profile="programming-cursor-mcp",
            correlation_id=str(uuid4()),
        )
        hits = found.get("hits") or []
        leaked = [h for h in hits if "tenant_a_only" in str(h.get("qualified_name") or "")]
        assert leaked == [], f"cross-scope leak into {foreign}: {leaked}"

        with pytest.raises(Exception):
            dispatch_capability(
                backends,
                "code_graph.get_symbol",
                {"qualified_name": "tenant_a_only"},
                scope=foreign,
                usage_profile="programming-cursor-mcp",
                correlation_id=str(uuid4()),
            )

    backends.close()

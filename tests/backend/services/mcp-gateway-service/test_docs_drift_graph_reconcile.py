"""Regression: docs_drift_check must honor Neo4j/graph human DOCUMENTED_BY.

docs-sync Postgres anchors are not the SoT for Phase-2 human links. When the
code graph already has a human DOCUMENTED_BY edge, MCP drift must not invent a
docs-sync orphan and report false missing_doc.
"""

from __future__ import annotations

from mcp_gateway_service.backends import docs as docs_backend
from mcp_gateway_service.backends.platform import PlatformBackends
from mcp_gateway_service.store_factory import build_stores


def _backends() -> PlatformBackends:
    return PlatformBackends(
        build_stores(
            {
                "ASTLOOM_MCP_STORE_MODE": "memory",
                "ASTLOOM_MCP_GRAPH_MODE": "memory",
            }
        )
    )


def test_drift_check_false_when_graph_has_human_documented_by():
    backends = _backends()
    scope = {"tenant_id": "t", "workspace_id": "w", "project_id": "p"}
    graph_scope = backends.graph_scope(scope)
    backends.graph.ingest_file(
        graph_scope,
        backends.actor_id,
        "corr-ingest",
        "k-ingest",
        {
            "file_path": "src/auth.py",
            "language": "python",
            "source": (
                "def login(user, password):\n"
                "    return len(password) > 8\n"
            ),
        },
    )
    linked = backends.graph.upsert_human_documentation(
        graph_scope,
        doc_id="doc-login-rules",
        relative_path="docs/login.md",
        body="# Login\n\nRules for login.",
        title="Login rules",
        linked_symbol_tokens=["src.auth.login"],
    )
    assert linked["linked_symbol_ids"]

    # Short name + misleading file_path previously created an orphan docs-sync
    # symbol with no anchors → false missing_doc.
    result = docs_backend.docs_drift_check(
        backends,
        {"symbol": "login", "file_path": "totally/wrong/path.py"},
        scope=scope,
        correlation_id="corr-drift-human",
        base={"backend": "in_process"},
    )
    assert result["drift"] is False
    assert result["findings"] == []
    assert result["lookup_source"] == "graph"
    assert result["documented_by"]
    assert any(str(item.get("target_id", "")).startswith("doc:human:") for item in result["documented_by"])

    # Must not pollute docs-sync with a new required orphan for this call.
    docs_symbols = backends.docs.store.list_symbols(backends.docs_scope(scope))
    assert not any(s.symbol_path == "login" and s.file_path == "totally/wrong/path.py" for s in docs_symbols)


def test_drift_check_still_true_without_human_documented_by():
    backends = _backends()
    scope = {"tenant_id": "t", "workspace_id": "w", "project_id": "p"}
    graph_scope = backends.graph_scope(scope)
    backends.graph.ingest_file(
        graph_scope,
        backends.actor_id,
        "corr-ingest-2",
        "k-ingest-2",
        {
            "file_path": "src/auth/hash.py",
            "language": "python",
            "source": "def hash_password(value: str) -> str:\n    return value\n",
        },
    )

    result = docs_backend.docs_drift_check(
        backends,
        {"symbol": "hash_password", "file_path": "src/auth/hash.py"},
        scope=scope,
        correlation_id="corr-drift-missing",
        base={"backend": "in_process"},
    )
    assert result["drift"] is True
    assert result["findings"]
    assert result.get("lookup_source") != "graph"

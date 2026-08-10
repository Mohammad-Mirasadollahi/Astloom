from __future__ import annotations

from uuid import uuid4

from mcp_gateway_service.backends import PlatformBackends, dispatch_capability
from mcp_gateway_service.server import McpGateway, handle_message
from mcp_gateway_service.store_factory import build_stores, resolve_store_mode


def test_resolve_store_mode_defaults_to_memory(monkeypatch):
    monkeypatch.delenv("ASTLOOM_MCP_STORE_MODE", raising=False)
    monkeypatch.delenv("ASTLOOM_DATABASE_URL", raising=False)
    assert resolve_store_mode({}) == "memory"


def test_resolve_store_mode_postgres_when_url(monkeypatch):
    env = {"ASTLOOM_DATABASE_URL": "postgresql://astloom:x@127.0.0.1:32232/astloom"}
    assert resolve_store_mode(env) == "postgres"
    env["ASTLOOM_MCP_STORE_MODE"] = "memory"
    assert resolve_store_mode(env) == "memory"


def test_build_stores_memory_bundle():
    bundle = build_stores({"ASTLOOM_MCP_STORE_MODE": "memory"})
    assert bundle.mode == "memory"
    backends = PlatformBackends(bundle)
    assert backends.store_mode == "memory"
    ping = dispatch_capability(
        backends,
        "platform.ping",
        {},
        scope={"tenant_id": "t", "workspace_id": "w", "project_id": "p"},
        usage_profile="default",
        correlation_id=str(uuid4()),
    )
    assert ping["store_mode"] == "memory"
    backends.close()


def test_gateway_reports_store_mode():
    gw = McpGateway(
        profile_id="programming-cursor-mcp",
        tenant_id="t",
        workspace_id="w",
        project_id="p",
        backends=PlatformBackends(build_stores({"ASTLOOM_MCP_STORE_MODE": "memory"})),
    )
    result = handle_message(
        gw,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "astloom_ping", "arguments": {}},
        },
    )
    import json

    payload = json.loads(result["result"]["content"][0]["text"])
    assert payload["store_mode"] == "memory"
    gw.backends.close()


def test_build_stores_neo4j_failure_falls_back_to_memory(monkeypatch, caplog):
    import logging

    from mcp_gateway_service.store_factory import build_stores

    def boom(_settings):
        raise ConnectionRefusedError("Neo4j refused connection")

    monkeypatch.setattr("code_graph_service.bootstrap.build_service", boom)
    with caplog.at_level(logging.ERROR):
        bundle = build_stores(
            {
                "ASTLOOM_MCP_STORE_MODE": "memory",
                "ASTLOOM_MCP_GRAPH_MODE": "neo4j",
                "ASTLOOM_NEO4J_PASSWORD": "secret",
                "ASTLOOM_NEO4J_URI": "bolt://127.0.0.1:1",
            }
        )
    assert bundle.graph_mode == "memory"
    assert bundle.graph_service is None
    assert any("Neo4j graph unavailable" in r.message for r in caplog.records)
    bundle.close()


def test_build_stores_postgres_failure_falls_back_to_memory(monkeypatch, caplog):
    import logging

    from mcp_gateway_service.store_factory import build_stores

    class BoomStore:
        def __init__(self, *_args, **_kwargs):
            raise OSError("postgres down")

    monkeypatch.setattr(
        "core_data_service.postgres_store.PostgresStore",
        BoomStore,
    )
    with caplog.at_level(logging.ERROR):
        bundle = build_stores(
            {
                "ASTLOOM_MCP_STORE_MODE": "postgres",
                "ASTLOOM_DATABASE_URL": "postgresql://astloom:x@127.0.0.1:1/astloom",
                "ASTLOOM_MCP_GRAPH_MODE": "memory",
            }
        )
    assert bundle.mode == "memory"
    assert any("postgres stores unavailable" in r.message for r in caplog.records)
    bundle.close()


def test_code_graph_tools_neighbors_and_ingest():
    from uuid import uuid4

    from mcp_gateway_service.backends import PlatformBackends, dispatch_capability
    from mcp_gateway_service.store_factory import build_stores

    backends = PlatformBackends(build_stores({"ASTLOOM_MCP_STORE_MODE": "memory", "ASTLOOM_MCP_GRAPH_MODE": "memory"}))
    scope = {"tenant_id": "t", "workspace_id": "w", "project_id": "p"}
    ingested = dispatch_capability(
        backends,
        "code_graph.ingest_file",
        {
            "file_path": "src/util.py",
            "language": "python",
            "source": "def helper():\n    return 1\n\ndef caller():\n    return helper()\n",
        },
        scope=scope,
        usage_profile="programming-cursor-mcp",
        correlation_id=str(uuid4()),
    )
    assert ingested["graph_mode"] == "memory"
    assert ingested["ingest"]["symbols_indexed"] >= 2

    found = dispatch_capability(
        backends,
        "code_graph.get_symbol",
        {"qualified_name": "helper"},
        scope=scope,
        usage_profile="programming-cursor-mcp",
        correlation_id=str(uuid4()),
    )
    # qualified_name may be module-qualified depending on parser
    symbol = found["symbol"]
    assert "helper" in symbol["name"] or "helper" in symbol["qualified_name"]

    neighbors = dispatch_capability(
        backends,
        "code_graph.neighbors",
        {"symbol_id": symbol["id"], "max_depth": 1},
        scope=scope,
        usage_profile="programming-cursor-mcp",
        correlation_id=str(uuid4()),
    )
    assert "edges" in neighbors

    impact = dispatch_capability(
        backends,
        "code_graph.impact",
        {"symbol_id": symbol["id"], "max_depth": 2, "direction": "both"},
        scope=scope,
        usage_profile="programming-cursor-mcp",
        correlation_id=str(uuid4()),
    )
    assert impact["impact_of"] == symbol["id"]
    assert "blast" in impact
    assert impact.get("direction") == "both"
    assert impact["min_confidence"] == "probable"
    assert "escalate_hint" in impact

    callers = dispatch_capability(
        backends,
        "code_graph.callers",
        {"symbol_id": symbol["id"], "top_k": 10},
        scope=scope,
        usage_profile="programming-cursor-mcp",
        correlation_id=str(uuid4()),
    )
    assert callers.get("callers_of") == symbol["id"]
    assert callers["min_confidence"] == "probable"
    assert "callers" in callers
    assert "escalate_hint" in callers

    community = dispatch_capability(
        backends,
        "code_graph.community",
        {"symbol_id": symbol["id"], "member_limit": 20},
        scope=scope,
        usage_profile="programming-cursor-mcp",
        correlation_id=str(uuid4()),
    )
    assert "community_id" in community
    assert "escalate_hint" in community

    call_path = dispatch_capability(
        backends,
        "code_graph.call_path",
        {"symbol_id": symbol["id"], "max_depth": 3},
        scope=scope,
        usage_profile="programming-cursor-mcp",
        correlation_id=str(uuid4()),
    )
    assert "call_path_ids" in call_path
    assert "escalate_hint" in call_path

    ctx = dispatch_capability(
        backends,
        "code_graph.generation_context",
        {"symbol_id": symbol["id"]},
        scope=scope,
        usage_profile="programming-cursor-mcp",
        correlation_id=str(uuid4()),
    )
    assert "seed" in ctx or "symbols" in ctx or "seed_symbol" in ctx or ctx.get("symbol") or "expansion" in ctx

    profile = dispatch_capability(
        backends,
        "code_graph.language_profile",
        {},
        scope=scope,
        usage_profile="programming-cursor-mcp",
        correlation_id=str(uuid4()),
    )
    assert "language_profile" in profile
    backends.close()


def test_code_graph_unused_candidates_scored_contract():
    """MCP unused_candidates returns score/evidence/kpi_hints (dead-code intelligence)."""
    from uuid import uuid4

    from mcp_gateway_service.backends import PlatformBackends, dispatch_capability
    from mcp_gateway_service.store_factory import build_stores

    backends = PlatformBackends(
        build_stores({"ASTLOOM_MCP_STORE_MODE": "memory", "ASTLOOM_MCP_GRAPH_MODE": "memory"})
    )
    scope = {"tenant_id": "t", "workspace_id": "w", "project_id": "p-dead"}
    dispatch_capability(
        backends,
        "code_graph.ingest_file",
        {
            "file_path": "src/orphan.py",
            "language": "python",
            "source": "def unused_helper():\n    return 42\n\ndef also_unused():\n    return unused_helper()\n",
        },
        scope=scope,
        usage_profile="programming-cursor-mcp",
        correlation_id=str(uuid4()),
    )
    payload = dispatch_capability(
        backends,
        "code_graph.unused_candidates",
        {
            "scope_mode": "project_scan",
            "path_prefix": "src",
            "min_confidence": 0.5,
            "include_uncertain": True,
            "max_results": 50,
        },
        scope=scope,
        usage_profile="programming-cursor-mcp",
        correlation_id=str(uuid4()),
    )
    assert payload["scope_mode"] == "project_scan"
    assert payload.get("path_prefix") == "src"
    assert "kpi_hints" in payload
    assert "dead_code_candidates_surfaced" in payload["kpi_hints"]
    assert "index_coverage" in payload
    rows = list(payload.get("candidates") or []) + list(payload.get("skipped_uncertain") or [])
    assert rows
    assert all(str(r.get("path") or "").startswith("src") for r in rows)
    sample = rows[0]
    assert "score" in sample
    assert "confidence" in sample
    assert "evidence" in sample
    assert "finding_kind" in sample
    triage_payload = dispatch_capability(
        backends,
        "code_graph.unused_candidates",
        {
            "scope_mode": "project_scan",
            "include_uncertain": True,
            "triage": True,
            "max_results": 10,
        },
        scope=scope,
        usage_profile="programming-cursor-mcp",
        correlation_id=str(uuid4()),
    )
    assert triage_payload.get("triage_enabled") is True
    assert triage_payload.get("triage_note") == "triage_cannot_raise_safe_to_delete"
    assert triage_payload.get("triage_engine") == "local_rules"
    uncertain = list(triage_payload.get("skipped_uncertain") or [])
    if uncertain:
        assert "triage" in uncertain[0]
        assert uncertain[0]["triage"].get("safe_to_delete") is False
    backends.close()


def test_docs_stale_candidates_scored_contract():
    """MCP docs.stale_candidates returns score/evidence/kpi_hints (doc 78)."""
    from uuid import uuid4

    from mcp_gateway_service.backends import PlatformBackends, dispatch_capability
    from mcp_gateway_service.store_factory import build_stores

    backends = PlatformBackends(
        build_stores({"ASTLOOM_MCP_STORE_MODE": "memory", "ASTLOOM_MCP_GRAPH_MODE": "memory"})
    )
    scope = {"tenant_id": "t", "workspace_id": "w", "project_id": "p-stale-docs"}
    dispatch_capability(
        backends,
        "docs_sync.write",
        {
            "mode": "index",
            "title": "Orphan fixture",
            "body": "Body for stale orphan fixture.\n",
            "path": "docs/fixtures/stale_orphan.md",
            "doc_id": "as.doc.test.stale-orphan",
            "frontmatter": {
                "doc_id": "as.doc.test.stale-orphan",
                "title": "Orphan fixture",
                "owner": "test",
                "status": "active",
                "schema_version": "1.0",
                "linked_symbols": [],
                "decision_refs": [],
                "concern_lane": "product",
                "lifecycle_lane": "current",
                "authority": "informative",
                "updated_at": "2020-01-01",
            },
        },
        scope=scope,
        usage_profile="programming-cursor-mcp",
        correlation_id=str(uuid4()),
    )
    payload = dispatch_capability(
        backends,
        "docs.stale_candidates",
        {
            "scope_mode": "project_scan",
            "path_prefix": "docs/fixtures",
            "min_confidence": 0.5,
            "include_uncertain": True,
            "max_results": 20,
        },
        scope=scope,
        usage_profile="programming-cursor-mcp",
        correlation_id=str(uuid4()),
    )
    assert payload["scope_mode"] == "project_scan"
    assert payload.get("path_prefix") == "docs/fixtures"
    assert "kpi_hints" in payload
    assert "stale_docs_candidates_surfaced" in payload["kpi_hints"]
    assert "index_coverage" in payload
    rows = list(payload.get("candidates") or []) + list(payload.get("skipped_uncertain") or [])
    assert rows
    sample = rows[0]
    assert "score" in sample
    assert "finding_kind" in sample
    assert "evidence" in sample
    assert any(r.get("finding_kind") == "orphan_doc" for r in rows), rows
    backends.close()


def test_code_graph_ingest_repo_via_mcp(tmp_path):
    from uuid import uuid4

    from mcp_gateway_service.backends import PlatformBackends, dispatch_capability
    from mcp_gateway_service.store_factory import build_stores

    (tmp_path / "mod.py").write_text("def hello():\n    return 'hi'\n", encoding="utf-8")
    backends = PlatformBackends(
        build_stores({"ASTLOOM_MCP_STORE_MODE": "memory", "ASTLOOM_MCP_GRAPH_MODE": "memory"})
    )
    scope = {"tenant_id": "t", "workspace_id": "w", "project_id": "p-repo"}
    result = dispatch_capability(
        backends,
        "code_graph.ingest_repo",
        {"root_path": str(tmp_path), "include_outcomes": True},
        scope=scope,
        usage_profile="programming-cursor-mcp",
        correlation_id=str(uuid4()),
    )
    assert result["ingest_repo"]["files_ingested"] == 1
    assert result["ingest_repo"]["files_failed"] == 0
    assert result["ok"] is True
    got = dispatch_capability(
        backends,
        "code_graph.get_symbol",
        {"qualified_name": "hello"},
        scope=scope,
        usage_profile="programming-cursor-mcp",
        correlation_id=str(uuid4()),
    )
    assert "hello" in got["symbol"]["name"]
    backends.close()


def test_create_task_persists_in_memory_store():
    backends = PlatformBackends.from_env({"ASTLOOM_MCP_STORE_MODE": "memory"})
    scope = {"tenant_id": "t", "workspace_id": "w", "project_id": "p"}
    created = dispatch_capability(
        backends,
        "core_data.create_task",
        {"title": "Persist me", "instructions": "via MCP"},
        scope=scope,
        usage_profile="programming-cursor-mcp",
        correlation_id=str(uuid4()),
    )
    assert created["store_mode"] == "memory"
    assert created["task"]["data"]["title"] == "Persist me"
    backends.close()

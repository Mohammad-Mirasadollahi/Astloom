"""Live challenging probes for docs_drift_check vs real Neo4j DOCUMENTED_BY.

Requires ASTLOOM_* env (postgres + neo4j) matching the running Astloom stack.
Seeds the two dogfood human links when missing so the suite does not depend on
a prior full-repo ``astloom sync``.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

from mcp_gateway_service.backends import docs as docs_backend
from mcp_gateway_service.backends.platform import PlatformBackends
from mcp_gateway_service.server import McpGateway

_SEED_CODE = (
    "backend/services/code-graph-service/src/code_graph_service/domain/hybrid_doc_coverage.py",
    "backend/services/mcp-gateway-service/src/mcp_gateway_service/backends/quality.py",
)
_SEED_DOCS = (
    "docs/07-code-knowledge-graph/41-hybrid-documentation-coverage.md",
    "docs/01-core-data-model/09-automated-followup-task-lifecycle-and-retention.md",
)


def _live_env_ready() -> bool:
    return bool(
        os.environ.get("ASTLOOM_DATABASE_URL")
        and os.environ.get("ASTLOOM_NEO4J_URI")
        and os.environ.get("ASTLOOM_MCP_GRAPH_MODE", "neo4j") == "neo4j"
    )


def _seed_human_documented_by(live_scope: dict[str, str]) -> None:
    """Ingest seed symbols + Phase-2 human DOCUMENTED_BY for live drift challenges."""
    from astloom_cli.docs_link_sync import sync_human_docs
    from astloom_cli.util import repo_root
    from code_graph_service.bootstrap import Settings, build_service
    from code_graph_service.core import Scope

    root = Path(repo_root()).resolve()
    prev_provider = os.environ.get("ASTLOOM_EMBEDDING_PROVIDER")
    prev_local = os.environ.get("ASTLOOM_EMBEDDING_LOCAL_ENABLED")
    prev_docs = os.environ.get("ASTLOOM_LITELLM_DOCS_ENABLED")
    os.environ["ASTLOOM_EMBEDDING_PROVIDER"] = "stub"
    os.environ["ASTLOOM_EMBEDDING_LOCAL_ENABLED"] = "false"
    os.environ["ASTLOOM_LITELLM_DOCS_ENABLED"] = "false"
    try:
        settings = Settings(
            store_backend="neo4j",
            database_url=os.environ.get("ASTLOOM_CODE_GRAPH_DATABASE_URL")
            or os.environ.get("ASTLOOM_DATABASE_URL", ""),
            neo4j_uri=os.environ["ASTLOOM_NEO4J_URI"],
            neo4j_user=os.environ.get("ASTLOOM_NEO4J_USER", "neo4j"),
            neo4j_password=os.environ.get("ASTLOOM_NEO4J_PASSWORD", ""),
            neo4j_database=os.environ.get("ASTLOOM_NEO4J_DATABASE", "neo4j"),
        )
        service = build_service(settings)
        scope = Scope(
            live_scope["tenant_id"],
            live_scope["workspace_id"],
            live_scope["project_id"],
        )
        try:
            for rel in _SEED_CODE:
                path = root / rel
                if not path.is_file():
                    pytest.skip(f"seed source missing: {rel}")
                service.ingest_file(
                    scope,
                    "live-drift-seed",
                    f"corr-seed-{Path(rel).name}",
                    f"idem-seed-{rel}",
                    {
                        "file_path": rel,
                        "source": path.read_text(encoding="utf-8"),
                        "language": "python",
                    },
                )
            result = sync_human_docs(
                graph_service=service,
                graph_scope=scope,
                root_path=root,
                filters={
                    "docs_enabled": True,
                    "doc_match_globs": list(_SEED_DOCS),
                    "doc_exclude_dirs": [],
                    "doc_exclude_globs": [],
                },
                actor="live-drift-seed",
                correlation_id=f"live-drift-seed-{uuid.uuid4().hex[:8]}",
                refresh_unchanged_links=True,
            )
            if int(getattr(result, "links_created", 0) or 0) < 1 and int(
                getattr(result, "docs_indexed", 0) or 0
            ) < 1:
                pytest.skip(f"could not seed human doc links: {result.to_dict()}")
        finally:
            service.store.close()
    finally:
        if prev_provider is None:
            os.environ.pop("ASTLOOM_EMBEDDING_PROVIDER", None)
        else:
            os.environ["ASTLOOM_EMBEDDING_PROVIDER"] = prev_provider
        if prev_local is None:
            os.environ.pop("ASTLOOM_EMBEDDING_LOCAL_ENABLED", None)
        else:
            os.environ["ASTLOOM_EMBEDDING_LOCAL_ENABLED"] = prev_local
        if prev_docs is None:
            os.environ.pop("ASTLOOM_LITELLM_DOCS_ENABLED", None)
        else:
            os.environ["ASTLOOM_LITELLM_DOCS_ENABLED"] = prev_docs


@pytest.fixture(scope="module")
def live_backends() -> PlatformBackends:
    if not _live_env_ready():
        pytest.skip("live Astloom postgres/neo4j env not configured")
    env = {
        **os.environ,
        "ASTLOOM_MCP_STORE_MODE": os.environ.get("ASTLOOM_MCP_STORE_MODE", "postgres"),
        "ASTLOOM_MCP_GRAPH_MODE": "neo4j",
        "ASTLOOM_MCP_GRAPH_SEED": "false",
    }
    backends = PlatformBackends.from_env(env)
    yield backends
    backends.close()


@pytest.fixture(scope="module")
def live_scope() -> dict[str, str]:
    return {
        "tenant_id": os.environ.get("ASTLOOM_TENANT_ID", "mir"),
        "workspace_id": os.environ.get("ASTLOOM_WORKSPACE_ID", "dev"),
        "project_id": os.environ.get("ASTLOOM_PROJECT_ID", "astloom"),
    }


@pytest.fixture(scope="module", autouse=True)
def _ensure_live_human_doc_links(live_backends: PlatformBackends, live_scope: dict[str, str]) -> None:
    """Guarantee Phase-2 human links exist before drift challenges run."""
    del live_backends  # backends must be up; seeding uses its own graph service
    _seed_human_documented_by(live_scope)


@pytest.mark.live
def test_live_drift_human_linked_short_name_no_false_missing(
    live_backends: PlatformBackends,
    live_scope: dict[str, str],
) -> None:
    """Challenge 1: short name + wrong file_path must not invent missing_doc."""
    result = docs_backend.docs_drift_check(
        live_backends,
        {
            "symbol": "build_symbol_doc_coverage",
            "file_path": "this/path/does/not/exist.py",
        },
        scope=live_scope,
        correlation_id=f"live-drift-human-{uuid.uuid4().hex[:8]}",
        base={"backend": "in_process"},
    )
    assert result["drift"] is False, result
    assert result["findings"] == []
    assert result["lookup_source"] == "graph"
    assert any(str(x.get("target_id", "")).startswith("doc:human:") for x in result["documented_by"])


@pytest.mark.live
def test_live_drift_quality_audit_human_link(
    live_backends: PlatformBackends,
    live_scope: dict[str, str],
) -> None:
    """Challenge 2: second real linked symbol from follow-up Task doc."""
    result = docs_backend.docs_drift_check(
        live_backends,
        {
            "symbol": "quality_audit",
            "file_path": "backend/services/mcp-gateway-service/src/mcp_gateway_service/backends/quality.py",
        },
        scope=live_scope,
        correlation_id=f"live-drift-qa-{uuid.uuid4().hex[:8]}",
        base={"backend": "in_process"},
    )
    assert result["drift"] is False, result
    assert result["lookup_source"] == "graph"
    targets = {str(x.get("target_id") or "") for x in result["documented_by"]}
    assert any("followup-task-lifecycle" in t or "automated-followup" in t or t.startswith("doc:human:") for t in targets)


@pytest.mark.live
def test_live_drift_idempotent_no_orphan_spam(
    live_backends: PlatformBackends,
    live_scope: dict[str, str],
) -> None:
    """Challenge 3: two calls must stay clean and not grow docs-sync orphans."""
    docs_scope = live_backends.docs_scope(live_scope)
    before = len(live_backends.docs.store.list_symbols(docs_scope))
    for i in range(2):
        result = docs_backend.docs_drift_check(
            live_backends,
            {"symbol": "build_symbol_doc_coverage", "file_path": f"junk/{i}.py"},
            scope=live_scope,
            correlation_id=f"live-drift-idem-{i}-{uuid.uuid4().hex[:8]}",
            base={"backend": "in_process"},
        )
        assert result["drift"] is False
        assert result["lookup_source"] == "graph"
    after = len(live_backends.docs.store.list_symbols(docs_scope))
    assert after == before


@pytest.mark.live
def test_live_drift_unknown_symbol_still_reports_missing(
    live_backends: PlatformBackends,
    live_scope: dict[str, str],
) -> None:
    """Challenge 4: truly unknown symbol still takes docs-sync path → missing_doc."""
    unique = f"never_linked_symbol_{uuid.uuid4().hex[:10]}"
    isolated_scope = {
        **live_scope,
        "project_id": f"{live_scope['project_id']}-drift-{uuid.uuid4().hex[:8]}",
    }
    main_docs_scope = live_backends.docs_scope(live_scope)
    main_symbol_count = len(live_backends.docs.store.list_symbols(main_docs_scope))
    result = docs_backend.docs_drift_check(
        live_backends,
        {"symbol": unique, "file_path": f"src/{unique}.py"},
        scope=isolated_scope,
        correlation_id=f"live-drift-missing-{uuid.uuid4().hex[:8]}",
        base={"backend": "in_process"},
    )
    assert result["drift"] is True
    assert result["findings"]
    assert result.get("lookup_source") == "docs_sync"
    assert result["findings"][0]["drift_type"] == "missing_doc"
    assert len(live_backends.docs.store.list_symbols(main_docs_scope)) == main_symbol_count


@pytest.mark.live
def test_live_mcp_gateway_tool_surface_drift_and_generation(
    live_backends: PlatformBackends,
    live_scope: dict[str, str],
) -> None:
    """Challenge 5: full MCP tool path — drift + generation_context agree on human layer."""
    gw = McpGateway(
        profile_id=os.environ.get("ASTLOOM_USAGE_PROFILE", "programming-cursor-mcp"),
        tenant_id=live_scope["tenant_id"],
        workspace_id=live_scope["workspace_id"],
        project_id=live_scope["project_id"],
        backends=live_backends,
    )
    drift = gw.call_tool(
        "astloom_docs_drift_check",
        {
            "symbol": "build_symbol_doc_coverage",
            "file_path": "backend/services/code-graph-service/src/code_graph_service/domain/hybrid_doc_coverage.py",
        },
    )
    payload = drift["structuredContent"]
    assert payload["drift"] is False, payload
    assert payload["lookup_source"] == "graph"

    ctx = gw.call_tool(
        "astloom_code_graph_generation_context",
        {
            "qualified_name": (
                "backend.services.code-graph-service.src.code_graph_service."
                "domain.hybrid_doc_coverage.build_symbol_doc_coverage"
            )
        },
    )
    hybrid = ctx["structuredContent"]["hybrid_documentation"]
    assert hybrid["preferred_layer"] == "human"
    assert hybrid["coverage"]["human"] is True

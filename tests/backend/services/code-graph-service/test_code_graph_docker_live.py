"""Live Docker integration tests for code-graph stores (non-default ports)."""

from __future__ import annotations

import os
import uuid

import pytest

from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.neo4j_store import Neo4jStore
from code_graph_service.postgres_store import PostgresStore

# Port profile: backend/configs/port-profiles/astloom-dev.json
POSTGRES_PORT = int(os.environ.get("ASTLOOM_POSTGRES_PORT", "32232"))
NEO4J_BOLT_PORT = int(os.environ.get("ASTLOOM_NEO4J_BOLT_PORT", "32287"))
POSTGRES_PASSWORD = os.environ.get("ASTLOOM_POSTGRES_PASSWORD", "astloom-local-dev-secret")
NEO4J_PASSWORD = os.environ.get("ASTLOOM_NEO4J_PASSWORD", "astloom-local-dev-secret")
NEO4J_USER = os.environ.get("ASTLOOM_NEO4J_USER", "neo4j")

PYTHON_SOURCE = """\
def check_password(password):
    return len(password) > 8

def login(user, password):
    return check_password(password)
"""


def _require_tcp(host: str, port: int) -> None:
    import socket

    sock = socket.socket()
    sock.settimeout(2)
    try:
        sock.connect((host, port))
    except OSError as exc:
        pytest.skip(f"service not reachable at {host}:{port}: {exc}")
    finally:
        sock.close()


def _assert_non_default_ports() -> None:
    forbidden = {5432, 7474, 7687}
    assert POSTGRES_PORT not in forbidden, "Postgres host port must not be default 5432"
    assert NEO4J_BOLT_PORT not in forbidden, "Neo4j Bolt host port must not be default 7687"


def test_docker_ports_follow_port_profile():
    _assert_non_default_ports()
    _require_tcp("127.0.0.1", POSTGRES_PORT)
    _require_tcp("127.0.0.1", NEO4J_BOLT_PORT)


def test_postgres_store_python_ingest_live():
    _assert_non_default_ports()
    _require_tcp("127.0.0.1", POSTGRES_PORT)
    url = (
        f"postgresql://astloom:{POSTGRES_PASSWORD}@127.0.0.1:{POSTGRES_PORT}/astloom"
    )
    store = PostgresStore(url)
    try:
        scope = Scope("tenant-live", "ws-live", f"proj-{uuid.uuid4().hex[:8]}")
        service = CodeGraphService(store)
        result = service.ingest_file(
            scope,
            "agent",
            "corr-pg",
            f"idem-pg-{uuid.uuid4().hex}",
            {"file_path": "src/auth.py", "source": PYTHON_SOURCE, "language": "python"},
        )
        assert result.symbols_indexed >= 3
        login_id = f"sym:{scope.project_id}:src.auth.login"
        neighbors = service.structural_query(scope, login_id, "CALLS")
        assert any(edge["rel_type"] == "CALLS" for edge in neighbors["edges"])
        assert store.outbox()[-1]["event_type"] in {"FileIngested", "SymbolsDocumented"}
    finally:
        store.close()


def test_neo4j_store_python_ingest_live():
    _assert_non_default_ports()
    _require_tcp("127.0.0.1", NEO4J_BOLT_PORT)
    store = Neo4jStore(
        uri=f"bolt://127.0.0.1:{NEO4J_BOLT_PORT}",
        user=NEO4J_USER,
        password=NEO4J_PASSWORD,
        ensure_schema=True,
    )
    try:
        scope = Scope("tenant-live", "ws-live", f"proj-{uuid.uuid4().hex[:8]}")
        service = CodeGraphService(store)
        result = service.ingest_file(
            scope,
            "agent",
            "corr-nj",
            f"idem-nj-{uuid.uuid4().hex}",
            {"file_path": "src/auth.py", "source": PYTHON_SOURCE, "language": "python"},
        )
        assert result.symbols_indexed >= 3
        login_id = f"sym:{scope.project_id}:src.auth.login"
        neighbors = service.structural_query(scope, login_id, "CALLS")
        assert any(edge["rel_type"] == "CALLS" for edge in neighbors["edges"])
        events = store.outbox()
        assert any(event["event_type"] == "FileIngested" for event in events)

        check_id = f"sym:{scope.project_id}:src.auth.check_password"
        callers = service.callers(scope, check_id, top_k=10)
        assert any(c.get("name") == "login" for c in callers.get("callers") or [])
        assert "escalate_hint" in callers
        impact = service.impact_analysis(scope, check_id, direction="upstream", max_depth=2)
        assert impact.get("direction") == "upstream"
        assert "blast" in impact
        community = service.community_of_symbol(scope, check_id, member_limit=20)
        assert "community_id" in community
    finally:
        store.close()


@pytest.mark.live
def test_neo4j_hybrid_callers_impact_live():
    """Release-gate: directed impact + callers on Neo4j (Codebase-Memory hybrid)."""
    _assert_non_default_ports()
    _require_tcp("127.0.0.1", NEO4J_BOLT_PORT)
    store = Neo4jStore(
        uri=f"bolt://127.0.0.1:{NEO4J_BOLT_PORT}",
        user=NEO4J_USER,
        password=NEO4J_PASSWORD,
        ensure_schema=True,
    )
    try:
        scope = Scope("tenant-live", "ws-live", f"proj-hyb-{uuid.uuid4().hex[:8]}")
        service = CodeGraphService(store)
        service.ingest_file(
            scope,
            "agent",
            "corr-hyb",
            f"idem-hyb-{uuid.uuid4().hex}",
            {"file_path": "src/auth.py", "source": PYTHON_SOURCE, "language": "python"},
        )
        check_id = f"sym:{scope.project_id}:src.auth.check_password"
        callers = service.callers(scope, check_id, top_k=10)
        assert any(c.get("name") == "login" for c in callers.get("callers") or [])
        impact = service.impact_analysis(scope, check_id, direction="both", max_depth=3)
        assert "blast" in impact and "escalate_hint" in impact
        community = service.community_of_symbol(scope, check_id)
        assert "community_id" in community
        login_id = f"sym:{scope.project_id}:src.auth.login"
        path_pack = service.call_path_pack(scope, login_id, max_depth=3)
        assert path_pack.get("call_path_ids")
        # HTTP_CALLS / ASYNC_CALLS live fixture
        routes = (
            "from fastapi import FastAPI\napp = FastAPI()\n\n"
            '@app.get("/api/v1/users")\ndef list_users():\n    return []\n'
        )
        client_src = (
            "import httpx\n\ndef fetch_users():\n    return httpx.get(\"/api/v1/users\")\n"
        )
        service.ingest_file(
            scope,
            "agent",
            "corr-http",
            f"idem-http-{uuid.uuid4().hex}",
            {"file_path": "api_routes.py", "source": routes, "language": "python"},
        )
        service.ingest_file(
            scope,
            "agent",
            "corr-http2",
            f"idem-http2-{uuid.uuid4().hex}",
            {"file_path": "api_client.py", "source": client_src, "language": "python"},
        )
        async_edges = [
            e for e in store.list_edges(scope) if e.rel_type in {"HTTP_CALLS", "ASYNC_CALLS"}
        ]
        assert async_edges
    finally:
        store.close()

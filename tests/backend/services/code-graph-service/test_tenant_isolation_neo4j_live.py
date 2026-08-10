"""Neo4j-backed tenant isolation (GAP-005 production path).

Skips when Compose Neo4j is down; never treats skip as pass.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from code_graph_service.core import CodeGraphService, NotFoundError, Scope
from code_graph_service.neo4j_store import Neo4jStore

from live_helpers import NEO4J_BOLT_PORT, NEO4J_PASSWORD, NEO4J_USER, require_tcp, skip_on_live_connect_error

pytestmark = pytest.mark.live

SRC = "def tenant_secret_fn():\n    return 1\n"


def _neo4j_store() -> Neo4jStore:
    require_tcp("127.0.0.1", NEO4J_BOLT_PORT)
    try:
        return Neo4jStore(
            uri=f"bolt://127.0.0.1:{NEO4J_BOLT_PORT}",
            user=NEO4J_USER,
            password=NEO4J_PASSWORD,
            ensure_schema=True,
            gds_enabled=False,
        )
    except Exception as exc:  # noqa: BLE001
        skip_on_live_connect_error(exc)
        raise


def test_neo4j_symbols_isolated_across_tenants():
    store = _neo4j_store()
    try:
        svc = CodeGraphService(store)
        a = Scope(f"iso-a-{uuid4().hex[:8]}", "w", "p")
        b = Scope(f"iso-b-{uuid4().hex[:8]}", "w", "p")
        svc.ingest_file(
            a,
            "agent",
            str(uuid4()),
            f"iso-{uuid4()}",
            {"file_path": "src/secret.py", "source": SRC, "language": "python"},
        )
        assert store.list_symbols(a)
        assert store.list_symbols(b) == []
        hybrid_b = svc.hybrid_search(b, "tenant_secret_fn")
        leaked = [
            h
            for h in hybrid_b.get("hits") or []
            if "tenant_secret_fn" in str(h.get("qualified_name") or "")
        ]
        assert leaked == []
        sid = store.list_symbols(a)[0].id
        with pytest.raises(NotFoundError):
            store.get_symbol(sid, b)
    finally:
        store.close()

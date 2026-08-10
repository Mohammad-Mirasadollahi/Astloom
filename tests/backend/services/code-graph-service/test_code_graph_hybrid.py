"""Unit tests for embedding index, outbox mirror, and hybrid retrieval wiring."""

from __future__ import annotations

import os
import uuid

import pytest

from code_graph_service.core import CodeGraphService, LocalEmbeddingStub, Scope
from code_graph_service.outbox_mirror_store import OutboxMirrorStore
from code_graph_service.postgres_side import InMemoryEmbeddingIndex, PostgresEmbeddingIndex, PostgresOutboxMirror
from code_graph_service.testing import InMemoryStore

PYTHON_SOURCE = """\
def check_password(password):
    return len(password) > 8

def login(user, password):
    return check_password(password)
"""

POSTGRES_PORT = int(os.environ.get("ASTLOOM_POSTGRES_PORT", "32232"))
POSTGRES_PASSWORD = os.environ.get("ASTLOOM_POSTGRES_PASSWORD", "astloom-local-dev-secret")
NEO4J_BOLT_PORT = int(os.environ.get("ASTLOOM_NEO4J_BOLT_PORT", "32287"))
NEO4J_PASSWORD = os.environ.get("ASTLOOM_NEO4J_PASSWORD", "astloom-local-dev-secret")
NEO4J_USER = os.environ.get("ASTLOOM_NEO4J_USER", "neo4j")


def test_inmemory_embedding_index_semantic_search():
    store = InMemoryStore()
    index = InMemoryEmbeddingIndex()
    service = CodeGraphService(store, embedding_index=index)
    scope = Scope("t", "w", "emb-mem")
    service.ingest_file(
        scope,
        "agent",
        "c",
        "idem-emb",
        {"file_path": "src/auth.py", "source": PYTHON_SOURCE, "language": "python"},
    )
    hits = service.semantic_search(scope, "login password check")
    assert hits
    assert hits[0]["score"] > 0
    assert hits[0]["retrieval"] == "pgvector"
    assert "graph_neighbors" in hits[0]
    names = {hit["symbol"]["qualified_name"] for hit in hits}
    assert any("login" in name or "check_password" in name for name in names)
    # FILE symbols must not pollute ANN index.
    assert all(hit["symbol"]["kind"] != "file" for hit in hits)


def test_embedding_index_skips_file_kind_and_deletes_stale():
    index = InMemoryEmbeddingIndex()
    scope = Scope("t", "w", "stale")
    index.upsert(scope, "file:x", [0.1] * 16, model="local-hash-v1", kind="file")
    index.upsert(scope, "sym:fn", [0.2] * 16, model="local-hash-v1", kind="function")
    hits = index.search(scope, [0.2] * 16, top_k=5)
    assert [sid for sid, _ in hits] == ["sym:fn"]
    index.delete(scope, "sym:fn")
    assert index.search(scope, [0.2] * 16, top_k=5) == []


def test_hybrid_search_flags_missing_embedding_index():
    store = InMemoryStore()
    service = CodeGraphService(
        store,
        embeddings=LocalEmbeddingStub(dims=16),
        embedding_index=None,
    )
    scope = Scope("t", "w", "hyb-no-idx")
    service.ingest_file(
        scope,
        "agent",
        "c",
        "idem-hyb",
        {"file_path": "src/auth.py", "source": PYTHON_SOURCE, "language": "python"},
    )
    # Neo4j-backed MCP often has no per-symbol vectors when pgvector is unwired;
    # simulate empty semantic channel with an embedder still present.
    service.semantic_search = lambda *_a, **_k: []  # type: ignore[method-assign]
    payload = service.hybrid_search(scope, "login password")
    assert payload["channels"]["bm25"] >= 1
    assert payload["channels"]["semantic"] == 0
    assert "embedding_index_unavailable" in str(payload.get("semantic_error") or "")


def test_hybrid_search_retries_semantic_after_admin_shutdown():
    store = InMemoryStore()
    index = InMemoryEmbeddingIndex()
    service = CodeGraphService(
        store,
        embeddings=LocalEmbeddingStub(dims=16),
        embedding_index=index,
    )
    scope = Scope("t", "w", "hyb-retry")
    service.ingest_file(
        scope,
        "agent",
        "c",
        "idem-hyb-retry",
        {"file_path": "src/auth.py", "source": PYTHON_SOURCE, "language": "python"},
    )
    calls = {"n": 0}
    resets = {"n": 0}
    real_semantic = service.semantic_search
    real_reset = service.reset_database_connections

    def flaky_semantic(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            class AdminShutdown(Exception):
                pass

            raise AdminShutdown("terminating connection due to administrator command")
        return real_semantic(*args, **kwargs)

    def counting_reset() -> None:
        resets["n"] += 1
        real_reset()

    service.semantic_search = flaky_semantic  # type: ignore[method-assign]
    service.reset_database_connections = counting_reset  # type: ignore[method-assign]
    payload = service.hybrid_search(scope, "login password")
    assert calls["n"] == 2
    assert resets["n"] == 1
    assert payload["channels"]["semantic"] >= 1
    assert not payload.get("semantic_error")


def test_generation_context_includes_expansion_field():
    store = InMemoryStore()
    service = CodeGraphService(store)
    scope = Scope("t", "w", "gen-exp")
    service.ingest_file(
        scope,
        "agent",
        "c",
        "idem-gen",
        {"file_path": "src/auth.py", "source": PYTHON_SOURCE, "language": "python"},
    )
    login_id = f"sym:{scope.project_id}:src.auth.login"
    ctx = service.build_generation_context(scope, login_id)
    assert ctx["expansion"] == "one_hop"
    assert ctx["uses_full_repository"] is False
    assert ctx["symbol_count"] >= 1


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


def test_postgres_embedding_index_live():
    _require_tcp("127.0.0.1", POSTGRES_PORT)
    url = f"postgresql://astloom:{POSTGRES_PASSWORD}@127.0.0.1:{POSTGRES_PORT}/astloom"
    index = PostgresEmbeddingIndex(url, dims=1024, ensure_schema=True)
    scope = Scope("tenant-emb", "ws-emb", f"proj-{uuid.uuid4().hex[:8]}")
    try:
        store = InMemoryStore()
        service = CodeGraphService(
            store,
            embeddings=LocalEmbeddingStub(dims=1024),
            embedding_index=index,
        )
        service.ingest_file(
            scope,
            "agent",
            "c",
            f"idem-{scope.project_id}",
            {"file_path": "src/auth.py", "source": PYTHON_SOURCE, "language": "python"},
        )
        hits = service.semantic_search(scope, "authenticate login")
        assert hits
        assert hits[0]["score"] > 0
        assert hits[0]["retrieval"] == "pgvector"
        assert all(hit["symbol"]["kind"] != "file" for hit in hits)
    finally:
        index.wipe_scope(scope)
        index.close()


def test_postgres_embedding_dimension_mismatch_preserves_existing_rows():
    _require_tcp("127.0.0.1", POSTGRES_PORT)
    url = f"postgresql://astloom:{POSTGRES_PASSWORD}@127.0.0.1:{POSTGRES_PORT}/astloom"
    canonical = PostgresEmbeddingIndex(url, dims=1024, ensure_schema=True)
    scope = Scope("tenant-emb", "ws-emb", f"guard-{uuid.uuid4().hex[:8]}")
    try:
        canonical.upsert(
            scope,
            "sentinel",
            [0.01] * 1024,
            model="dimension-guard",
            kind="function",
        )
        with pytest.raises(RuntimeError, match="dimension mismatch"):
            PostgresEmbeddingIndex(url, dims=16, ensure_schema=True)
        assert canonical.list_symbol_models(scope) == {"sentinel": "dimension-guard"}
    finally:
        canonical.wipe_scope(scope)
        canonical.close()


def test_hybrid_pgvector_and_inmemory_graph_neighbors():
    """Stage-1 hybrid: pgvector-filtered hits + graph_neighbors from structural store."""
    store = InMemoryStore()
    index = InMemoryEmbeddingIndex()
    service = CodeGraphService(store, embedding_index=index)
    scope = Scope("t", "w", "hybrid-neigh")
    service.ingest_file(
        scope,
        "agent",
        "c",
        "idem-hybrid",
        {"file_path": "src/auth.py", "source": PYTHON_SOURCE, "language": "python"},
    )
    hits = service.semantic_search(scope, "login", top_k=3, expand_seeds=2, expand_depth=1)
    assert hits
    assert any(hit.get("graph_neighbors") for hit in hits[:2])
    assert any(hit.get("graph_expansion") for hit in hits[:2])


def test_stage2_vector_index_allowlist_path():
    """Injected VectorIndexPort Stage-2 sets retrieval=turbovec after Stage-1 candidates."""
    from vector_index import InMemoryEntityIdMap, InMemoryVectorIndex

    store = InMemoryStore()
    emb_index = InMemoryEmbeddingIndex()
    vector_index = InMemoryVectorIndex(dim=16)
    entity_id_map = InMemoryEntityIdMap()
    service = CodeGraphService(
        store,
        embedding_index=emb_index,
        vector_index=vector_index,
        entity_id_map=entity_id_map,
    )
    scope = Scope("t", "w", "ann-stage2")
    service.ingest_file(
        scope,
        "agent",
        "c",
        "idem-ann",
        {"file_path": "src/auth.py", "source": PYTHON_SOURCE, "language": "python"},
    )
    hits = service.semantic_search(scope, "login password check", top_k=3)
    assert hits
    assert hits[0]["retrieval"] == "turbovec"
    assert hits[0]["score"] > 0


def test_neo4j_outbox_mirrors_to_postgres_live():
    _require_tcp("127.0.0.1", POSTGRES_PORT)
    _require_tcp("127.0.0.1", NEO4J_BOLT_PORT)
    from code_graph_service.neo4j_store import Neo4jStore

    url = f"postgresql://astloom:{POSTGRES_PASSWORD}@127.0.0.1:{POSTGRES_PORT}/astloom"
    nj = Neo4jStore(
        uri=f"bolt://127.0.0.1:{NEO4J_BOLT_PORT}",
        user=NEO4J_USER,
        password=NEO4J_PASSWORD,
        ensure_schema=True,
    )
    mirror = PostgresOutboxMirror(url)
    store = OutboxMirrorStore(nj, mirror)
    try:
        service = CodeGraphService(store)
        scope = Scope("tenant-obx", "ws-obx", f"proj-{uuid.uuid4().hex[:8]}")
        service.ingest_file(
            scope,
            "agent",
            "c",
            f"idem-obx-{scope.project_id}",
            {"file_path": "src/auth.py", "source": PYTHON_SOURCE, "language": "python"},
        )
        neo_events = [e for e in nj.outbox() if e.get("project_id") == scope.project_id]
        assert neo_events
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT event_id, event_type, published_at
                    FROM code_graph.outbox
                    WHERE payload->>'project_id' = %s
                    ORDER BY created_at
                    """,
                    (scope.project_id,),
                )
                rows = cur.fetchall()
        assert rows
        assert any(row["event_type"] in {"FileIngested", "SymbolsDocumented"} for row in rows)
        assert all(row["published_at"] is None for row in rows)
    finally:
        store.close()

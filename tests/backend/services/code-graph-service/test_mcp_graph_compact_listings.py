"""MCP/query paths must not dump full Neo4j symbol bodies."""

from __future__ import annotations

from uuid import uuid4

from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.testing import InMemoryStore


SCOPE = Scope("t", "w", "p")


def test_hybrid_search_uses_compact_index_not_full_bodies():
    store = InMemoryStore()
    service = CodeGraphService(store)
    service.ingest_file(
        SCOPE,
        "agent",
        str(uuid4()),
        "one",
        {
            "file_path": "src/auth.py",
            "language": "python",
            "source": "def hash_password(value: str) -> str:\n    return value\n",
        },
    )
    frozen = store.list_symbols_index(SCOPE)

    def _boom(_scope):
        raise AssertionError("full list_symbols must not run on MCP query paths")

    store.list_symbols = _boom  # type: ignore[method-assign]
    store.list_symbols_index = lambda _scope: frozen  # type: ignore[method-assign]
    store.list_symbols_lean = lambda _scope: frozen  # type: ignore[method-assign]
    payload = service.hybrid_search(SCOPE, "hash_password", top_k=3)
    assert payload["hits"]
    assert payload["hits"][0]["qualified_name"].endswith("hash_password")


def test_semantic_search_falls_back_to_lexical_when_embed_fails():
    store = InMemoryStore()
    service = CodeGraphService(store)
    service.ingest_file(
        SCOPE,
        "agent",
        str(uuid4()),
        "one",
        {
            "file_path": "src/auth.py",
            "language": "python",
            "source": "def validate_password_against_policy(value: str) -> bool:\n    return True\n",
        },
    )

    class _Boom:
        def embed(self, text, *, is_query=False):
            raise RuntimeError("LiteLLM embedding batch failed: name resolution")

    service.embeddings = _Boom()
    hits = service.semantic_search(SCOPE, "validate_password_against_policy", top_k=3)
    assert hits
    assert hits[0]["retrieval"] == "lexical_fallback"
    assert "semantic_error" in hits[0]


def test_hybrid_search_skips_catalog_dump_when_fulltext_hits():
    store = InMemoryStore()
    service = CodeGraphService(store)
    ingested = service.ingest_file(
        SCOPE,
        "agent",
        str(uuid4()),
        "one",
        {
            "file_path": "src/auth.py",
            "language": "python",
            "source": "def hash_password(value: str) -> str:\n    return value\n",
        },
    )
    sid = ingested.changed_symbol_ids[0]

    def _boom_index(_scope):
        raise AssertionError("compact catalog must not load when fulltext hits")

    store.list_symbols_index = _boom_index  # type: ignore[method-assign]
    store.list_symbols_lean = _boom_index  # type: ignore[method-assign]
    store.fulltext_search = lambda _scope, _q, **_k: [  # type: ignore[method-assign]
        {"symbol_id": sid, "score": 1.0, "method": "test.fulltext"}
    ]
    payload = service.hybrid_search(SCOPE, "hash_password", top_k=3)
    assert payload["hits"]
    assert payload["hits"][0]["symbol_id"] == sid


def test_explore_and_callers_use_neighborhood_not_full_edge_scan():
    store = InMemoryStore()
    service = CodeGraphService(store)
    ingested = service.ingest_file(
        SCOPE,
        "agent",
        str(uuid4()),
        "one",
        {
            "file_path": "src/auth.py",
            "language": "python",
            "source": (
                "def hash_password(value: str) -> str:\n"
                "    return value\n"
                "def login(password: str) -> str:\n"
                "    return hash_password(password)\n"
            ),
        },
    )
    frozen_edges = list(store.list_edges(SCOPE))
    seed = ingested.changed_symbol_ids[0]

    def _boom_edges(_scope, * _a, **_k):
        raise AssertionError("full list_edges must not run when neighborhood_edges exists")

    def _neighborhood(scope, seed_id, **_kwargs):
        _ = scope
        return [e for e in frozen_edges if e.source_id == seed_id or e.target_id == seed_id]

    store.list_edges = _boom_edges  # type: ignore[method-assign]
    store.neighborhood_edges = _neighborhood  # type: ignore[method-assign]
    pack = service.explore(SCOPE, "hash_password", top_k=3, max_depth=1)
    assert pack.get("seed_ids") or pack.get("sections")
    callers = service.callers(SCOPE, seed, max_depth=1, top_k=5)
    assert callers.get("symbol")
    store.neighborhood_edges = lambda *_a, **_k: []  # type: ignore[method-assign]
    empty = service.callers(SCOPE, seed, max_depth=1, top_k=5)
    assert empty.get("symbol")
    impact = service.impact_analysis(SCOPE, seed, max_depth=1, top_k=5)
    assert impact.get("symbol")
    community = service.community_of_symbol(SCOPE, seed, member_limit=10)
    assert community.get("symbol")
    path_pack = service.call_path_pack(SCOPE, seed, max_depth=2)
    assert path_pack.get("symbol") or path_pack.get("path") or "path_ids" in path_pack
    unused = service.unused_candidates(SCOPE, scope_mode="task_neighborhood")
    assert unused.get("candidates") == [] or unused.get("note") == "no_anchor_symbols_or_paths"


def test_unused_candidates_without_anchors_skips_catalog_dump():
    store = InMemoryStore()
    service = CodeGraphService(store)

    def _boom(_scope):
        raise AssertionError("unused_candidates must not dump the catalog without anchors")

    store.list_symbols_index = _boom  # type: ignore[method-assign]
    store.list_symbols_lean = _boom  # type: ignore[method-assign]
    store.list_symbols = _boom  # type: ignore[method-assign]
    store.list_edges = _boom  # type: ignore[method-assign]
    payload = service.unused_candidates(SCOPE, scope_mode="task_neighborhood")
    assert payload["candidates"] == []
    assert payload.get("note") == "no_anchor_symbols_or_paths"


def test_polyglot_profile_uses_language_counts_not_catalog_dump():
    store = InMemoryStore()
    service = CodeGraphService(store)

    def _boom(_scope):
        raise AssertionError("polyglot must not dump symbols/edges when language_counts exists")

    store.list_symbols_index = _boom  # type: ignore[method-assign]
    store.list_symbols_lean = _boom  # type: ignore[method-assign]
    store.list_symbols = _boom  # type: ignore[method-assign]
    store.list_edges = _boom  # type: ignore[method-assign]
    store.language_counts = lambda _scope: {  # type: ignore[method-assign]
        "file_counts": {"python": 4},
        "symbol_counts": {"python": 12},
    }
    profile = service.get_polyglot_profile(SCOPE)
    assert profile.file_counts_by_language["python"] == 4
    assert profile.symbol_counts_by_language["python"] == 12


def test_architecture_overview_skips_catalog_dump_on_neo4j_scale_path():
    store = InMemoryStore()
    service = CodeGraphService(store)

    def _boom(_scope, *_a, **_k):
        raise AssertionError("architecture_overview must not dump the catalog on Neo4j")

    store.list_symbols_index = _boom  # type: ignore[method-assign]
    store.list_symbols_lean = _boom  # type: ignore[method-assign]
    store.list_symbols = _boom  # type: ignore[method-assign]
    store.list_edges = _boom  # type: ignore[method-assign]
    store.neighborhood_edges = lambda *_a, **_k: []  # type: ignore[method-assign]
    store.rank_symbols_by_degree = lambda *_a, **_k: []  # type: ignore[method-assign]
    overview = service.architecture_overview(SCOPE, top_n=5)
    assert overview.get("hubs") == [] or overview.get("communities") == [] or "algorithm" in overview


def test_generation_context_skips_catalog_dump_when_neighborhood_exists():
    store = InMemoryStore()
    service = CodeGraphService(store)
    ingested = service.ingest_file(
        SCOPE,
        "agent",
        str(uuid4()),
        "one",
        {
            "file_path": "src/auth.py",
            "language": "python",
            "source": (
                "def hash_password(value: str) -> str:\n"
                "    return value\n"
                "def login(password: str) -> str:\n"
                "    return hash_password(password)\n"
            ),
        },
    )
    frozen_edges = list(store.list_edges(SCOPE))
    seed = ingested.changed_symbol_ids[0]

    def _boom(_scope, *_a, **_k):
        raise AssertionError("generation_context must not dump list_edges on Neo4j")

    def _neighborhood(scope, seed_id, **_kwargs):
        _ = scope
        return [e for e in frozen_edges if e.source_id == seed_id or e.target_id == seed_id]

    store.list_edges = _boom  # type: ignore[method-assign]
    store.neighborhood_edges = _neighborhood  # type: ignore[method-assign]
    store.language_counts = lambda _scope: {  # type: ignore[method-assign]
        "file_counts": {"python": 1},
        "symbol_counts": {"python": 2},
    }
    ctx = service.build_generation_context(SCOPE, seed, max_symbols=8)
    assert ctx.get("seed_symbol_id") == seed
    assert ctx.get("expansion") == "cypher_neighborhood"

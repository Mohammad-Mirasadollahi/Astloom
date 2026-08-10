"""Fuzzer suite (50 cases) for production retrieval — unit + live.

Mix of simple and adversarial inputs: empty/unicode/Lucene-special queries,
oversized corpora, disconnected graphs, GDS env clamps, hybrid/explore
validation, and live Neo4j/Postgres noise.

Save: tests/backend/services/code-graph-service/test_production_retrieval_fuzzer.py
Re-run:
  ASTLOOM_NEO4J_PASSWORD=… ASTLOOM_POSTGRES_PASSWORD=… \\
    PYTHONPATH=backend/services/code-graph-service/src \\
    .venv/bin/python -m pytest \\
    tests/backend/services/code-graph-service/test_production_retrieval_fuzzer.py -v
"""

from __future__ import annotations

import os
import random
import string
import uuid

import pytest

from code_graph_service.bootstrap import _gds_concurrency
from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.domain.communities import detect_communities, last_community_algorithm
from code_graph_service.domain.embeddings import LocalEmbeddingStub
from code_graph_service.domain.errors import ValidationError
from code_graph_service.domain.hybrid_search import (
    coalesce_rank_lists,
    lexical_rank,
    lexical_rank_scored,
    rrf_merge,
    searchable_text,
    tokenize,
)
from code_graph_service.llm_wiring import HybridEmbeddings
from code_graph_service.neo4j_store import Neo4jStore, _lucene_query

from live_helpers import skip_on_live_connect_error

NEO4J_BOLT_PORT = int(os.environ.get("ASTLOOM_NEO4J_BOLT_PORT", "32287"))
POSTGRES_PORT = int(os.environ.get("ASTLOOM_POSTGRES_PORT", "32232"))
NEO4J_PASSWORD = os.environ.get("ASTLOOM_NEO4J_PASSWORD", "astloom-local-dev-secret")
NEO4J_USER = os.environ.get("ASTLOOM_NEO4J_USER", "neo4j")
POSTGRES_PASSWORD = os.environ.get("ASTLOOM_POSTGRES_PASSWORD", "astloom-local-dev-secret")

_RNG = random.Random(20260721)


def _require_tcp(port: int) -> None:
    import socket

    sock = socket.socket()
    sock.settimeout(2)
    try:
        sock.connect(("127.0.0.1", port))
    except OSError as exc:
        pytest.skip(f"port {port} unreachable: {exc}")
    finally:
        sock.close()


def _live_service() -> tuple[Neo4jStore, CodeGraphService, Scope]:
    _require_tcp(NEO4J_BOLT_PORT)
    try:
        store = Neo4jStore(
            uri=f"bolt://127.0.0.1:{NEO4J_BOLT_PORT}",
            user=NEO4J_USER,
            password=NEO4J_PASSWORD,
            ensure_schema=True,
            gds_enabled=True,
            gds_concurrency=4,
        )
    except Exception as exc:  # noqa: BLE001
        skip_on_live_connect_error(exc)
        raise  # pragma: no cover
    scope = Scope("tenant-fuzz", "ws-fuzz", f"fuzz-{uuid.uuid4().hex[:10]}")
    service = CodeGraphService(
        store,
        embeddings=HybridEmbeddings(stub=LocalEmbeddingStub(dims=1024), dims=1024, local=None),
    )
    return store, service, scope


# ---------------------------------------------------------------------------
# Unit fuzzers
# ---------------------------------------------------------------------------

FUZZ_QUERIES_TOKENIZE = [
    "",
    "   ",
    "a",
    "ab",
    "login",
    "login auth",
    "hash_password",
    "معتبرسازی ورود",
    "🚀 rocket login",
    "a" * 5000,
    "foo.bar.baz",
    "path/to/file.py",
]


@pytest.mark.parametrize("query", FUZZ_QUERIES_TOKENIZE, ids=[f"tok{i}" for i in range(12)])
def test_fuzz_tokenize_never_raises(query: str):
    tokens = tokenize(query)
    assert isinstance(tokens, list)
    assert all(isinstance(t, str) for t in tokens)


FUZZ_LUCENE = [
    "",
    "login",
    'hash_password("x")',
    "a+b|c&&d",
    "[[[",
    "foo~2",
    "path/auth/login.py",
    "*" * 40,
]


@pytest.mark.parametrize("raw", FUZZ_LUCENE, ids=[f"luc{i}" for i in range(8)])
def test_fuzz_lucene_query_safe(raw: str):
    out = _lucene_query(raw)
    assert isinstance(out, str)
    if out:
        assert len(out) < 10_000


FUZZ_BM25 = [
    ("login", [("1", "login user"), ("2", "render")]),
    ("", [("1", "login")]),
    ("zzzz_missing", [("1", "login user")]),
    ("login " * 200, [("1", "login"), ("2", "login auth")]),
]


@pytest.mark.parametrize("query,corpus", FUZZ_BM25, ids=[f"bm{i}" for i in range(4)])
def test_fuzz_bm25_rank_stable(query: str, corpus: list[tuple[str, str]]):
    ranked = lexical_rank(query, corpus, top_k=10)
    scored = lexical_rank_scored(query, corpus, top_k=10)
    assert isinstance(ranked, list)
    assert len(ranked) == len(scored)
    assert ranked == [sid for sid, _ in scored]


def test_fuzz_rrf_merge_empty_and_dupes():
    assert rrf_merge() == []
    assert rrf_merge([]) == []
    merged = rrf_merge(["a", "b"], ["b", "a"], ["a"])
    assert merged[0][0] == "a"


def test_fuzz_coalesce_rank_lists_filters_empty():
    assert coalesce_rank_lists(None, [], ["x", ""], None) == [["x"]]


FUZZ_GDS_CONC = ["", "4", "1", "0", "-3", "16", "99", "abc"]


@pytest.mark.parametrize("raw", FUZZ_GDS_CONC, ids=[f"gds{i}" for i in range(8)])
def test_fuzz_gds_concurrency_clamped_1_to_4(raw: str):
    n = _gds_concurrency(raw)
    assert 1 <= n <= 4


FUZZ_COMMUNITIES: list[tuple[list[str], list[tuple[str, str, str]]]] = [
    ([], []),
    (["a"], []),
    (["a", "b"], [("a", "b", "CALLS")]),
    (
        ["a", "b", "c", "d"],
        [("a", "b", "CALLS"), ("b", "a", "CALLS"), ("c", "d", "CALLS"), ("d", "c", "CALLS")],
    ),
]


@pytest.mark.parametrize("nodes,edges", FUZZ_COMMUNITIES, ids=[f"com{i}" for i in range(4)])
def test_fuzz_communities_deterministic(nodes, edges):
    c1 = detect_communities(nodes, edges, seed=7)
    c2 = detect_communities(nodes, edges, seed=7)
    assert [x.member_ids for x in c1] == [x.member_ids for x in c2]
    covered = {m for c in c1 for m in c.member_ids}
    assert covered == set(nodes)
    if nodes:
        assert last_community_algorithm() in {
            "scikit_network_leiden",
            "louvain_leiden_refine",
            "isolated_nodes",
        }


def test_fuzz_searchable_text_handles_huge_body():
    text = searchable_text(name="n", body="x" * 5000, body_limit=100)
    assert "n" in text
    assert len(text) < 5200


# Unit items: 12+8+4+1+1+8+4+1 = 39; live: 6+5 = 11 → 50 total

LIVE_QUERIES = [
    "login",
    "!!!@@@###",
    "معتبرسازی",
    "a" * 800,
    'foo AND bar OR "baz"',
    "../../etc/passwd",
]


@pytest.fixture(scope="module")
def fuzz_live_ready():
    _require_tcp(NEO4J_BOLT_PORT)


@pytest.fixture(scope="module")
def fuzz_seeded_service(fuzz_live_ready):
    try:
        store, service, scope = _live_service()
        src = (
            "def login(u,p):\n    return check_password(p)\n\n"
            "def check_password(p):\n    return len(p)>8\n\n"
            "def render_dashboard(t):\n    return t\n"
        )
        service.ingest_file(
            scope,
            "agent",
            "corr-fuzz",
            f"idem-fuzz-{uuid.uuid4().hex}",
            {"file_path": "src/fuzz_auth.py", "source": src, "language": "python"},
        )
    except Exception as exc:  # noqa: BLE001
        skip_on_live_connect_error(exc)
        raise  # pragma: no cover
    yield store, service, scope
    store.close()


@pytest.mark.parametrize("query", LIVE_QUERIES, ids=[f"liveq{i}" for i in range(6)])
def test_fuzz_live_hybrid_and_explore_survive(fuzz_seeded_service, query: str):
    _store, service, scope = fuzz_seeded_service
    if not query.strip():
        with pytest.raises(ValidationError):
            service.hybrid_search(scope, query, top_k=5)
        return
    hybrid = service.hybrid_search(scope, query, top_k=5)
    assert "hits" in hybrid and "mode" in hybrid
    explore = service.explore(scope, query, top_k=6, max_depth=2)
    assert "sections" in explore
    assert "freshness" in explore


def test_fuzz_live_empty_query_rejected(fuzz_seeded_service):
    _store, service, scope = fuzz_seeded_service
    with pytest.raises(ValidationError):
        service.hybrid_search(scope, "   ", top_k=3)
    with pytest.raises(ValidationError):
        service.explore(scope, "", top_k=3)


def test_fuzz_live_architecture_and_path_random_pair(fuzz_seeded_service):
    store, service, scope = fuzz_seeded_service
    overview = service.architecture_overview(scope, top_n=5)
    assert "algorithm" in overview
    symbols = [s for s in store.list_symbols(scope) if s.kind.value in {"function", "method"}]
    assert symbols
    a = symbols[_RNG.randrange(len(symbols))]
    b = symbols[_RNG.randrange(len(symbols))]
    path = service.symbol_path(scope, a.id, b.id, max_depth=6)
    assert path["method"] in {"neo4j_shortest_path", "in_memory_bfs"}
    assert isinstance(path["reachable"], bool)


def test_fuzz_live_postgres_fts_weird_query(fuzz_live_ready):
    from code_graph_service.postgres_store import PostgresStore

    _require_tcp(POSTGRES_PORT)
    url = f"postgresql://astloom:{POSTGRES_PASSWORD}@127.0.0.1:{POSTGRES_PORT}/astloom"
    store = None
    try:
        store = PostgresStore(url, ensure_schema=True)
        scope = Scope("tenant-fuzz", "ws-fuzz", f"pgfuzz-{uuid.uuid4().hex[:8]}")
        service = CodeGraphService(
            store,
            embeddings=HybridEmbeddings(stub=LocalEmbeddingStub(dims=1024), dims=1024, local=None),
        )
        service.ingest_file(
            scope,
            "agent",
            "corr-pg",
            f"idem-pg-{uuid.uuid4().hex}",
            {
                "file_path": "x.py",
                "source": "def alpha_beta_gamma():\n    return 1\n",
                "language": "python",
            },
        )
        for q in ("alpha", "!!!", "معتبر", "alpha_beta_gamma"):
            _ = store.fulltext_search(scope, q, top_k=5)
            hybrid = service.hybrid_search(scope, q if q.strip() else "alpha", top_k=3)
            assert "hits" in hybrid
    except Exception as exc:  # noqa: BLE001
        skip_on_live_connect_error(exc)
    finally:
        if store is not None:
            store.close()


def test_fuzz_live_gds_off_degree_method(fuzz_live_ready):
    try:
        store = Neo4jStore(
            uri=f"bolt://127.0.0.1:{NEO4J_BOLT_PORT}",
            user=NEO4J_USER,
            password=NEO4J_PASSWORD,
            ensure_schema=True,
            gds_enabled=False,
            gds_concurrency=99,
        )
    except Exception as exc:  # noqa: BLE001
        skip_on_live_connect_error(exc)
        raise  # pragma: no cover
    try:
        caps = store.capabilities()
        assert caps["gds"] is False
        assert caps["gds_concurrency"] == 4
        scope = Scope("tenant-fuzz", "ws-fuzz", f"gdsfuzz-{uuid.uuid4().hex[:8]}")
        service = CodeGraphService(store)
        service.ingest_file(
            scope,
            "agent",
            "c",
            f"i-{uuid.uuid4().hex}",
            {"file_path": "a.py", "source": "def f():\n    return 1\n", "language": "python"},
        )
        ranked = store.rank_symbols_by_degree(scope, top_k=5)
        assert ranked
        assert all(r["method"] == "cypher.degree" for r in ranked)
    finally:
        store.close()


def test_fuzz_live_random_corpus_bm25_then_hybrid(fuzz_seeded_service):
    _store, service, scope = fuzz_seeded_service
    soup = " ".join(
        "".join(_RNG.choices(string.ascii_letters + "_", k=_RNG.randint(3, 12)))
        for _ in range(40)
    )
    hybrid = service.hybrid_search(scope, soup + " login", top_k=8)
    assert hybrid["mode"] in {
        "bm25",
        "hybrid_rrf_semantic_bm25",
        "hybrid_rrf_fts_semantic_bm25",
    }
    assert isinstance(hybrid.get("channels"), dict)

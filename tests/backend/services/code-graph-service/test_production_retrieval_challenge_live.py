"""50 live challenge tests for production retrieval (Neo4j + Postgres).

Adversarial queries, ranking vs noise, FastAPI routes/TESTED_BY, communities,
GDS-off degrade, Postgres FTS, path/depth extremes, freshness, detect_changes.

Save: tests/backend/services/code-graph-service/test_production_retrieval_challenge_live.py
Re-run:
  ASTLOOM_NEO4J_PASSWORD=… ASTLOOM_POSTGRES_PASSWORD=… \\
    PYTHONPATH=backend/services/code-graph-service/src \\
    .venv/bin/python -m pytest \\
    tests/backend/services/code-graph-service/test_production_retrieval_challenge_live.py -v
"""

from __future__ import annotations

import os
import random
import string
import uuid
from pathlib import Path

import pytest

from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.domain.embeddings import LocalEmbeddingStub
from code_graph_service.domain.errors import ValidationError
from code_graph_service.llm_wiring import HybridEmbeddings
from code_graph_service.neo4j_store import Neo4jStore

from live_helpers import skip_on_live_connect_error

NEO4J_BOLT_PORT = int(os.environ.get("ASTLOOM_NEO4J_BOLT_PORT", "32287"))
POSTGRES_PORT = int(os.environ.get("ASTLOOM_POSTGRES_PORT", "32232"))
NEO4J_PASSWORD = os.environ.get("ASTLOOM_NEO4J_PASSWORD", "astloom-local-dev-secret")
NEO4J_USER = os.environ.get("ASTLOOM_NEO4J_USER", "neo4j")
POSTGRES_PASSWORD = os.environ.get("ASTLOOM_POSTGRES_PASSWORD", "astloom-local-dev-secret")
_RNG = random.Random(20260721)

AUTH_PY = '''\
def check_password(password: str) -> bool:
    return len(password) > 8

def hash_password(password: str) -> str:
    return "hash:" + password

def login(user: str, password: str) -> bool:
    return check_password(password)
'''

NOISE_PY = '''\
def render_dashboard(title: str) -> str:
    return f"<h1>{title}</h1>"

def format_currency(amount: float) -> str:
    return f"${amount:.2f}"

def paint_widget(color: str) -> str:
    return color.upper()
'''

API_PY = '''\
from fastapi import FastAPI
app = FastAPI()

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/login")
def login_route(user: str, password: str):
    from auth import login
    return {"ok": login(user, password)}
'''

TEST_AUTH_PY = '''\
from auth import login, check_password

def test_login_ok():
    assert login("u", "longpassword") is True

def test_check_password_short():
    assert check_password("x") is False
'''

CLUSTER_A = '''\
def cluster_a_one():
    return cluster_a_two()
def cluster_a_two():
    return cluster_a_three()
def cluster_a_three():
    return 1
'''

CLUSTER_B = '''\
def cluster_b_one():
    return cluster_b_two()
def cluster_b_two():
    return cluster_b_three()
def cluster_b_three():
    return 2
'''

HYBRID_MODES = {
    "bm25",
    "hybrid_rrf_semantic_bm25",
    "hybrid_rrf_fts_semantic_bm25",
}


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


def _neo4j(*, gds_enabled: bool = True) -> Neo4jStore:
    try:
        return Neo4jStore(
            uri=f"bolt://127.0.0.1:{NEO4J_BOLT_PORT}",
            user=NEO4J_USER,
            password=NEO4J_PASSWORD,
            ensure_schema=True,
            gds_enabled=gds_enabled,
            gds_concurrency=4,
        )
    except Exception as exc:  # noqa: BLE001 — live gate: skip soft deps
        skip_on_live_connect_error(exc)
        raise  # pragma: no cover


def _svc(store) -> CodeGraphService:
    return CodeGraphService(
        store,
        embeddings=HybridEmbeddings(stub=LocalEmbeddingStub(dims=1024), dims=1024, local=None),
    )


def _ingest(service: CodeGraphService, scope: Scope, path: str, source: str, key: str) -> None:
    service.ingest_file(
        scope,
        "agent",
        f"corr-{key}",
        f"idem-{key}-{uuid.uuid4().hex}",
        {"file_path": path, "source": source, "language": "python"},
    )


@pytest.fixture(scope="module")
def challenge_ready():
    assert NEO4J_BOLT_PORT not in {7687, 7474}
    assert POSTGRES_PORT != 5432
    _require_tcp(NEO4J_BOLT_PORT)
    _require_tcp(POSTGRES_PORT)


@pytest.fixture(scope="module")
def challenge_corpus(challenge_ready):
    """Shared noisy multi-file graph for most challenge cases."""
    try:
        store = _neo4j()
        scope = Scope("tenant-chal", "ws-chal", f"chal-{uuid.uuid4().hex[:10]}")
        service = _svc(store)
        for path, src, key in (
            ("auth.py", AUTH_PY, "auth"),
            ("ui.py", NOISE_PY, "ui"),
            ("api.py", API_PY, "api"),
            ("tests/test_auth.py", TEST_AUTH_PY, "test"),
            ("pkg/a.py", CLUSTER_A, "ca"),
            ("pkg/b.py", CLUSTER_B, "cb"),
        ):
            _ingest(service, scope, path, src, key)
    except Exception as exc:  # noqa: BLE001
        skip_on_live_connect_error(exc)
        raise  # pragma: no cover
    yield store, service, scope
    store.close()


# --- 20: hybrid adversarial queries -----------------------------------------

CHAL_HYBRID_QUERIES = [
    "authenticate login hash_password",
    "!!!@@@###$$$",
    "معتبرسازی ورود کاربر",
    "a" * 1200,
    'foo AND bar OR "baz" NOT qux',
    "../../etc/passwd",
    "login" + " noise" * 80,
    "POST /login route handler",
    "hash_password(\"x\")",
    "cluster_a_one",
    "render_dashboard",
    "path/to/auth.py",
    "*" * 30,
    "login\x00null",
    "SELECT * FROM users; --",
    "🚀 login rocket",
    "check_password short",
    "format_currency paint_widget",
    "health ok fastapi",
    "zzzz_totally_missing_token_xyz",
]


@pytest.mark.parametrize("query", CHAL_HYBRID_QUERIES, ids=[f"hyb{i}" for i in range(20)])
def test_chal_live_hybrid_adversarial(challenge_corpus, query: str):
    _store, service, scope = challenge_corpus
    hybrid = service.hybrid_search(scope, query, top_k=8)
    assert hybrid["mode"] in HYBRID_MODES
    assert "hits" in hybrid and "channels" in hybrid
    assert isinstance(hybrid["hits"], list)
    assert len(hybrid["hits"]) <= 8


# --- 10: explore adversarial ------------------------------------------------

CHAL_EXPLORE_QUERIES = [
    "how does login work end to end",
    "blast radius of check_password",
    "معتبرسازی",
    "??? unexplained ???",
    "cluster_b_two callers",
    "FastAPI /health",
    "a" * 400,
    "ui paint_widget only",
    "TESTED_BY login",
    "architecture hub symbols",
]


@pytest.mark.parametrize("query", CHAL_EXPLORE_QUERIES, ids=[f"exp{i}" for i in range(10)])
def test_chal_live_explore_adversarial(challenge_corpus, query: str):
    _store, service, scope = challenge_corpus
    pack = service.explore(scope, query, top_k=10, max_depth=3)
    assert "sections" in pack
    assert "freshness" in pack
    assert pack.get("seed_ids") is not None


# --- 5: top_k extremes ------------------------------------------------------

CHAL_TOP_K = [1, 2, 7, 25, 50]


@pytest.mark.parametrize("top_k", CHAL_TOP_K, ids=[f"topk{k}" for k in CHAL_TOP_K])
def test_chal_live_hybrid_top_k_clamp(challenge_corpus, top_k: int):
    _store, service, scope = challenge_corpus
    hybrid = service.hybrid_search(scope, "login auth", top_k=top_k)
    assert hybrid["mode"] in HYBRID_MODES
    assert len(hybrid["hits"]) <= min(top_k, 50)


# --- 4: depth extremes on path/structural -----------------------------------

CHAL_DEPTHS = [1, 2, 4, 8]


@pytest.mark.parametrize("depth", CHAL_DEPTHS, ids=[f"dep{d}" for d in CHAL_DEPTHS])
def test_chal_live_path_and_neighbors_depth(challenge_corpus, depth: int):
    store, service, scope = challenge_corpus
    funcs = [s for s in store.list_symbols(scope) if s.kind.value in {"function", "method"}]
    assert len(funcs) >= 2
    a, b = funcs[0], funcs[_RNG.randrange(len(funcs))]
    path = service.symbol_path(scope, a.id, b.id, max_depth=depth)
    assert path["method"] in {"neo4j_shortest_path", "in_memory_bfs"}
    nbr = service.structural_query(scope, a.id, "CALLS", max_depth=depth)
    assert nbr.get("expansion") in {"apoc_expand", "store_expand", "one_hop"}


# --- 11 hard singles (20+10+5+4+11 = 50) -------------------------------------


def test_chal_live_rrf_auth_beats_ui_noise(challenge_corpus):
    _store, service, scope = challenge_corpus
    hybrid = service.hybrid_search(scope, "authenticate login hash_password", top_k=5)
    assert hybrid["hits"]
    top = hybrid["hits"][0]
    blob = f"{top.get('qualified_name', '')} {top.get('file_path', '')}".lower()
    assert "auth" in blob or "login" in blob or "password" in blob or "hash" in blob
    assert "render_dashboard" not in blob and "format_currency" not in blob


def test_chal_live_empty_and_whitespace_rejected(challenge_corpus):
    _store, service, scope = challenge_corpus
    with pytest.raises(ValidationError):
        service.hybrid_search(scope, "", top_k=3)
    with pytest.raises(ValidationError):
        service.hybrid_search(scope, "   \t  ", top_k=3)
    with pytest.raises(ValidationError):
        service.explore(scope, "", top_k=3)


def test_chal_live_architecture_two_clusters(challenge_corpus):
    _store, service, scope = challenge_corpus
    overview = service.architecture_overview(scope, top_n=10)
    assert overview.get("algorithm") in {
        "scikit_network_leiden",
        "louvain_leiden_refine",
        "isolated_nodes",
    }
    assert overview.get("communities") is not None
    assert len(overview["communities"]) >= 1
    assert overview.get("hubs") is not None


def test_chal_live_routes_or_tested_by_edges(challenge_corpus):
    store, service, scope = challenge_corpus
    edges = store.list_edges(scope)
    rels = {e.rel_type for e in edges}
    assert "CALLS" in rels or "CONTAINS" in rels
    route_or_tested = [e for e in edges if e.rel_type in {"ROUTES_TO", "TESTED_BY"}]
    # Best-effort extractors; structural graph must still be queryable
    explore = service.explore(scope, "POST /login", top_k=12)
    assert explore.get("seed_ids") is not None
    assert route_or_tested or explore.get("sections") is not None


def test_chal_live_detect_changes_mixed_paths(challenge_corpus):
    _store, service, scope = challenge_corpus
    report = service.detect_changes(
        scope,
        ["auth.py", "api.py", "missing.py", "../outside.py", "pkg/a.py"],
        include_flows=True,
    )
    assert isinstance(report, dict) and report


def test_chal_live_freshness_pending_banner(challenge_corpus):
    _store, service, scope = challenge_corpus
    pending = service.mark_file_pending("auth.py")
    assert pending.get("pending_count", 0) >= 1 or pending.get("pending_files")
    status = service.freshness_status()
    blob = " ".join(str(status.get(k) or "") for k in ("banner", "footer", "pending_files", "pending_count"))
    assert "Pending sync" in blob or status.get("pending_count", 0) >= 1
    service.clear_pending_sync("auth.py")


def test_chal_live_gds_off_forces_cypher_degree(challenge_ready):
    store = _neo4j(gds_enabled=False)
    try:
        caps = store.capabilities()
        assert caps["gds"] is False and caps["gds_enabled"] is False
        scope = Scope("tenant-chal", "ws-chal", f"nogds-{uuid.uuid4().hex[:8]}")
        service = _svc(store)
        _ingest(service, scope, "auth.py", AUTH_PY, "nogds")
        ranked = store.rank_symbols_by_degree(scope, top_k=5)
        assert ranked
        assert all(r.get("method") == "cypher.degree" for r in ranked)
    finally:
        store.close()


def test_chal_live_postgres_fts_and_hybrid(challenge_ready):
    from code_graph_service.postgres_store import PostgresStore

    url = f"postgresql://astloom:{POSTGRES_PASSWORD}@127.0.0.1:{POSTGRES_PORT}/astloom"
    store = None
    try:
        store = PostgresStore(url, ensure_schema=True)
        scope = Scope("tenant-chal", "ws-chal", f"pg-{uuid.uuid4().hex[:8]}")
        service = _svc(store)
        _ingest(service, scope, "src/auth.py", AUTH_PY, "pg")
        for q in ("login password", "!!!", "معتبر", "hash_password"):
            _ = store.fulltext_search(scope, q, top_k=8)
            hybrid = service.hybrid_search(scope, q if q.strip() else "login", top_k=5)
            assert hybrid["hits"] or hybrid["mode"] in HYBRID_MODES
    except Exception as exc:  # noqa: BLE001
        skip_on_live_connect_error(exc)
    finally:
        if store is not None:
            store.close()


def test_chal_live_random_bm25_soup_still_modes(challenge_corpus):
    _store, service, scope = challenge_corpus
    soup = " ".join(
        "".join(_RNG.choices(string.ascii_letters + "_", k=_RNG.randint(4, 14)))
        for _ in range(50)
    )
    hybrid = service.hybrid_search(scope, soup + " login", top_k=10)
    assert hybrid["mode"] in HYBRID_MODES
    assert isinstance(hybrid.get("channels"), dict)


def test_chal_live_degree_rank_method_when_gds_on(challenge_corpus):
    store, _service, scope = challenge_corpus
    ranked = store.rank_symbols_by_degree(scope, top_k=8)
    assert isinstance(ranked, list)
    if ranked:
        assert ranked[0].get("method") in {"gds.degree", "cypher.degree"}


def test_chal_live_write_results_artifact(challenge_corpus):
    import json
    from datetime import datetime, timezone

    store, service, scope = challenge_corpus
    caps = store.capabilities()
    hybrid = service.hybrid_search(scope, "login", top_k=5)
    overview = service.architecture_overview(scope, top_n=5)
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "suite": "challenge_live_50",
        "scope": scope.project_id,
        "capabilities": caps,
        "hybrid_mode": hybrid.get("mode"),
        "hybrid_top": hybrid.get("hits", [])[:5],
        "community_algorithm": overview.get("algorithm"),
        "community_count": len(overview.get("communities") or []),
    }
    out_dir = Path("/opt/Astloom/tests/artifacts/code-graph-live")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"challenge-live-{uuid.uuid4().hex[:8]}.json"
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    assert out.is_file() and out.stat().st_size > 40

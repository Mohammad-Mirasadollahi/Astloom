"""Production retrieval stack tests: BM25, hybrid modes, communities backend."""

from __future__ import annotations

from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.domain.communities import detect_communities, last_community_algorithm
from code_graph_service.domain.hybrid_search import lexical_rank, lexical_rank_scored, searchable_text
from code_graph_service.neo4j_store import _lucene_query
from code_graph_service.testing import InMemoryStore


def test_bm25_ranks_relevant_symbol_first():
    corpus = [
        ("1", searchable_text(name="login", qualified_name="auth.login", signature="def login()")),
        ("2", searchable_text(name="render", qualified_name="ui.render", signature="def render()")),
        ("3", searchable_text(name="authenticate", qualified_name="auth.authenticate", file_path="auth/login.py")),
    ]
    ranked = lexical_rank("login auth", corpus, top_k=3)
    assert ranked[0] in {"1", "3"}
    scored = lexical_rank_scored("login", corpus, top_k=3)
    assert scored[0][1] > 0


def test_bm25_supports_persian_tokens_and_script_variants():
    corpus = [
        ("auth", "قوانین ورود کاربر و رمز عبور امن"),
        ("ui", "راهنمای نمایش داشبورد و نمودار"),
    ]
    ranked = lexical_rank_scored("قوانين ورود و رمز عبور", corpus, top_k=2)
    assert ranked
    assert ranked[0][0] == "auth"
    assert ranked[0][1] > 0


def test_lucene_query_ors_tokens():
    q = _lucene_query('hash_password("x") path/auth')
    assert "OR" in q
    assert "hash_password" in q or "hash" in q


def test_communities_report_algorithm():
    nodes = ["a", "b", "c", "d"]
    edges = [
        ("a", "b", "CALLS"),
        ("b", "a", "CALLS"),
        ("c", "d", "CALLS"),
        ("d", "c", "CALLS"),
    ]
    found = detect_communities(nodes, edges, seed=1)
    assert found
    algo = last_community_algorithm()
    assert algo in {"scikit_network_leiden", "louvain_leiden_refine"}


def test_hybrid_search_mode_bm25(tmp_path=None):
    service = CodeGraphService(InMemoryStore())
    scope = Scope(tenant_id="t", workspace_id="w", project_id="p")
    # Minimal ingest via put through service would need more setup; use explore path symbols
    from code_graph_service.domain.enums import DocStatus, SymbolKind
    from code_graph_service.domain.models import GraphSymbol

    store = service.store
    for sid, name, qn in (
        ("s1", "login", "pkg.login"),
        ("s2", "render", "pkg.render"),
    ):
        store.put_symbol(
            GraphSymbol(
                id=sid,
                scope=scope,
                kind=SymbolKind.FUNCTION,
                file_path=f"{name}.py",
                name=name,
                qualified_name=qn,
                signature=f"def {name}():",
                body=f"def {name}():\n    pass\n",
                hash_value="h",
                ai_documentation="",
                doc_status=DocStatus.MISSING,
                embedding=[],
                visibility="public",
                version=1,
                created_at="2020-01-01T00:00:00Z",
                updated_at="2020-01-01T00:00:00Z",
            )
        )
    result = service.hybrid_search(scope, "login user", top_k=5)
    assert result["mode"] in {"bm25", "hybrid_rrf_semantic_bm25", "hybrid_rrf_fts_semantic_bm25"}
    assert result["hits"]
    assert result["hits"][0]["symbol_id"] == "s1"
    assert "channels" in result
    assert "embedding_backend" in result

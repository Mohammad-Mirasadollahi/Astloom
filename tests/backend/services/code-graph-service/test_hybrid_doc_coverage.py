"""Hybrid documentation coverage pack tests."""

from __future__ import annotations

from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.domain.hybrid_doc_coverage import (
    FALLBACK_CHAIN,
    build_symbol_doc_coverage,
)
from code_graph_service.testing import InMemoryStore

SCOPE = Scope("t", "w", "hybrid-cov")

SOURCE = """\
# WHY: auth entry must validate password length before session create
def check_password(password):
    return len(password) > 8

def login(user, password):
    return check_password(password)
"""

SOURCE2 = """\
def check_password(password):
    return len(password) > 8

def login(user, password):
    return check_password(password)
"""

SOURCE_RATIONALE_ONLY = """\
# WHY: keep password checks local to this module
def only_fn(x):
    return x
"""


def test_hybrid_coverage_prefers_human_over_living():
    store = InMemoryStore()
    svc = CodeGraphService(store)
    svc.ingest_file(
        SCOPE,
        "agent",
        "c",
        "idem-h",
        {"file_path": "src/auth.py", "source": SOURCE, "language": "python"},
    )
    login_id = f"sym:{SCOPE.project_id}:src.auth.login"
    result = svc.upsert_human_documentation(
        SCOPE,
        doc_id="auth.login",
        relative_path="docs/auth.md",
        title="Auth login",
        body="Human doc for login flow.\n",
        linked_symbol_tokens=["src/auth.py::login"],
    )
    assert login_id in result["linked_symbol_ids"]
    pack = build_symbol_doc_coverage(store, SCOPE, store.get_symbol(login_id, SCOPE))
    assert pack["mode"] == "hybrid"
    assert pack["coverage"]["ast"] is True
    assert pack["coverage"]["human"] is True
    assert pack["preferred_layer"] == "human"
    assert pack["fallback_chain"] == list(FALLBACK_CHAIN)
    assert "human" in pack["active_layers"]
    assert "human" not in pack["gaps"]
    assert pack["invents_edges"] is False
    assert pack["optional"]["llm_auto_pair"]
    assert pack["preferred_snippets"]
    assert "Human doc" in pack["preferred_snippets"][0]

    ctx = svc.build_generation_context(SCOPE, login_id)
    assert "hybrid_documentation" in ctx
    assert ctx["hybrid_documentation"]["preferred_layer"] == "human"
    assert "Hybrid documentation coverage" in ctx["prompt_context"]


def test_hybrid_coverage_falls_back_to_living_or_ast():
    store = InMemoryStore()
    svc = CodeGraphService(store)
    scope = Scope("t", "w", "hybrid-cov-2")
    svc.ingest_file(
        scope,
        "agent",
        "c2",
        "idem-h2",
        {"file_path": "src/auth2.py", "source": SOURCE2, "language": "python"},
    )
    login_id = f"sym:{scope.project_id}:src.auth2.login"
    pack = build_symbol_doc_coverage(store, scope, store.get_symbol(login_id, scope))
    assert pack["coverage"]["ast"] is True
    assert pack["coverage"]["human"] is False
    assert "human" in pack["gaps"]
    assert pack["preferred_layer"] in {"living", "ast", "rationale"}
    assert pack["invents_edges"] is False


def test_hybrid_coverage_prefers_rationale_when_no_human_or_living_text():
    store = InMemoryStore()
    svc = CodeGraphService(store)
    scope = Scope("t", "w", "hybrid-cov-3")
    svc.ingest_file(
        scope,
        "agent",
        "c3",
        "idem-h3",
        {
            "file_path": "src/only.py",
            "source": SOURCE_RATIONALE_ONLY,
            "language": "python",
        },
    )
    fn_id = f"sym:{scope.project_id}:src.only.only_fn"
    seed = store.get_symbol(fn_id, scope)
    seed.ai_documentation = ""
    store.put_symbol(seed)
    # Drop seed→living DOCUMENTED_BY so only file→rationale remains for enrichment.
    for edge in list(store.list_edges(scope)):
        if edge.rel_type != "DOCUMENTED_BY":
            continue
        if edge.source_id != fn_id:
            continue
        if str(edge.target_id).startswith("rationale:"):
            continue
        store.delete_edge(scope, edge.id)

    pack = build_symbol_doc_coverage(store, scope, store.get_symbol(fn_id, scope))
    assert pack["coverage"]["ast"] is True
    assert pack["coverage"]["human"] is False
    assert pack["coverage"]["rationale"] is True
    assert pack["coverage"]["living"] is False
    assert pack["preferred_layer"] == "rationale"
    assert any("password checks" in (s or "") for s in pack["preferred_snippets"])
    assert "living" in pack["gaps"]
    assert "human" in pack["gaps"]


def test_hybrid_coverage_dedupes_human_docs():
    store = InMemoryStore()
    svc = CodeGraphService(store)
    scope = Scope("t", "w", "hybrid-cov-4")
    svc.ingest_file(
        scope,
        "agent",
        "c4",
        "idem-h4",
        {"file_path": "src/auth4.py", "source": SOURCE2, "language": "python"},
    )
    login_id = f"sym:{scope.project_id}:src.auth4.login"
    svc.upsert_human_documentation(
        scope,
        doc_id="auth4.login",
        relative_path="docs/auth4.md",
        title="Auth4",
        body="Human once.\n",
        linked_symbol_tokens=["src/auth4.py::login"],
    )
    pack = build_symbol_doc_coverage(store, scope, store.get_symbol(login_id, scope))
    ids = [d["symbol_id"] for d in pack["layers"]["human_docs"]]
    assert len(ids) == len(set(ids))

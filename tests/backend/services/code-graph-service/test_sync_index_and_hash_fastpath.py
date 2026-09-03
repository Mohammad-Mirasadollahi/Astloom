"""Index/hash listing and pending-edge filters for fast content-push."""

from __future__ import annotations

from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.domain.enums import CallConfidence, DocStatus, SymbolKind
from code_graph_service.domain.hashing import digest, now_iso
from code_graph_service.domain.models import GraphEdge, GraphSymbol
from code_graph_service.testing import InMemoryStore


def _scope() -> Scope:
    return Scope("t", "w", "p-fast")


def _sym(
    scope: Scope,
    *,
    sid: str,
    name: str,
    kind: SymbolKind,
    path: str = "a.py",
    body: str = "BODY_SHOULD_NOT_MATTER",
) -> GraphSymbol:
    stamp = now_iso()
    return GraphSymbol(
        id=sid,
        scope=scope,
        kind=kind,
        file_path=path,
        name=name,
        qualified_name=name if kind != SymbolKind.FILE else path,
        signature="sig",
        body=body,
        hash_value=digest(name + path),
        ai_documentation="DOCS",
        doc_status=DocStatus.UNCHANGED,
        embedding=[0.1],
        created_at=stamp,
        updated_at=stamp,
        language="python",
    )


def test_list_symbols_index_strips_bulky_fields() -> None:
    store = InMemoryStore()
    scope = _scope()
    store.put_symbol(_sym(scope, sid="f", name="a.py", kind=SymbolKind.FILE))
    store.put_symbol(_sym(scope, sid="fn", name="foo", kind=SymbolKind.FUNCTION))
    indexed = store.list_symbols_index(scope)
    assert len(indexed) == 2
    assert all(s.body == "" for s in indexed)
    assert all(s.ai_documentation == "" for s in indexed)
    assert all(s.embedding == [] for s in indexed)


def test_content_hash_maps_requires_code_children() -> None:
    store = InMemoryStore()
    scope = _scope()
    store.put_symbol(_sym(scope, sid="f1", name="a.py", kind=SymbolKind.FILE, path="a.py"))
    store.put_symbol(_sym(scope, sid="orphan", name="b.py", kind=SymbolKind.FILE, path="b.py"))
    store.put_symbol(_sym(scope, sid="fn", name="foo", kind=SymbolKind.FUNCTION, path="a.py"))
    svc = CodeGraphService(store)
    files, docs = svc.content_hash_maps(scope)
    assert "a.py" in files
    assert "b.py" not in files
    assert docs == {}


def test_list_edges_target_id_prefixes_filters_pending_only() -> None:
    store = InMemoryStore()
    scope = _scope()
    store.put_edge(
        GraphEdge(
            id="e1",
            scope=scope,
            rel_type="CALLS",
            source_id="a",
            target_id="unresolved:foo",
            confidence=CallConfidence.UNRESOLVED,
            metadata={},
        )
    )
    store.put_edge(
        GraphEdge(
            id="e2",
            scope=scope,
            rel_type="CALLS",
            source_id="a",
            target_id="fn:bar",
            confidence=CallConfidence.EXACT,
            metadata={},
        )
    )
    pending = store.list_edges(scope, rel_type="CALLS", target_id_prefixes=["unresolved:"])
    assert [e.id for e in pending] == ["e1"]
    all_calls = store.list_edges(scope, rel_type="CALLS")
    assert {e.id for e in all_calls} == {"e1", "e2"}


def test_pushed_partial_inventory_skips_prune_symbol_dump(monkeypatch) -> None:
    """Partial content-push must not prune (or dump symbols for prune)."""
    store = InMemoryStore()
    scope = _scope()
    svc = CodeGraphService(store)
    prune_calls = {"n": 0}

    def boom(*_a, **_k):
        prune_calls["n"] += 1
        raise AssertionError("prune must not run on partial inventory")

    monkeypatch.setattr(svc, "_prune_removed_source_symbols", boom)
    result = svc.ingest_pushed_sources(
        scope,
        "actor",
        "corr",
        "idem-1",
        {
            "files": [
                {
                    "file_path": "x.py",
                    "source": "def hello():\n    return 1\n",
                    "language": "python",
                }
            ],
            "finalize_cross_file": False,
            "embedding_refresh_mode": "skip",
            "inventory_complete": False,
        },
    )
    assert result.files_failed == 0
    assert prune_calls["n"] == 0

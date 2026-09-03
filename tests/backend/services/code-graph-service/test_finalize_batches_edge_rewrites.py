"""Finalize must batch Neo4j edge deletes/puts (not one round-trip per unresolved)."""

from __future__ import annotations

from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.domain.enums import CallConfidence, DocStatus, SymbolKind
from code_graph_service.domain.hashing import digest, now_iso
from code_graph_service.domain.models import GraphEdge, GraphSymbol
from code_graph_service.testing import InMemoryStore


class _CountingStore(InMemoryStore):
    def __init__(self) -> None:
        super().__init__()
        self.delete_edge_calls = 0
        self.delete_edges_calls = 0
        self.put_edge_calls = 0
        self.put_edges_calls = 0

    def delete_edge(self, scope: Scope, edge_id: str) -> None:
        self.delete_edge_calls += 1
        super().delete_edge(scope, edge_id)

    def delete_edges(self, scope: Scope, edge_ids: list[str]) -> None:
        self.delete_edges_calls += 1
        super().delete_edges(scope, edge_ids)

    def put_edge(self, edge: GraphEdge) -> None:
        self.put_edge_calls += 1
        super().put_edge(edge)

    def put_edges(self, edges: list[GraphEdge]) -> None:
        self.put_edges_calls += 1
        super().put_edges(edges)


def _sym(scope: Scope, *, sid: str, name: str, kind: SymbolKind = SymbolKind.FUNCTION) -> GraphSymbol:
    stamp = now_iso()
    return GraphSymbol(
        id=sid,
        scope=scope,
        kind=kind,
        file_path="a.py",
        name=name,
        qualified_name=name,
        signature=f"def {name}()",
        body="",
        hash_value=digest(name),
        ai_documentation="",
        doc_status=DocStatus.UNCHANGED,
        embedding=[],
        created_at=stamp,
        updated_at=stamp,
    )


def test_finalize_batches_unresolved_call_rewrites():
    store = _CountingStore()
    svc = CodeGraphService(store)
    scope = Scope("t", "w", "batch-finalize")
    src = _sym(scope, sid="sym:batch-finalize:src", name="src")
    dst = _sym(scope, sid="sym:batch-finalize:dst", name="dst")
    unresolved = _sym(
        scope,
        sid="unresolved:batch-finalize:dst",
        name="dst",
        kind=SymbolKind.UNRESOLVED,
    )
    store.put_symbol(src)
    store.put_symbol(dst)
    store.put_symbol(unresolved)
    n = 40
    for i in range(n):
        store.put_edge(
            GraphEdge(
                id=f"edge:old-{i}",
                scope=scope,
                rel_type="CALLS",
                source_id=src.id,
                target_id=unresolved.id,
                confidence=CallConfidence.UNRESOLVED,
                metadata={"call": "dst", "file_path": "a.py"},
            )
        )

    store.delete_edge_calls = 0
    store.delete_edges_calls = 0
    store.put_edge_calls = 0
    store.put_edges_calls = 0

    written = svc.finalize_cross_file_resolution(scope)
    assert written >= n
    # Root cause of hung sync: N delete_edge round-trips. Must be bulk.
    assert store.delete_edge_calls == 0
    assert store.delete_edges_calls >= 1
    assert store.put_edge_calls == 0
    assert store.put_edges_calls >= 1

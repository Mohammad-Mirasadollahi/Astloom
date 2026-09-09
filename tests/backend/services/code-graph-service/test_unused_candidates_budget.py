"""unused_candidates must stay inside MCP budgets on large projects.

Root cause of ThinkingSOC -32001: anchored modes dumped full list_edges /
list_symbols_compact. Soft budget covers project_scan headroom under hard 25s.
"""

from __future__ import annotations

import time

from code_graph_service.application.service import CodeGraphService
from code_graph_service.domain.enums import CallConfidence, DocStatus, RelType, SymbolKind
from code_graph_service.domain.models import GraphEdge, GraphSymbol, Scope
from code_graph_service.testing import InMemoryStore


class CountingStore(InMemoryStore):
    def __init__(self) -> None:
        super().__init__()
        self.list_symbols_calls = 0
        self.list_edges_calls: list[dict] = []

    def list_symbols(self, scope: Scope) -> list[GraphSymbol]:
        self.list_symbols_calls += 1
        return super().list_symbols(scope)

    def list_symbols_index(self, scope: Scope) -> list[GraphSymbol]:
        self.list_symbols_calls += 1
        return super().list_symbols_index(scope)

    def list_symbols_lean(self, scope: Scope) -> list[GraphSymbol]:
        self.list_symbols_calls += 1
        return super().list_symbols_lean(scope)

    def list_edges(self, scope: Scope, **kwargs):  # type: ignore[no-untyped-def]
        self.list_edges_calls.append(dict(kwargs))
        return super().list_edges(scope, **kwargs)


def _fill_noise(store: CountingStore, scope: Scope, n: int = 200) -> None:
    for i in range(n):
        store.put_symbol(
            GraphSymbol(
                id=f"s:noise:{i}",
                scope=scope,
                kind=SymbolKind.FUNCTION,
                file_path=f"noise/m{i}.py",
                name=f"noise_{i}",
                qualified_name=f"noise.m{i}.noise_{i}",
                signature=f"def noise_{i}():",
                body="return 1",
                hash_value="h",
                ai_documentation="",
                doc_status=DocStatus.UNCHANGED,
                embedding=[],
                visibility="public",
            )
        )
        if i > 0:
            store.put_edge(
                GraphEdge(
                    id=f"e:noise:{i}",
                    scope=scope,
                    rel_type=RelType.CALLS.value,
                    source_id=f"s:noise:{i}",
                    target_id=f"s:noise:{i - 1}",
                    confidence=CallConfidence.EXACT,
                )
            )


def test_changed_symbols_does_not_full_dump_project():
    store = CountingStore()
    scope = Scope("t", "w", "narrow_unused")
    svc = CodeGraphService(store)
    _fill_noise(store, scope, n=200)
    orphan = GraphSymbol(
        id="s:orphan",
        scope=scope,
        kind=SymbolKind.FUNCTION,
        file_path="pkg/orphan.py",
        name="orphan_fn",
        qualified_name="pkg.orphan.orphan_fn",
        signature="def orphan_fn():",
        body="return 1",
        hash_value="h",
        ai_documentation="",
        doc_status=DocStatus.UNCHANGED,
        embedding=[],
        visibility="private",
    )
    store.put_symbol(orphan)
    svc.record_sync_stamp(scope)

    store.list_symbols_calls = 0
    store.list_edges_calls = []
    out = svc.unused_candidates(
        scope,
        scope_mode="changed_symbols",
        anchor_symbols=["orphan_fn"],
        max_results=10,
        min_confidence=0.8,
    )
    assert out.get("candidates") is not None
    unscoped_edge_dumps = [
        c
        for c in store.list_edges_calls
        if not c.get("source_id") and not c.get("target_id") and not c.get("target_id_prefixes")
    ]
    assert not unscoped_edge_dumps, store.list_edges_calls
    assert store.list_symbols_calls == 0


def test_project_scan_soft_budget_returns_degraded_instead_of_hanging():
    store = CountingStore()
    scope = Scope("t", "w", "budget_unused")
    svc = CodeGraphService(store)
    store.put_symbol(
        GraphSymbol(
            id="s:a",
            scope=scope,
            kind=SymbolKind.FUNCTION,
            file_path="a.py",
            name="a",
            qualified_name="a.a",
            signature="def a():",
            body="return 1",
            hash_value="h",
            ai_documentation="",
            doc_status=DocStatus.UNCHANGED,
            embedding=[],
            visibility="private",
        )
    )
    svc.record_sync_stamp(scope)

    original = store.list_symbols_index

    def _slow_index(scope_arg: Scope):
        time.sleep(2.0)
        return original(scope_arg)

    store.list_symbols_index = _slow_index  # type: ignore[method-assign]
    deadline = time.monotonic() + 0.15
    t0 = time.monotonic()
    out = svc.unused_candidates(
        scope,
        scope_mode="project_scan",
        max_results=5,
        min_confidence=0.5,
        deadline_monotonic=deadline,
    )
    elapsed = time.monotonic() - t0
    # Must return soon after soft deadline — not wait for the worker to finish.
    assert elapsed < 0.8, elapsed
    assert out.get("degraded") is True
    assert "graph_load" in (out.get("truncated_phases") or [])

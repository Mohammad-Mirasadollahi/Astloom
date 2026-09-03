"""Per-file emit must not re-dump the whole project graph."""

from __future__ import annotations

from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.domain.enums import CallConfidence, DocStatus, SymbolKind
from code_graph_service.domain.hashing import digest, now_iso
from code_graph_service.domain.models import GraphEdge, GraphSymbol
from code_graph_service.testing import InMemoryStore


class _CountingStore(InMemoryStore):
    def __init__(self) -> None:
        super().__init__()
        self.list_symbols_calls = 0
        self.list_edges_unfiltered = 0

    def list_symbols(self, scope: Scope):
        self.list_symbols_calls += 1
        return super().list_symbols(scope)

    def list_edges(self, scope: Scope, **kwargs):
        if kwargs.get("rel_type") is None and kwargs.get("source_id") is None:
            self.list_edges_unfiltered += 1
        return super().list_edges(scope, **kwargs)


def _scope() -> Scope:
    return Scope("t", "w", "p-emit")


def _sym(scope: Scope, **kw) -> GraphSymbol:
    stamp = now_iso()
    return GraphSymbol(
        id=kw["id"],
        scope=scope,
        kind=kw["kind"],
        file_path=kw.get("path", "a.py"),
        name=kw["name"],
        qualified_name=kw.get("qn", kw["name"]),
        signature="",
        body=kw.get("body", ""),
        hash_value=digest(kw["name"]),
        ai_documentation="",
        doc_status=DocStatus.UNCHANGED,
        embedding=[],
        created_at=stamp,
        updated_at=stamp,
        language="python",
    )


def test_di_and_http_use_shared_maps_without_full_list_symbols() -> None:
    store = _CountingStore()
    scope = _scope()
    store.put_symbol(
        _sym(scope, id="fn", name="handler", kind=SymbolKind.FUNCTION, body="Depends(get_db)")
    )
    store.put_symbol(_sym(scope, id="prov", name="get_db", kind=SymbolKind.FUNCTION))
    store.put_symbol(
        _sym(
            scope,
            id="rt",
            name="GET /x",
            kind=SymbolKind.ROUTE,
            qn="route:GET:/x",
        )
    )
    svc = CodeGraphService(store)
    before = store.list_symbols_calls
    src = "def handler(db=Depends(get_db)):\n    return 1\n"
    n = svc._emit_di_injections(
        scope,
        file_path="a.py",
        source=src,
        language="python",
        short_names={"handler": ["fn"], "get_db": ["prov"]},
    )
    assert n >= 1
    assert store.list_symbols_calls == before

    before_e = store.list_edges_unfiltered
    svc._emit_http_calls(
        scope,
        file_path="a.py",
        source='requests.get("/x")\n',
        language="python",
        routes_by_path={"/x": ["rt"]},
    )
    assert store.list_edges_unfiltered == before_e

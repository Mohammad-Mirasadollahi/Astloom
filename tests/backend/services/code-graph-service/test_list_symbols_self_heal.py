"""Self-heal: default list_symbols stays hang-safe; inventory degrades to FILE-only."""

from __future__ import annotations

from types import SimpleNamespace

from code_graph_service.core import Scope
from code_graph_service.domain.enums import DocStatus, SymbolKind
from code_graph_service.domain.hashing import digest, now_iso
from code_graph_service.domain.models import GraphSymbol
from code_graph_service.domain.ports import (
    list_symbols_for_inventory,
    list_symbols_hydrated,
)
from code_graph_service.testing import InMemoryStore


def _scope() -> Scope:
    return Scope("t", "w", "p-heal")


def _sym(scope: Scope, *, sid: str, name: str, kind: SymbolKind, body: str = "BODY") -> GraphSymbol:
    stamp = now_iso()
    return GraphSymbol(
        id=sid,
        scope=scope,
        kind=kind,
        file_path="a.py",
        name=name,
        qualified_name=name if kind != SymbolKind.FILE else "a.py",
        signature="sig",
        body=body,
        hash_value=digest(name),
        ai_documentation="LIVING_DOC",
        doc_status=DocStatus.UNCHANGED,
        embedding=[0.1],
        created_at=stamp,
        updated_at=stamp,
        language="python",
    )


def test_inmemory_list_symbols_full_keeps_body_for_embed_heal() -> None:
    store = InMemoryStore()
    scope = _scope()
    store.put_symbol(_sym(scope, sid="fn", name="foo", kind=SymbolKind.FUNCTION))
    full = store.list_symbols_full(scope)
    assert full[0].body == "BODY"
    assert full[0].ai_documentation == "LIVING_DOC"
    hydrated = list_symbols_hydrated(store, scope)
    assert hydrated[0].body == "BODY"


def test_list_symbols_for_inventory_self_heals_to_file_on_index_failure() -> None:
    scope = _scope()
    file_row = _sym(scope, sid="file:a", name="a.py", kind=SymbolKind.FILE)

    def _boom(_scope: Scope) -> list[GraphSymbol]:
        raise RuntimeError("neo4j unpack stuck")

    store = SimpleNamespace(
        list_symbols_index=_boom,
        list_symbols_lean=_boom,
        list_symbols=_boom,
        list_file_symbols_index=lambda _scope: [file_row],
    )
    symbols, meta = list_symbols_for_inventory(store, scope, file_only=False)
    assert meta["healed"] is True
    assert meta["mode"] == "file"
    assert "RuntimeError" in str(meta.get("heal_reason") or "")
    assert len(symbols) == 1
    assert symbols[0].id == "file:a"


def test_list_symbols_for_inventory_file_only_skips_index() -> None:
    scope = _scope()
    file_row = _sym(scope, sid="file:a", name="a.py", kind=SymbolKind.FILE)
    calls: list[str] = []

    def _index(_scope: Scope) -> list[GraphSymbol]:
        calls.append("index")
        return []

    store = SimpleNamespace(
        list_symbols_index=_index,
        list_file_symbols_index=lambda _scope: [file_row],
    )
    symbols, meta = list_symbols_for_inventory(store, scope, file_only=True)
    assert calls == []
    assert meta == {"mode": "file", "healed": False}
    assert symbols[0].id == "file:a"

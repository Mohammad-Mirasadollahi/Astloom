"""Detect missing structural edges on hash-stable FILE symbols.

Role: decide when content-hash equality is not enough to skip re-ingest.
SoT: CONTAINS edges from FILE → function/method/class children.
Invariants: children without CONTAINS ⇒ repair; empty child set ⇒ no repair.
Allowed failure: store list errors propagate to caller.
Forbidden: treating edgeless FILE rows as up-to-date forever.
"""

from __future__ import annotations

from typing import Protocol

from .enums import RelType, SymbolKind
from .models import GraphEdge, GraphSymbol, Scope

_CHILD_KINDS = frozenset({SymbolKind.FUNCTION, SymbolKind.METHOD, SymbolKind.CLASS})


class _IntegrityStore(Protocol):
    def list_symbols_for_file(self, scope: Scope, file_path: str) -> list[GraphSymbol]: ...

    def list_edges(
        self,
        scope: Scope,
        *,
        rel_type: str | None = None,
        source_id: str | None = None,
        target_id: str | None = None,
    ) -> list[GraphEdge]: ...


def file_needs_contains_repair(
    store: _IntegrityStore,
    scope: Scope,
    *,
    file_id: str,
    file_path: str,
) -> bool:
    """True when the file has code children but no CONTAINS edges from FILE."""
    children = [
        s
        for s in store.list_symbols_for_file(scope, file_path)
        if s.kind in _CHILD_KINDS and s.id != file_id
    ]
    if not children:
        return False
    contains = store.list_edges(
        scope, rel_type=RelType.CONTAINS.value, source_id=file_id
    )
    return not contains

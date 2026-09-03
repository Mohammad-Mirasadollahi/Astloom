"""Detect missing structural edges on hash-stable FILE symbols.

Role: decide when content-hash equality is not enough to skip re-ingest.
SoT: CONTAINS edges from FILE → function/method/class children;
``metadata.ingest_complete`` for childless (constants-only) modules.
Invariants: children without CONTAINS ⇒ repair; empty child set ⇒ no repair;
incomplete FILE stubs (no children, no ingest_complete) stay unpublished.
Allowed failure: store list errors propagate to caller.
Forbidden: publishing edgeless FILE stubs before ingest completes.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol

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


def file_content_hash_publishable(
    *,
    digest: str,
    has_code_children: bool,
    metadata: Mapping[str, Any] | None = None,
) -> bool:
    """True when a FILE content hash may be published for unchanged-skip.

    Files with function/method/class children publish once those exist.
    Constants-only modules never grow those children — publish only after
    ``ingest_complete`` is stamped at successful ingest end (stubs written
    before a failed embed stay unpublished and/or are rolled back).
    """
    if not str(digest or "").strip():
        return False
    if has_code_children:
        return True
    return bool((metadata or {}).get("ingest_complete"))


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

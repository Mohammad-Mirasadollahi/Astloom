"""Persistence port for the Code-Knowledge Graph."""

from __future__ import annotations

from typing import Any, Protocol

from .models import GraphEdge, GraphSymbol, Scope


class Store(Protocol):
    def get_symbol(self, symbol_id: str, scope: Scope) -> GraphSymbol: ...
    def put_symbol(self, symbol: GraphSymbol) -> None: ...
    def delete_symbol(self, symbol_id: str, scope: Scope) -> None: ...
    def list_symbols(self, scope: Scope) -> list[GraphSymbol]: ...
    def list_symbols_for_file(self, scope: Scope, file_path: str) -> list[GraphSymbol]: ...
    def get_symbol_by_qualified_name(self, scope: Scope, qualified_name: str) -> GraphSymbol | None: ...
    def delete_file_edges(self, scope: Scope, file_path: str) -> None: ...
    def delete_edge(self, scope: Scope, edge_id: str) -> None: ...
    def put_edge(self, edge: GraphEdge) -> None: ...
    def list_edges(
        self,
        scope: Scope,
        *,
        rel_type: str | None = None,
        source_id: str | None = None,
        target_id: str | None = None,
    ) -> list[GraphEdge]: ...
    def begin_idempotency(self, scope: Scope, key: str, resource: str) -> str | None: ...
    def complete_idempotency(self, scope: Scope, key: str, resource: str, resource_id: str) -> None: ...
    def append_event(self, event: dict[str, Any]) -> None: ...
    def outbox(self) -> list[dict[str, Any]]: ...
    def wipe_scope(self, scope: Scope) -> dict[str, int]:
        """Delete all graph rows for the project scope. Returns deleted counts."""
        ...


def list_symbols_compact(store: Any, scope: Scope) -> list[GraphSymbol]:
    """Prefer index/lean listings so MCP/sync never dump living-doc bodies.

    Never calls ``list_symbols_full`` — that path is embed-heal only.
    """
    for name in ("list_symbols_index", "list_symbols_lean", "list_symbols"):
        fn = getattr(store, name, None)
        if callable(fn):
            return list(fn(scope))
    return []


def list_symbols_hydrated(store: Any, scope: Scope) -> list[GraphSymbol]:
    """Body + living-doc text for embedding refresh / rare hydrated scans."""
    for name in ("list_symbols_full", "list_symbols_lean"):
        fn = getattr(store, name, None)
        if callable(fn):
            return list(fn(scope))
    fn = getattr(store, "list_symbols", None)
    if callable(fn):
        return list(fn(scope))
    return []


def list_symbols_for_inventory(
    store: Any,
    scope: Scope,
    *,
    file_only: bool = False,
) -> tuple[list[GraphSymbol], dict[str, Any]]:
    """Inventory listing with automatic self-heal to FILE-only on failure.

    Returns ``(symbols, meta)`` where meta includes ``mode`` (``index``|``file``)
    and ``healed`` when the compact index path failed and FILE listing recovered.
    """
    if file_only:
        return list(list_file_symbols_compact(store, scope)), {
            "mode": "file",
            "healed": False,
        }
    try:
        return list(list_symbols_compact(store, scope)), {
            "mode": "index",
            "healed": False,
        }
    except Exception as exc:  # noqa: BLE001 — fail open so sync/inventory still runs
        return list(list_file_symbols_compact(store, scope)), {
            "mode": "file",
            "healed": True,
            "heal_reason": f"{type(exc).__name__}: {exc}"[:240],
        }


def list_file_symbols_for_paths(store: Any, scope: Scope, paths: list[str]) -> list[GraphSymbol]:
    """FILE symbols for the given relative paths (small-batch sync)."""
    fn = getattr(store, "list_file_symbols_for_paths", None)
    if callable(fn):
        return list(fn(scope, paths))
    # Fallback: filter a compact listing (tests / older stores).
    wanted = {str(p or "").replace("\\", "/").strip() for p in paths if str(p or "").strip()}
    if not wanted:
        return []
    from .enums import SymbolKind

    return [
        s
        for s in list_symbols_compact(store, scope)
        if s.kind == SymbolKind.FILE and s.file_path.replace("\\", "/") in wanted
    ]


def scope_has_symbols(store: Any, scope: Scope) -> bool:
    fn = getattr(store, "has_any_symbol", None)
    if callable(fn):
        return bool(fn(scope))
    return bool(list_symbols_compact(store, scope))


def list_file_symbols_compact(store: Any, scope: Scope) -> list[GraphSymbol]:
    """FILE nodes only for inventory/change detection under tool budgets."""
    fn = getattr(store, "list_file_symbols_index", None)
    if callable(fn):
        return list(fn(scope))
    from .enums import SymbolKind

    return [s for s in list_symbols_compact(store, scope) if s.kind == SymbolKind.FILE]

"""Shared symbol id resolution for MCP code-graph handlers."""

from __future__ import annotations

from typing import Any

from ..platform import PlatformBackends


def resolve_symbol_id(backends: PlatformBackends, scope: dict[str, str], arguments: dict[str, Any]) -> str:
    symbol_id = str(arguments.get("symbol_id") or "").strip()
    if symbol_id:
        return symbol_id
    qualified = str(arguments.get("qualified_name") or arguments.get("name") or "").strip()
    if not qualified:
        raise ValueError("symbol_id or qualified_name is required")
    graph_scope = backends.graph_scope(scope)
    store = backends.graph.store
    getter = getattr(store, "get_symbol_by_qualified_name", None)
    if callable(getter):
        hit = getter(graph_scope, qualified)
        if hit is not None:
            return hit.id
    from code_graph_service.domain.ports import list_symbols_compact

    matches: list[str] = []
    for symbol in list_symbols_compact(store, graph_scope):
        if symbol.qualified_name == qualified or symbol.name == qualified:
            matches.append(symbol.id)
    if not matches:
        raise ValueError(f"symbol not found for qualified_name/name={qualified!r}")
    return matches[0]

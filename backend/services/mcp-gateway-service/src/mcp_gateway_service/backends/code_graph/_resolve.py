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
    matches: list[str] = []
    for symbol in backends.graph.store.list_symbols(graph_scope):
        if symbol.qualified_name == qualified or symbol.name == qualified:
            matches.append(symbol.id)
    if not matches:
        raise ValueError(f"symbol not found for qualified_name/name={qualified!r}")
    if len(matches) > 1:
        # Prefer exact qualified_name match order already collected; return first stable id.
        return matches[0]
    return matches[0]


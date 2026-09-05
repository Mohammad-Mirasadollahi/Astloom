"""MCP symbol resolve must not dump the catalog when a store lookup misses."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from mcp_gateway_service.backends.code_graph._resolve import resolve_symbol_id


class _Store:
    def __init__(self) -> None:
        self.dumped = False

    def get_symbol_by_qualified_name(self, scope, qualified):
        _ = scope, qualified
        return None

    def list_symbols_index(self, scope):
        self.dumped = True
        raise AssertionError("compact catalog dump after qualified-name miss")

    def list_symbols_lean(self, scope):
        return self.list_symbols_index(scope)

    def list_symbols(self, scope):
        return self.list_symbols_index(scope)


def test_resolve_missing_qualified_name_does_not_dump_catalog():
    store = _Store()
    graph = SimpleNamespace(store=store)
    backends = SimpleNamespace(
        graph=graph,
        graph_scope=lambda scope: SimpleNamespace(**scope),
    )
    with pytest.raises(ValueError, match="symbol not found"):
        resolve_symbol_id(
            backends,
            {"tenant_id": "t", "workspace_id": "w", "project_id": "p"},
            {"qualified_name": f"missing_{uuid4().hex}"},
        )
    assert store.dumped is False

"""In-memory Code Graph Store for unit/contract tests (thread-safe).

Role: deterministic Store fake for parallel ingest tests.
Source of truth: in-process dicts under one ``RLock``.
Allowed: concurrent workers without ``lock_reads=True``.
Forbidden: production durability; unlocked shared dicts.
"""

from __future__ import annotations

import threading
from copy import deepcopy
from typing import Any, Callable, TypeVar

from .core import ConflictError, GraphEdge, GraphSymbol, NotFoundError, Scope

_T = TypeVar("_T")


class InMemoryStore:
    """Deterministic graph Store fake for unit and transport-contract tests."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._symbols: dict[str, GraphSymbol] = {}
        self._edges: dict[str, GraphEdge] = {}
        self._idempotency: dict[tuple[str, str, str], str] = {}
        self._events: list[dict[str, Any]] = []

    def _with_lock(self, fn: Callable[[], _T]) -> _T:
        with self._lock:
            return fn()

    @staticmethod
    def _scope_key(scope: Scope) -> str:
        return "|".join((scope.tenant_id, scope.workspace_id, scope.project_id, scope.project_group_id or ""))

    @staticmethod
    def _same_project(left: Scope, right: Scope) -> bool:
        return (left.tenant_id, left.workspace_id, left.project_id) == (
            right.tenant_id,
            right.workspace_id,
            right.project_id,
        )

    def get_symbol(self, symbol_id: str, scope: Scope) -> GraphSymbol:
        def _run() -> GraphSymbol:
            item = self._symbols.get(symbol_id)
            if item is None or not self._same_project(item.scope, scope):
                raise NotFoundError("symbol not found in project scope")
            return deepcopy(item)

        return self._with_lock(_run)

    def put_symbol(self, symbol: GraphSymbol) -> None:
        self._with_lock(lambda: self._symbols.__setitem__(symbol.id, deepcopy(symbol)))

    def delete_symbol(self, symbol_id: str, scope: Scope) -> None:
        def _run() -> None:
            item = self._symbols.get(symbol_id)
            if item is not None and self._same_project(item.scope, scope):
                del self._symbols[symbol_id]

        self._with_lock(_run)

    def delete_symbols(self, symbol_ids: list[str], scope: Scope) -> None:
        for symbol_id in symbol_ids:
            self.delete_symbol(symbol_id, scope)

    def list_symbols(self, scope: Scope) -> list[GraphSymbol]:
        def _run() -> list[GraphSymbol]:
            items = [item for item in self._symbols.values() if self._same_project(item.scope, scope)]
            return deepcopy(sorted(items, key=lambda item: (item.qualified_name, item.id)))

        return self._with_lock(_run)

    def list_symbols_lean(self, scope: Scope) -> list[GraphSymbol]:
        symbols = self.list_symbols(scope)
        for sym in symbols:
            sym.ai_documentation = ""
        return symbols

    def list_symbols_for_file(self, scope: Scope, file_path: str) -> list[GraphSymbol]:
        path = str(file_path or "").replace("\\", "/")

        def _run() -> list[GraphSymbol]:
            items = [
                item
                for item in self._symbols.values()
                if self._same_project(item.scope, scope)
                and str(item.file_path or "").replace("\\", "/") == path
            ]
            return deepcopy(sorted(items, key=lambda item: (item.qualified_name, item.id)))

        return self._with_lock(_run)

    def get_symbol_by_qualified_name(self, scope: Scope, qualified_name: str) -> GraphSymbol | None:
        def _run() -> GraphSymbol | None:
            for item in self._symbols.values():
                if self._same_project(item.scope, scope) and item.qualified_name == qualified_name:
                    return deepcopy(item)
            return None

        return self._with_lock(_run)

    def delete_file_edges(self, scope: Scope, file_path: str) -> None:
        def _run() -> None:
            drop = [
                edge_id
                for edge_id, edge in self._edges.items()
                if self._same_project(edge.scope, scope) and edge.metadata.get("file_path") == file_path
            ]
            for edge_id in drop:
                del self._edges[edge_id]

        self._with_lock(_run)

    def delete_edge(self, scope: Scope, edge_id: str) -> None:
        def _run() -> None:
            edge = self._edges.get(edge_id)
            if edge is not None and self._same_project(edge.scope, scope):
                del self._edges[edge_id]

        self._with_lock(_run)

    def delete_edges(self, scope: Scope, edge_ids: list[str]) -> None:
        def _run() -> None:
            for edge_id in edge_ids:
                edge = self._edges.get(edge_id)
                if edge is not None and self._same_project(edge.scope, scope):
                    del self._edges[edge_id]

        self._with_lock(_run)

    def put_edge(self, edge: GraphEdge) -> None:
        self._with_lock(lambda: self._edges.__setitem__(edge.id, deepcopy(edge)))

    def put_edges(self, edges: list[GraphEdge]) -> None:
        def _run() -> None:
            for edge in edges:
                self._edges[edge.id] = deepcopy(edge)

        self._with_lock(_run)

    def list_edges(
        self,
        scope: Scope,
        *,
        rel_type: str | None = None,
        source_id: str | None = None,
        target_id: str | None = None,
    ) -> list[GraphEdge]:
        def _run() -> list[GraphEdge]:
            items = [
                item
                for item in self._edges.values()
                if self._same_project(item.scope, scope)
                and (rel_type is None or item.rel_type == rel_type)
                and (source_id is None or item.source_id == source_id)
                and (target_id is None or item.target_id == target_id)
            ]
            return deepcopy(sorted(items, key=lambda item: item.id))

        return self._with_lock(_run)

    def begin_idempotency(self, scope: Scope, key: str, resource: str) -> str | None:
        def _run() -> str | None:
            packed = (self._scope_key(scope), key, resource)
            if packed in self._idempotency:
                return self._idempotency[packed]
            return None

        return self._with_lock(_run)

    def complete_idempotency(self, scope: Scope, key: str, resource: str, resource_id: str) -> None:
        def _run() -> None:
            packed = (self._scope_key(scope), key, resource)
            if packed in self._idempotency and self._idempotency[packed] != resource_id:
                raise ConflictError("idempotency key already bound to another resource")
            self._idempotency[packed] = resource_id

        self._with_lock(_run)

    def append_event(self, event: dict[str, Any]) -> None:
        self._with_lock(lambda: self._events.append(deepcopy(event)))

    def outbox(self) -> list[dict[str, Any]]:
        return self._with_lock(lambda: deepcopy(self._events))

    def wipe_scope(self, scope: Scope) -> dict[str, int]:
        def _run() -> dict[str, int]:
            symbol_ids = [
                sid for sid, item in self._symbols.items() if self._same_project(item.scope, scope)
            ]
            edge_ids = [eid for eid, item in self._edges.items() if self._same_project(item.scope, scope)]
            for sid in symbol_ids:
                del self._symbols[sid]
            for eid in edge_ids:
                del self._edges[eid]
            scope_key = self._scope_key(scope)
            drop_keys = [key for key in self._idempotency if key[0] == scope_key]
            for key in drop_keys:
                del self._idempotency[key]
            return {
                "symbols": len(symbol_ids),
                "edges": len(edge_ids),
                "idempotency": len(drop_keys),
            }

        return self._with_lock(_run)

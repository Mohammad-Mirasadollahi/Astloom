"""Persistence ports for this service (Phase C DI hygiene).

Role: Store protocol for common-context items and events.
Source of truth: approved CommonItems in the store; concrete adapters in postgres_store/testing.
Allowed vs forbidden: construct adapters only from bootstrap.py — not from API handlers or domain helpers.
"""

from __future__ import annotations

from typing import Any, Protocol

from .scope import Scope


class Store(Protocol):
    def begin_idempotency(self, scope: Scope, key: str, resource: str) -> str | None: ...
    def complete_idempotency(self, scope: Scope, key: str, resource: str, resource_id: str) -> None: ...
    def append_event(self, event: dict[str, Any]) -> None: ...
    def put_item(self, item: dict[str, Any]) -> None: ...
    def get_item(self, item_id: str, scope: Scope) -> dict[str, Any]: ...
    def list_items(self, scope: Scope, status: str | None = None) -> list[dict[str, Any]]: ...


__all__ = ["Store"]

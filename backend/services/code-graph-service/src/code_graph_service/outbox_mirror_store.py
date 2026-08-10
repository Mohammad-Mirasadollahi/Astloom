"""Store wrapper that mirrors outbox events to PostgreSQL for the relay worker."""

from __future__ import annotations

from typing import Any

from .domain.ports import Store
from .postgres_side import PostgresOutboxMirror


class OutboxMirrorStore:
    """Delegates the Store port and dual-writes append_event to Postgres outbox."""

    def __init__(self, store: Store, mirror: PostgresOutboxMirror) -> None:
        self._store = store
        self._mirror = mirror

    def close(self) -> None:
        close = getattr(self._store, "close", None)
        if callable(close):
            close()
        self._mirror.close()

    def reset_connections(self) -> None:
        """Release PostgreSQL worker connections without closing the graph driver."""
        reset = getattr(self._store, "reset_connections", None)
        if callable(reset):
            reset()
        self._mirror.reset_connections()

    def append_event(self, event: dict[str, Any]) -> None:
        self._store.append_event(event)
        self._mirror.append_event(event)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._store, name)

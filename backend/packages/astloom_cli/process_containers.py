"""Process-scoped service containers for the Astloom CLI (Phase D DI).

Long-running / repeated CLI commands must reuse one composition root per process
instead of rebuilding Neo4j/Postgres pools on every helper call.
"""

from __future__ import annotations

from typing import Any

# Backend key → constructed service / container payload.
_GRAPH: dict[str, Any] = {}
_DOCS_SYNC: dict[str, Any] = {}


def clear_process_containers() -> None:
    """Test helper: drop cached CLI composition roots."""
    for key, value in list(_GRAPH.items()):
        closer = getattr(value, "close", None)
        if callable(closer):
            try:
                closer()
            except Exception:  # noqa: BLE001
                pass
        _GRAPH.pop(key, None)
    for key, value in list(_DOCS_SYNC.items()):
        service = value
        store = getattr(service, "store", None)
        closer = getattr(store, "close", None) if store is not None else None
        if callable(closer):
            try:
                closer()
            except Exception:  # noqa: BLE001
                pass
        _DOCS_SYNC.pop(key, None)


def get_graph_service(*, backend: str, factory):
    """Return a cached code-graph service for ``backend`` (``neo4j`` / ``memory``)."""
    key = backend.strip().lower() or "memory"
    existing = _GRAPH.get(key)
    if existing is not None:
        # ServiceContainer has .graph; bare service is returned as-is.
        return getattr(existing, "graph", existing)
    built = factory()
    _GRAPH[key] = built
    return getattr(built, "graph", built)


def get_docs_sync_service(*, backend: str, factory):
    """Return a cached docs-sync service for ``backend`` (``postgres`` / ``memory``)."""
    key = backend.strip().lower() or "memory"
    existing = _DOCS_SYNC.get(key)
    if existing is not None:
        return getattr(existing, "service", existing)
    built = factory()
    _DOCS_SYNC[key] = built
    return getattr(built, "service", built)

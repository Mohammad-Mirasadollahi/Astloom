"""Build in-process service stores for the MCP gateway (memory, PostgreSQL, or Neo4j graph)."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Literal, Mapping

StoreMode = Literal["memory", "postgres"]
GraphMode = Literal["memory", "postgres", "neo4j"]

logger = logging.getLogger(__name__)

SERVICE_URL_ENV = {
    "core": "ASTLOOM_CORE_DATA_DATABASE_URL",
    "memory": "ASTLOOM_MEMORY_DATABASE_URL",
    "graph": "ASTLOOM_CODE_GRAPH_DATABASE_URL",
    "docs": "ASTLOOM_DOCS_SYNC_DATABASE_URL",
    "common_context": "ASTLOOM_COMMON_CONTEXT_DATABASE_URL",
}


@dataclass(frozen=True)
class StoreBundle:
    mode: StoreMode
    graph_mode: GraphMode
    core: Any
    memory: Any
    graph: Any
    docs: Any
    common_context: Any
    database_url: str | None = None
    # When graph_mode == neo4j, graph is unused; graph_service is the live facade.
    graph_service: Any | None = None

    def close(self) -> None:
        if self.graph_service is not None:
            closer = getattr(self.graph_service, "close", None)
            if callable(closer):
                closer()
        for store in (self.core, self.memory, self.graph, self.docs, self.common_context):
            if store is None:
                continue
            closer = getattr(store, "close", None)
            if callable(closer):
                closer()


def resolve_store_mode(environ: Mapping[str, str] | None = None) -> StoreMode:
    env = environ if environ is not None else os.environ
    explicit = str(env.get("ASTLOOM_MCP_STORE_MODE") or "").strip().lower()
    if explicit in {"memory", "postgres"}:
        return explicit  # type: ignore[return-value]
    # Only the shared platform URL implies postgres for all MCP companion stores.
    # A lone ASTLOOM_CODE_GRAPH_DATABASE_URL must not force core/memory onto postgres.
    if str(env.get("ASTLOOM_DATABASE_URL") or "").strip():
        return "postgres"
    return "memory"


def resolve_graph_mode(environ: Mapping[str, str] | None = None) -> GraphMode:
    """Select code-graph backend for MCP (independent of other service store mode).

    Priority:
    1. ASTLOOM_MCP_GRAPH_MODE = memory|postgres|neo4j
    2. auto: Neo4j when password is set and CODE_GRAPH_STORE is neo4j (default)
    3. else follow ASTLOOM_MCP_STORE_MODE / postgres URL detection
    """
    env = environ if environ is not None else os.environ
    explicit = str(env.get("ASTLOOM_MCP_GRAPH_MODE") or "").strip().lower()
    if explicit in {"memory", "postgres", "neo4j"}:
        return explicit  # type: ignore[return-value]

    store_backend = str(env.get("ASTLOOM_CODE_GRAPH_STORE", "neo4j")).strip().lower() or "neo4j"
    neo4j_password = str(env.get("ASTLOOM_NEO4J_PASSWORD") or "").strip()
    placeholder_passwords = {
        "",
        "replace-with-a-local-secret",
        "changeme",
        "password",
        "neo4j",
    }
    if store_backend == "neo4j" and neo4j_password and neo4j_password not in placeholder_passwords:
        return "neo4j"
    if store_backend == "postgres":
        return "postgres"
    return resolve_store_mode(env)


def _url_for(service: str, env: Mapping[str, str]) -> str:
    specific = str(env.get(SERVICE_URL_ENV[service]) or "").strip()
    if specific:
        return specific
    shared = str(env.get("ASTLOOM_DATABASE_URL") or "").strip()
    if shared:
        return shared
    raise ValueError(
        f"postgres store mode requires ASTLOOM_DATABASE_URL or {SERVICE_URL_ENV[service]}"
    )


def _env_dict(environ: Mapping[str, str] | None) -> dict[str, str]:
    if environ is None:
        return dict(os.environ)
    return {str(k): str(v) for k, v in environ.items()}


def _memory_companion_stores() -> tuple[Any, Any, Any, Any]:
    from common_context_service.testing import InMemoryStore as CommonContextStore
    from core_data_service.testing import InMemoryStore as CoreStore
    from docs_sync_service.testing import InMemoryStore as DocsStore
    from memory_service.testing import InMemoryStore as MemoryStore

    return CoreStore(), MemoryStore(), DocsStore(), CommonContextStore()


def _memory_graph_store() -> Any:
    from code_graph_service.testing import InMemoryStore as GraphStore

    return GraphStore()


def build_stores(environ: Mapping[str, str] | None = None) -> StoreBundle:
    env = _env_dict(environ)
    mode = resolve_store_mode(env)
    graph_mode = resolve_graph_mode(env)

    if mode == "memory":
        core, memory, docs, common_context = _memory_companion_stores()
        database_url = None
    else:
        try:
            from common_context_service.postgres_store import PostgresStore as CommonContextStore
            from core_data_service.postgres_store import PostgresStore as CoreStore
            from docs_sync_service.postgres_store import PostgresStore as DocsStore
            from memory_service.postgres_store import PostgresStore as MemoryStore

            urls = {name: _url_for(name, env) for name in SERVICE_URL_ENV}
            core = CoreStore(urls["core"])
            memory = MemoryStore(urls["memory"])
            docs = DocsStore(urls["docs"])
            common_context = CommonContextStore(urls["common_context"])
            database_url = urls["core"]
        except Exception as exc:
            logger.exception(
                "MCP postgres stores unavailable (%s); falling back to in-memory companion stores",
                exc,
            )
            mode = "memory"
            core, memory, docs, common_context = _memory_companion_stores()
            database_url = None

    graph_service = None
    graph_store: Any = None

    if graph_mode == "neo4j":
        try:
            from code_graph_service.bootstrap import Settings, build_container

            graph_service = build_container(Settings.from_environment(env)).graph
            # Placeholder unused store so close() loops stay simple; real close via graph_service.
            graph_store = _memory_graph_store()
        except Exception as exc:
            logger.exception(
                "MCP Neo4j graph unavailable (%s); falling back to in-memory graph "
                "(start Compose neo4j or set ASTLOOM_MCP_GRAPH_MODE=memory)",
                exc,
            )
            graph_mode = "memory"
            graph_service = None
            graph_store = _memory_graph_store()
    elif graph_mode == "postgres":
        try:
            from code_graph_service.postgres_store import PostgresStore as GraphStore

            graph_store = GraphStore(_url_for("graph", env))
        except Exception as exc:
            logger.exception(
                "MCP postgres graph unavailable (%s); falling back to in-memory graph",
                exc,
            )
            graph_mode = "memory"
            graph_store = _memory_graph_store()
    else:
        graph_store = _memory_graph_store()

    return StoreBundle(
        mode=mode,
        graph_mode=graph_mode,
        core=core,
        memory=memory,
        graph=graph_store,
        docs=docs,
        common_context=common_context,
        database_url=database_url,
        graph_service=graph_service,
    )


@dataclass(frozen=True)
class McpServiceContainer:
    """Composition-root output for the MCP gateway process."""

    stores: StoreBundle
    backends: Any

    def close(self) -> None:
        closer = getattr(self.backends, "close", None)
        if callable(closer):
            closer()
        else:
            self.stores.close()


def build_container(environ: Mapping[str, str] | None = None) -> McpServiceContainer:
    """MCP composition root: stores + platform backends."""
    from .backends.platform import PlatformBackends

    stores = build_stores(environ)
    backends = PlatformBackends(stores)
    return McpServiceContainer(stores=stores, backends=backends)

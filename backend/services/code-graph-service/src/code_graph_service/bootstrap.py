from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

from .core import CodeGraphService
from .llm_wiring import LlmBackedDocGenerator, build_embeddings
from .local_embeddings import embedding_settings_from_env
from .neo4j_store import Neo4jStore
from .outbox_mirror_store import OutboxMirrorStore
from .postgres_side import PostgresEmbeddingIndex, PostgresOutboxMirror
from .postgres_store import PostgresStore


@dataclass(frozen=True)
class Settings:
    store_backend: str
    database_url: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    neo4j_database: str
    neo4j_gds_enabled: bool = True
    neo4j_gds_concurrency: int = 4

    @classmethod
    def from_environment(cls, environ: dict[str, str] | None = None) -> "Settings":
        # Neo4j is the default structural store (GAP-011 closed). Postgres remains
        # available via ASTLOOM_CODE_GRAPH_STORE=postgres for rollback / parity.
        # ASTLOOM_CODE_GRAPH_DATABASE_URL enables pgvector embeddings + outbox mirror.
        env = environ if environ is not None else os.environ
        store_backend = str(env.get("ASTLOOM_CODE_GRAPH_STORE", "neo4j")).strip().lower() or "neo4j"
        if store_backend not in {"postgres", "neo4j"}:
            raise RuntimeError("ASTLOOM_CODE_GRAPH_STORE must be 'postgres' or 'neo4j'")

        # Prefer graph-specific URL; fall back to shared MCP/CLI DATABASE_URL so
        # Neo4j + pgvector works when only ASTLOOM_DATABASE_URL is in mcp.json.
        database_url = str(env.get("ASTLOOM_CODE_GRAPH_DATABASE_URL", "")).strip()
        if not database_url:
            database_url = str(env.get("ASTLOOM_DATABASE_URL", "")).strip()
        neo4j_uri = str(env.get("ASTLOOM_NEO4J_URI", "bolt://127.0.0.1:32287")).strip() or "bolt://127.0.0.1:32287"
        neo4j_user = str(env.get("ASTLOOM_NEO4J_USER", "neo4j")).strip() or "neo4j"
        neo4j_password = str(env.get("ASTLOOM_NEO4J_PASSWORD", "")).strip()
        neo4j_database = str(env.get("ASTLOOM_NEO4J_DATABASE", "neo4j")).strip() or "neo4j"
        neo4j_gds_enabled = _env_flag(env.get("ASTLOOM_NEO4J_GDS_ENABLED"), default=True)
        neo4j_gds_concurrency = _gds_concurrency(env.get("ASTLOOM_NEO4J_GDS_CONCURRENCY"))

        if store_backend == "postgres":
            if not database_url:
                raise RuntimeError("ASTLOOM_CODE_GRAPH_DATABASE_URL is required for postgres store")
            if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
                raise RuntimeError("ASTLOOM_CODE_GRAPH_DATABASE_URL must use PostgreSQL")
        else:
            if not neo4j_uri:
                raise RuntimeError("ASTLOOM_NEO4J_URI is required for neo4j store")
            if not neo4j_password:
                raise RuntimeError("ASTLOOM_NEO4J_PASSWORD is required for neo4j store")
            if database_url and not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
                raise RuntimeError("ASTLOOM_CODE_GRAPH_DATABASE_URL must use PostgreSQL when set")

        return cls(
            store_backend=store_backend,
            database_url=database_url,
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
            neo4j_database=neo4j_database,
            neo4j_gds_enabled=neo4j_gds_enabled,
            neo4j_gds_concurrency=neo4j_gds_concurrency,
        )


@dataclass(frozen=True)
class ServiceContainer:
    """Process-scoped composition root output for code-graph HTTP/CLI."""

    graph: CodeGraphService
    settings: Settings | None = None

    def close(self) -> None:
        self.graph.close()


def _env_flag(raw: str | None, *, default: bool) -> bool:
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


def _gds_concurrency(raw: str | None) -> int:
    """GDS Community Edition caps concurrency at 4 cores — never exceed."""
    try:
        value = int(str(raw).strip() or "4")
    except ValueError:
        value = 4
    return max(1, min(value, 4))


def build_store(settings: Settings, *, max_connections: int | None = None):
    if settings.store_backend == "neo4j":
        store = Neo4jStore(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
            database=settings.neo4j_database,
            gds_enabled=settings.neo4j_gds_enabled,
            gds_concurrency=settings.neo4j_gds_concurrency,
        )
        if settings.database_url:
            return OutboxMirrorStore(
                store,
                PostgresOutboxMirror(settings.database_url, max_connections=max_connections),
            )
        return store
    return PostgresStore(settings.database_url, max_connections=max_connections)


def build_embedding_index(
    settings: Settings,
    *,
    max_connections: int | None = None,
) -> PostgresEmbeddingIndex | None:
    if not settings.database_url:
        return None
    dims = int(embedding_settings_from_env()["dims"])
    return PostgresEmbeddingIndex(
        settings.database_url,
        dims=dims,
        ensure_schema=True,
        max_connections=max_connections,
    )


def build_vector_index(dims: int, *, database_url: str | None = None) -> tuple[Any, Any]:
    """Optional TurboVec replica + entity id map; (None, None) when off/unavailable."""
    try:
        from vector_index import try_build_accelerator
    except ImportError:
        return None, None
    return try_build_accelerator(
        dim=dims,
        database_url=database_url,
        id_map_table="code_graph.embedding_id_map",
    )


def build_llm_gateway():
    """Construct the shared LiteLLM gateway from environment."""
    from llm_gateway import LiteLlmGateway, LlmGatewaySettings

    return LiteLlmGateway(LlmGatewaySettings.from_environment())


def build_container(settings: Settings | None = None) -> ServiceContainer:
    """Composition root: bind adapters and return a frozen service container."""
    from .llm_wiring import maybe_preload_embeddings
    from .locked_store import LockedEmbeddings, LockedStore, apply_sync_compute_limits

    resolved = settings or Settings.from_environment()
    cpu_plan = apply_sync_compute_limits()
    gateway = build_llm_gateway()
    embeddings = build_embeddings(gateway, settings=gateway.settings)
    if embeddings.local is not None:
        embeddings.local = LockedEmbeddings(
            embeddings.local,
            max_concurrency=cpu_plan.embed_concurrency,
        )
    maybe_preload_embeddings(embeddings)
    store_conc = int(cpu_plan.store_concurrency)
    # Pool size is auto from Postgres capacity (or ASTLOOM_PG_POOL_MAX); do not
    # clamp it to store_concurrency — that would invent a second bottleneck.
    emb_index = build_embedding_index(resolved)
    store = build_store(resolved)
    # Neo4j / store mutations still use concurrent store slots.
    if emb_index is not None:
        emb_index = LockedStore(
            emb_index,
            lock_reads=False,
            max_concurrent=store_conc,
        )
    dims = int(getattr(embeddings, "dims", 0) or embedding_settings_from_env()["dims"])
    vector_index, entity_id_map = build_vector_index(dims, database_url=resolved.database_url)
    graph = CodeGraphService(
        LockedStore(store, lock_reads=False, max_concurrent=store_conc),
        docs=LlmBackedDocGenerator(gateway, settings=gateway.settings),
        embeddings=embeddings,
        embedding_index=emb_index,
        llm=gateway,
        vector_index=vector_index,
        entity_id_map=entity_id_map,
    )
    return ServiceContainer(graph=graph, settings=resolved)


def build_service(settings: Settings | None = None) -> CodeGraphService:
    """Compatibility wrapper — prefer ``build_container`` for new wiring."""
    return build_container(settings).graph


def shutdown_container(container: ServiceContainer | None) -> None:
    if container is not None:
        container.close()

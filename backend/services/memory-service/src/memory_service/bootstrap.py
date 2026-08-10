from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

from .core import MemoryService
from .local_embedder import LocalHashEmbedder
from .postgres_embeddings import PostgresMemoryEmbeddingStore
from .postgres_store import PostgresStore


@dataclass(frozen=True)
class Settings:
    database_url: str

    @classmethod
    def from_environment(cls) -> "Settings":
        database_url = os.environ.get("ASTLOOM_MEMORY_SERVICE_DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("ASTLOOM_MEMORY_SERVICE_DATABASE_URL is required")
        if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise RuntimeError("ASTLOOM_MEMORY_SERVICE_DATABASE_URL must use PostgreSQL")
        return cls(database_url=database_url)


@dataclass(frozen=True)
class ServiceContainer:
    """Process-scoped composition root output."""

    service: MemoryService
    settings: Settings | None = None

    def close(self) -> None:
        store = getattr(self.service, "store", None)
        closer = getattr(store, "close", None) if store is not None else None
        if callable(closer):
            closer()
        emb = getattr(self.service, "embedding_store", None)
        emb_close = getattr(emb, "close", None) if emb is not None else None
        if callable(emb_close):
            emb_close()
        id_map = getattr(self.service, "entity_id_map", None)
        id_close = getattr(id_map, "close", None) if id_map is not None else None
        if callable(id_close):
            id_close()


def _embedding_dims() -> int:
    raw = os.environ.get("ASTLOOM_EMBEDDING_DIMS", "1024").strip() or "1024"
    try:
        return int(raw)
    except ValueError:
        return 1024


def build_embedder(dims: int | None = None) -> LocalHashEmbedder:
    """Default offline embedder; swap at composition root for LiteLLM/BGE later."""
    return LocalHashEmbedder(dims=dims if dims is not None else _embedding_dims())


def build_embedding_store(
    settings: Settings,
    *,
    dims: int | None = None,
) -> PostgresMemoryEmbeddingStore:
    return PostgresMemoryEmbeddingStore(
        settings.database_url,
        dims=dims if dims is not None else _embedding_dims(),
        ensure_schema=True,
    )


def build_vector_index(
    dims: int | None = None,
    *,
    database_url: str | None = None,
) -> tuple[Any, Any]:
    """Optional TurboVec replica + id map; only useful when embeddings SoR is also bound."""
    try:
        from vector_index import try_build_accelerator
    except ImportError:
        return None, None
    return try_build_accelerator(
        dim=dims if dims is not None else _embedding_dims(),
        database_url=database_url,
        id_map_table="memory.embedding_id_map",
    )


def build_container(settings: Settings | None = None) -> ServiceContainer:
    """Composition root: bind adapters and return a frozen service container."""
    resolved = settings or Settings.from_environment()
    dims = _embedding_dims()
    embedding_store = build_embedding_store(resolved, dims=dims)
    embedder = build_embedder(dims)
    vector_index, entity_id_map = build_vector_index(dims, database_url=resolved.database_url)
    service = MemoryService(
        PostgresStore(resolved.database_url),
        embedding_store=embedding_store,
        embedder=embedder,
        vector_index=vector_index,
        entity_id_map=entity_id_map,
    )
    return ServiceContainer(service=service, settings=resolved)


def build_service(settings: Settings | None = None) -> MemoryService:
    """Compatibility wrapper — prefer ``build_container`` for new wiring."""
    return build_container(settings).service


def shutdown_container(container: ServiceContainer | None) -> None:
    if container is not None:
        container.close()

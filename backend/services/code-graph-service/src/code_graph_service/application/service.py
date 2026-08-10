"""CodeGraphService facade — composes ingest, query, and generation use cases."""

from __future__ import annotations

import threading
from typing import Any

from ..domain.documentation import HeuristicDocGenerator
from ..domain.embeddings import LocalEmbeddingStub
from ..domain.freshness import FreshnessState
from ..domain.languages import assert_required_languages_supported
from ..domain.ports import Store
from ..postgres_side import EmbeddingIndex
from .edit_session import EditSessionFactory, EditSessionUseCases
from .embedding_refresh import EmbeddingRefreshMixin
from .generation import GenerationUseCases
from .ingest import IngestUseCases
from .intelligence import IntelligenceUseCases
from .queries import QueryUseCases


class CodeGraphService(
    IngestUseCases,
    QueryUseCases,
    GenerationUseCases,
    IntelligenceUseCases,
    EditSessionUseCases,
    EmbeddingRefreshMixin,
):
    """Application service entrypoint for the Code-Knowledge Graph."""

    def __init__(
        self,
        store: Store,
        docs: HeuristicDocGenerator | None = None,
        embeddings: LocalEmbeddingStub | None = None,
        embedding_index: EmbeddingIndex | None = None,
        llm: Any | None = None,
        edit_session_factory: EditSessionFactory | None = None,
        vector_index: Any | None = None,
        entity_id_map: Any | None = None,
    ) -> None:
        assert_required_languages_supported()
        self.store = store
        self.docs = docs or HeuristicDocGenerator()
        self.embeddings = embeddings or LocalEmbeddingStub()
        self.embedding_index = embedding_index
        self.llm = llm
        self.freshness = FreshnessState()
        self._edge_batches = threading.local()
        self.edit_session_factory = edit_session_factory
        # Optional Stage-2 ANN replica (VectorIndexPort); None → pgvector-only path.
        self.vector_index = vector_index
        self.entity_id_map = entity_id_map

    def close(self) -> None:
        closed: set[int] = set()
        for resource in (
            self.store,
            self.embedding_index,
            self.vector_index,
            self.entity_id_map,
        ):
            if resource is None or id(resource) in closed:
                continue
            closed.add(id(resource))
            closer = getattr(resource, "close", None)
            if callable(closer):
                closer()

    def reset_database_connections(self) -> None:
        """Release completed worker pools while keeping the service reusable."""
        for resource in (self.store, self.embedding_index):
            if resource is None:
                continue
            reset = getattr(resource, "reset_connections", None)
            if callable(reset):
                reset()

    def llm_providers(self) -> list[dict[str, Any]]:
        if self.llm is None:
            return []
        return [p.to_dict() for p in self.llm.list_providers()]

    def llm_config(self) -> dict[str, Any]:
        if self.llm is None:
            return {"enabled": False, "configured": False}
        from llm_gateway.routing import (
            docs_generation_enabled,
            embeddings_generation_enabled,
            resolve_route,
        )

        settings = getattr(self.llm, "settings", None)
        default_model = getattr(settings, "default_model", "") if settings else ""
        payload = self.llm.settings_public()
        payload.update(
            {
                "docs_enabled": docs_generation_enabled(),
                "embeddings_enabled": embeddings_generation_enabled(),
                "route_docs": resolve_route("docs.generate", default_model=default_model).to_dict(),
                "route_embed": resolve_route("embed.symbol", default_model=default_model).to_dict(),
            }
        )
        return payload

    def llm_sessions_snapshot(self) -> dict[str, Any]:
        """Process-local RPM session registry snapshot (in-flight + short history)."""
        if self.llm is None:
            return {
                "rpm": 0,
                "inflight_cap": 0,
                "starts_in_window": 0,
                "inflight_count": 0,
                "inflight": [],
                "history": [],
                "configured": False,
            }
        snap_fn = getattr(self.llm, "rpm_sessions_snapshot", None)
        if not callable(snap_fn):
            return {
                "rpm": 0,
                "inflight_cap": 0,
                "starts_in_window": 0,
                "inflight_count": 0,
                "inflight": [],
                "history": [],
                "configured": False,
            }
        payload = dict(snap_fn())
        payload["configured"] = True
        return payload

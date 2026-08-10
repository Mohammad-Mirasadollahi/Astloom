"""MemoryService facade composing domain command mixins."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from .batches import BatchCommands
from .embeddings import EmbeddingCommands
from .errors import ValidationError
from .helpers import now
from .items import MemoryItemCommands
from .models import Scope, WeightProfile
from .protocols import Store
from .questions import QuestionCommands
from .retrieval import RetrievalCommands


class MemoryService(
    EmbeddingCommands,
    MemoryItemCommands,
    RetrievalCommands,
    QuestionCommands,
    BatchCommands,
):
    def __init__(
        self,
        store: Store,
        profile: WeightProfile | None = None,
        *,
        embedding_store: Any | None = None,
        embedder: Any | None = None,
        vector_index: Any | None = None,
        entity_id_map: Any | None = None,
    ):
        self.store = store
        self.profile = profile or WeightProfile.default()
        self.embedding_store = embedding_store
        self.embedder = embedder
        self.vector_index = vector_index
        self.entity_id_map = entity_id_map

    def _require_key(self, key: str) -> None:
        if not key:
            raise ValidationError("Idempotency-Key header is required")

    def emit(
        self,
        event_type: str,
        payload: dict[str, Any],
        scope: Scope,
        actor: str,
        correlation_id: str,
        key: str,
        causation_id: str,
        evidence_refs: list[str],
    ) -> None:
        self.store.event(
            {
                "event_id": str(uuid4()),
                "event_type": event_type,
                "event_version": 1,
                "occurred_at": now(),
                "producer": "memory-service",
                "tenant_id": scope.tenant_id,
                "workspace_id": scope.workspace_id,
                "project_id": scope.project_id,
                "project_group_id": scope.project_group_id,
                "actor_ref": actor,
                "correlation_id": correlation_id,
                "causation_id": causation_id,
                "idempotency_key": key,
                "payload": payload,
                "evidence_refs": evidence_refs,
            }
        )

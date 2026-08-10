"""Embedding index / dense retrieve commands."""

from __future__ import annotations

from typing import Any

from .enums import MemoryKind, MemoryState
from .errors import NotFoundError, ValidationError
from .models import MemoryItem, Scope


class EmbeddingCommands:
    def index_memory_embedding(self, scope: Scope, memory_id: str) -> dict[str, Any]:
        """Persist SoR embedding for one memory item (Stage-1), then sync ANN replica."""
        if self.embedding_store is None or self.embedder is None:
            raise ValidationError("embedding_store and embedder are required")
        from ..domain.embeddings_store import MemoryEmbeddingRow

        item = self.store.get_memory(memory_id, scope)
        text = f"{item.title} {item.body}".strip()
        result = self.embedder.embed(text)
        vector = list(getattr(result, "vector", result))
        model = str(getattr(result, "model", getattr(self.embedder, "model", "unknown")))
        dims = int(getattr(result, "dims", len(vector)))
        row = MemoryEmbeddingRow(
            memory_id=memory_id,
            tenant_id=scope.tenant_id,
            workspace_id=scope.workspace_id,
            project_id=scope.project_id,
            vector=vector,
            model=model,
            dims=dims,
            kind=item.kind.value,
        )
        self.embedding_store.upsert(row)
        self._sync_vector_replica_upsert(memory_id, vector)
        return {"memory_id": memory_id, "model": model, "dims": dims}

    def delete_memory_embedding(self, scope: Scope, memory_id: str) -> dict[str, Any]:
        """Delete SoR embedding then remove ANN replica id (fail-open on replica)."""
        if self.embedding_store is None:
            raise ValidationError("embedding_store is required")
        deleter = getattr(self.embedding_store, "delete", None)
        if callable(deleter):
            deleter(scope, memory_id)
        self._sync_vector_replica_delete(memory_id)
        return {"memory_id": memory_id, "deleted": True}

    def retrieve_by_embedding(
        self,
        scope: Scope,
        query: str,
        *,
        top_k: int = 5,
    ) -> dict[str, Any]:
        """Stage-1 semantic retrieve over memory embeddings; optional Stage-2 ANN."""
        if self.embedding_store is None or self.embedder is None:
            raise ValidationError("embedding_store and embedder are required")
        from ..domain.embeddings_store import stage1_retrieve

        if not query.strip():
            raise ValidationError("query is required")
        result = self.embedder.embed(query, is_query=True) if hasattr(self.embedder, "embed") else None
        if result is None:
            raise ValidationError("embedder.embed is required")
        vector = list(getattr(result, "vector", result))
        retrieved = stage1_retrieve(
            self.embedding_store,
            scope,
            vector,
            top_k=top_k,
            vector_index=self.vector_index,
            entity_id_map=self.entity_id_map,
        )
        enriched = []
        for hit in retrieved.hits:
            try:
                item = self.store.get_memory(hit["memory_id"], scope)
                enriched.append({**hit, "memory": item.public()})
            except NotFoundError:
                continue
        payload = retrieved.public()
        payload["hits"] = enriched
        return payload

    def _sync_vector_replica_upsert(self, memory_id: str, vector: list[float]) -> None:
        if self.vector_index is None or self.entity_id_map is None:
            return
        try:
            import numpy as np

            uid = self.entity_id_map.get_or_assign(memory_id)
            self.vector_index.upsert([uid], np.asarray([vector], dtype=np.float32))
        except Exception:  # noqa: BLE001 — fail-open to SoR
            return

    def _sync_vector_replica_delete(self, memory_id: str) -> None:
        if self.vector_index is None or self.entity_id_map is None:
            return
        try:
            uid = self.entity_id_map.to_uint64(memory_id)
            if uid is None:
                return
            self.vector_index.remove([uid])
            remover = getattr(self.entity_id_map, "remove", None)
            if callable(remover):
                remover(memory_id)
        except Exception:  # noqa: BLE001 — fail-open to SoR
            return

    def _maybe_upsert_embedding(self, scope: Scope, item: MemoryItem) -> None:
        if self.embedding_store is None or self.embedder is None:
            return
        if item.kind == MemoryKind.RESTRICTED or item.state == MemoryState.RESTRICTED:
            return
        try:
            self.index_memory_embedding(scope, item.id)
        except Exception:  # noqa: BLE001 — create path stays durable without embeddings
            return

    def _embedding_hits(
        self,
        scope: Scope,
        query: str,
        candidates: list[MemoryItem],
    ) -> dict[str, dict[str, Any]]:
        """Stage-1 dense hits when SoR embeddings exist; optional Stage-2 TurboVec."""
        if self.embedding_store is None or self.embedder is None:
            return {}
        if not self.embedding_store.list_models(scope):
            return {}
        from ..domain.embeddings_store import stage1_retrieve

        query_vec = list(self.embedder.embed(query, is_query=True).vector)
        retrieved = stage1_retrieve(
            self.embedding_store,
            scope,
            query_vec,
            top_k=max(8, len(candidates) or 8),
            vector_index=self.vector_index,
            entity_id_map=self.entity_id_map,
        )
        return {str(hit["memory_id"]): hit for hit in retrieved.hits}

"""Shared application helpers for code-graph use cases."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from ..domain.documentation import HeuristicDocGenerator
from ..domain.embeddings import LocalEmbeddingStub
from ..domain.enums import CallConfidence, DocStatus, SymbolKind
from ..domain.errors import NotFoundError
from ..domain.external_calls import is_external_call_id
from ..domain.hashing import digest, now_iso
from ..domain.models import GraphEdge, GraphSymbol, Scope
from ..domain.parsing_authority import assert_durable_edge_metadata_allowed
from ..domain.ports import Store
from ..domain.rag import SEARCHABLE_SYMBOL_KINDS
from ..postgres_side import EmbeddingIndex


def unresolved_symbol_id(scope: Scope, call: str) -> str:
    """Scoped placeholder id so unresolved endpoints do not collide across projects."""
    return f"unresolved:{scope.project_id}:{call}"


def unresolved_call_name(target_id: str) -> str:
    """Extract the call name from unresolved:/ext:call: placeholders."""
    tid = str(target_id)
    for prefix in ("unresolved:", "ext:call:"):
        if tid.startswith(prefix):
            rest = tid.removeprefix(prefix)
            if ":" in rest:
                return rest.split(":", 1)[1]
            return rest
    return tid


class GraphServiceSupport:
    """Base helpers shared by ingest/query/generation use-case mixins."""

    store: Store
    docs: HeuristicDocGenerator
    embeddings: LocalEmbeddingStub
    embedding_index: EmbeddingIndex | None
    vector_index: Any | None
    entity_id_map: Any | None

    def _ann_sync_on_write(self) -> bool:
        # Composition root only injects vector_index when accelerator is enabled.
        return self.vector_index is not None and self.entity_id_map is not None

    def _sync_vector_replica_upsert(self, symbol_id: str, vector: list[float]) -> None:
        if not self._ann_sync_on_write():
            return
        try:
            import numpy as np

            uid = self.entity_id_map.get_or_assign(symbol_id)
            arr = np.asarray([vector], dtype=np.float32)
            self.vector_index.upsert([uid], arr)
        except Exception:
            try:
                from vector_index import get_accelerator_metrics

                get_accelerator_metrics().record_fallback()
            except Exception:
                pass
            # Replica lag is fail-open; pgvector SoR remains authoritative.
            return

    def _sync_vector_replica_delete(self, symbol_id: str) -> None:
        if self.vector_index is None or self.entity_id_map is None:
            return
        try:
            uid = self.entity_id_map.to_uint64(symbol_id)
            if uid is None:
                return
            self.vector_index.remove([uid])
            self.entity_id_map.remove(symbol_id)
        except Exception:
            try:
                from vector_index import get_accelerator_metrics

                get_accelerator_metrics().record_fallback()
            except Exception:
                pass
            return

    def _index_embedding(
        self,
        scope: Scope,
        symbol_id: str,
        vector: list[float],
        *,
        kind: str,
    ) -> None:
        if self.embedding_index is None:
            return
        kind_value = str(kind or "").strip() or "unknown"
        if kind_value not in SEARCHABLE_SYMBOL_KINDS:
            # Drop stale ANN rows if this id is no longer searchable.
            deleter = getattr(self.embedding_index, "delete", None)
            if callable(deleter):
                deleter(scope, symbol_id)
            self._sync_vector_replica_delete(symbol_id)
            return
        self.embedding_index.upsert(
            scope,
            symbol_id,
            vector,
            model=self.embeddings.model,
            kind=kind_value,
        )
        self._sync_vector_replica_upsert(symbol_id, vector)

    def _delete_embedding(self, scope: Scope, symbol_id: str) -> None:
        if self.embedding_index is None:
            return
        deleter = getattr(self.embedding_index, "delete", None)
        if callable(deleter):
            deleter(scope, symbol_id)
        self._sync_vector_replica_delete(symbol_id)

    def _ensure_placeholder_symbol(self, scope: Scope, symbol_id: str) -> None:
        """Materialize unresolved:* / ext:call:* endpoints so edges can attach."""
        if symbol_id.startswith("unresolved:"):
            kind = SymbolKind.UNRESOLVED
            doc = ""
        elif is_external_call_id(symbol_id):
            kind = SymbolKind.EXTERNAL
            doc = "external call (outside repository)"
        else:
            return
        if self._maybe_get(symbol_id, scope) is not None:
            return
        name = unresolved_call_name(symbol_id) or symbol_id
        stamp = now_iso()
        self.store.put_symbol(
            GraphSymbol(
                id=symbol_id,
                scope=scope,
                kind=kind,
                file_path="",
                name=name,
                qualified_name=symbol_id,
                signature="",
                body="",
                hash_value=digest(symbol_id),
                ai_documentation=doc,
                doc_status=DocStatus.MISSING,
                embedding=[],
                visibility="public",
                created_at=stamp,
                updated_at=stamp,
            )
        )

    def _ensure_unresolved_symbol(self, scope: Scope, symbol_id: str) -> None:
        """Backward-compatible alias for placeholder materialization."""
        self._ensure_placeholder_symbol(scope, symbol_id)

    def _put_edge(
        self,
        scope: Scope,
        rel_type: str,
        source_id: str,
        target_id: str,
        *,
        file_path: str,
        confidence: CallConfidence = CallConfidence.EXACT,
        metadata: dict[str, Any] | None = None,
        link_key: str | None = None,
    ) -> int:
        # ADR 48: durable CODE_REL SoR is AST ingest only — never LSP dual-write.
        assert_durable_edge_metadata_allowed(metadata)
        self._ensure_placeholder_symbol(scope, source_id)
        self._ensure_placeholder_symbol(scope, target_id)
        meta = {"file_path": file_path}
        if metadata:
            meta.update(metadata)
        stable = link_key or target_id
        edge = GraphEdge(
            id=f"edge:{digest(f'{rel_type}|{source_id}|{stable}')[:16]}",
            scope=scope,
            rel_type=rel_type,
            source_id=source_id,
            target_id=target_id,
            confidence=confidence,
            metadata=meta,
        )
        batch = getattr(self._edge_batches, "edges", None)
        if isinstance(batch, list):
            batch.append(edge)
        else:
            self.store.put_edge(edge)
        return 1

    def _begin_edge_batch(self) -> None:
        self._edge_batches.edges = []

    def _flush_edge_batch(self) -> None:
        edges = list(getattr(self._edge_batches, "edges", []) or [])
        try:
            if not edges:
                return
            bulk_put = getattr(self.store, "put_edges", None)
            if callable(bulk_put):
                bulk_put(edges)
            else:
                for edge in edges:
                    self.store.put_edge(edge)
        finally:
            self._edge_batches.edges = None

    def _maybe_get(self, symbol_id: str, scope: Scope) -> GraphSymbol | None:
        try:
            return self.store.get_symbol(symbol_id, scope)
        except NotFoundError:
            return None

    @staticmethod
    def _symbol_view(symbol: GraphSymbol) -> dict[str, Any]:
        return {
            "id": symbol.id,
            "kind": symbol.kind.value,
            "file_path": symbol.file_path,
            "name": symbol.name,
            "qualified_name": symbol.qualified_name,
            "signature": symbol.signature,
            "hash_value": symbol.hash_value,
            "ai_documentation": symbol.ai_documentation,
            "doc_status": symbol.doc_status.value,
            "visibility": symbol.visibility,
            "version": symbol.version,
            "language": symbol.language,
            "hash_version": symbol.hash_version,
            "parser_version": symbol.parser_version,
        }

    @staticmethod
    def _event(
        event_type: str,
        scope: Scope,
        actor_id: str,
        correlation_id: str,
        idempotency_key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "event_version": "1",
            "occurred_at": now_iso(),
            "producer": "code-graph-service",
            "tenant_id": scope.tenant_id,
            "workspace_id": scope.workspace_id,
            "project_id": scope.project_id,
            "project_group_id": scope.project_group_id,
            "actor_ref": actor_id,
            "correlation_id": correlation_id,
            "causation_id": correlation_id,
            "idempotency_key": idempotency_key,
            "payload": payload,
            "evidence_refs": [],
        }

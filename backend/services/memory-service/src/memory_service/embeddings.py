"""Memory embedding package surface (GAP-T03).

Re-exports the domain SoR helpers so docs/linked_symbols can cite
``memory_service.embeddings`` while the implementation lives in
``domain.embeddings_store``.
"""

from __future__ import annotations

from .domain.embeddings_store import (
    InMemoryMemoryEmbeddingStore,
    MemoryEmbeddingRow,
    MemoryEmbeddingStore,
    Stage1RetrieveResult,
    stage1_retrieve,
)
from .local_embedder import EmbeddingResult, LocalHashEmbedder
from .postgres_embeddings import PostgresMemoryEmbeddingStore

__all__ = [
    "EmbeddingResult",
    "InMemoryMemoryEmbeddingStore",
    "LocalHashEmbedder",
    "MemoryEmbeddingRow",
    "MemoryEmbeddingStore",
    "PostgresMemoryEmbeddingStore",
    "Stage1RetrieveResult",
    "stage1_retrieve",
]

"""HybridEmbeddings must soft-fail local BGE into stub when offline/cache miss."""

from __future__ import annotations

import pytest

from code_graph_service.domain.embeddings import LocalEmbeddingStub
from code_graph_service.llm_wiring import HybridEmbeddings


class _BrokenLocal:
    model_name = "broken/model"

    def embed(self, text: str, *, is_query: bool = False):
        raise RuntimeError("huggingface offline")

    def embed_many(self, texts: list[str], *, is_query: bool = False):
        raise RuntimeError("huggingface offline")


def test_hybrid_embed_falls_back_to_stub_when_local_fails() -> None:
    emb = HybridEmbeddings(
        gateway=None,
        local=_BrokenLocal(),
        stub=LocalEmbeddingStub(dims=8),
        dims=8,
    )
    result = emb.embed("hello")
    assert len(result.vector) == 8
    assert emb.backend_name.startswith("stub:")


def test_hybrid_embed_many_falls_back_when_local_batch_fails() -> None:
    emb = HybridEmbeddings(
        gateway=None,
        local=_BrokenLocal(),
        stub=LocalEmbeddingStub(dims=8),
        dims=8,
    )
    rows = emb.embed_many(["a", "b"])
    assert len(rows) == 2
    assert all(len(row.vector) == 8 for row in rows)

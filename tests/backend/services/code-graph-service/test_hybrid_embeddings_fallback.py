"""HybridEmbeddings fallback and fail-closed LiteLLM embed behavior."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from code_graph_service.domain.embeddings import LocalEmbeddingStub
from code_graph_service.llm_wiring import HybridEmbeddings


class _BrokenLocal:
    model_name = "broken/model"

    def embed(self, text: str, *, is_query: bool = False):
        raise RuntimeError("huggingface offline")

    def embed_many(self, texts: list[str], *, is_query: bool = False):
        raise RuntimeError("huggingface offline")


class _BrokenGateway:
    def embed(self, text: str, *, model: str | None = None):
        raise RuntimeError("openrouter down")


class _OkBatchGateway:
    def embed_many(self, texts: list[str], *, model: str | None = None):
        return [
            SimpleNamespace(vector=[0.1] * 8, model=model or "embed-ok")
            for _ in texts
        ]


class _BrokenBatchGateway:
    def embed(self, text: str, *, model: str | None = None):
        raise RuntimeError("openrouter down")

    def embed_many(self, texts: list[str], *, model: str | None = None):
        raise RuntimeError("openrouter down")


def test_hybrid_embed_falls_back_to_stub_when_local_fails(monkeypatch) -> None:
    monkeypatch.setenv("ASTLOOM_LITELLM_EMBEDDINGS_ENABLED", "false")
    emb = HybridEmbeddings(
        gateway=None,
        local=_BrokenLocal(),
        stub=LocalEmbeddingStub(dims=8),
        dims=8,
    )
    result = emb.embed("hello")
    assert len(result.vector) == 8
    assert emb.backend_name.startswith("stub:")


def test_hybrid_embed_many_falls_back_when_local_batch_fails(monkeypatch) -> None:
    monkeypatch.setenv("ASTLOOM_LITELLM_EMBEDDINGS_ENABLED", "false")
    emb = HybridEmbeddings(
        gateway=None,
        local=_BrokenLocal(),
        stub=LocalEmbeddingStub(dims=8),
        dims=8,
    )
    rows = emb.embed_many(["a", "b"])
    assert len(rows) == 2
    assert all(len(row.vector) == 8 for row in rows)


def test_truncate_embedding_input_respects_token_budget(monkeypatch) -> None:
    from code_graph_service.llm_wiring import truncate_embedding_input

    monkeypatch.setenv("ASTLOOM_EMBEDDING_MAX_INPUT_TOKENS", "10")
    monkeypatch.setenv("ASTLOOM_EMBEDDING_CHARS_PER_TOKEN", "3")
    long = "x" * 500
    out = truncate_embedding_input(long)
    assert len(out) <= 10 * 3
    assert out.endswith("…")


def test_hybrid_embed_fail_closed_when_litellm_embeddings_enabled(monkeypatch) -> None:
    monkeypatch.setenv("ASTLOOM_LITELLM_EMBEDDINGS_ENABLED", "true")
    monkeypatch.setenv("ASTLOOM_LITELLM_MODEL_EMBED", "openrouter/baai/bge-large-en-v1.5")
    from llm_gateway.routing import clear_routing_profile_cache

    clear_routing_profile_cache()
    emb = HybridEmbeddings(
        gateway=_BrokenGateway(),
        local=None,
        stub=LocalEmbeddingStub(dims=8),
        dims=8,
        settings=SimpleNamespace(enabled=True, default_model="x"),
    )
    with pytest.raises(RuntimeError, match="LiteLLM embedding failed"):
        emb.embed("hello")


def test_hybrid_embed_many_uses_embed_symbol_route(monkeypatch) -> None:
    monkeypatch.setenv("ASTLOOM_LITELLM_EMBEDDINGS_ENABLED", "true")
    monkeypatch.setenv("ASTLOOM_LITELLM_MODEL_EMBED", "openrouter/baai/bge-large-en-v1.5")
    from llm_gateway.routing import clear_routing_profile_cache

    clear_routing_profile_cache()
    emb = HybridEmbeddings(
        gateway=_OkBatchGateway(),
        local=None,
        stub=LocalEmbeddingStub(dims=8),
        dims=8,
        settings=SimpleNamespace(enabled=True, default_model="x"),
    )
    rows = emb.embed_many(["a", "b"])
    assert len(rows) == 2
    assert all(len(row.vector) == 8 for row in rows)
    assert emb.backend_name.startswith("litellm")


def test_hybrid_embed_many_fail_closed_when_litellm_batch_fails(monkeypatch) -> None:
    monkeypatch.setenv("ASTLOOM_LITELLM_EMBEDDINGS_ENABLED", "true")
    monkeypatch.setenv("ASTLOOM_LITELLM_MODEL_EMBED", "openrouter/baai/bge-large-en-v1.5")
    from llm_gateway.routing import clear_routing_profile_cache

    clear_routing_profile_cache()
    emb = HybridEmbeddings(
        gateway=_BrokenBatchGateway(),
        local=None,
        stub=LocalEmbeddingStub(dims=8),
        dims=8,
        settings=SimpleNamespace(enabled=True, default_model="x"),
    )
    with pytest.raises(RuntimeError, match="LiteLLM embedding batch failed"):
        emb.embed_many(["a", "b"])

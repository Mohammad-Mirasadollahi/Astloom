"""Local BGE must prefer on-disk cache and fail fast when offline/uncached."""

from __future__ import annotations

import time

import pytest

from code_graph_service import local_embeddings as le


def test_load_sentence_transformer_fails_fast_when_offline_and_uncached(
    monkeypatch, tmp_path
) -> None:
    le._load_sentence_transformer.cache_clear()
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    monkeypatch.delenv("ASTLOOM_EMBEDDING_ALLOW_DOWNLOAD", raising=False)
    started = time.monotonic()
    with pytest.raises(RuntimeError, match="not cached"):
        le._load_sentence_transformer(
            "BAAI/bge-large-en-v1.5",
            str(tmp_path / "empty-cache"),
            "cpu",
        )
    elapsed = time.monotonic() - started
    assert elapsed < 30.0


def test_load_sentence_transformer_uses_local_cache_when_present(monkeypatch) -> None:
    cache = "/opt/Astloom/ai-toolstack/data/rag-embedding-cache"
    model_dir = (
        f"{cache}/sentence-transformers/models--BAAI--bge-base-en-v1.5"
    )
    import os

    if not os.path.isdir(model_dir):
        pytest.skip("bge-base cache not present on this host")
    le._load_sentence_transformer.cache_clear()
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    model = le._load_sentence_transformer("BAAI/bge-base-en-v1.5", cache, "cpu")
    assert model is not None

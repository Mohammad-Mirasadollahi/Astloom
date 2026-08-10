"""Phase F2: embedding preload env knob + HF hub noise filter."""

from __future__ import annotations

import logging

from code_graph_service.domain.embeddings import LocalEmbeddingStub
from code_graph_service.llm_wiring import HybridEmbeddings, maybe_preload_embeddings
from code_graph_service.local_embeddings import (
    _DropUnauthenticatedHfHubNoise,
    _quiet_huggingface_hub_auth_noise,
    embedding_settings_from_env,
)


def test_embedding_preload_flag_defaults_false():
    cfg = embedding_settings_from_env({})
    assert cfg["preload"] is False


def test_embedding_preload_flag_true():
    cfg = embedding_settings_from_env({"ASTLOOM_EMBEDDING_PRELOAD": "true"})
    assert cfg["preload"] is True


def test_maybe_preload_embeddings_calls_local_preload(monkeypatch):
    calls: list[str] = []

    class FakeLocal:
        model_name = "fake"

        def preload(self) -> None:
            calls.append("preload")

        def embed(self, text: str, *, is_query: bool = False):
            raise AssertionError("embed should not run")

    emb = HybridEmbeddings(None, local=FakeLocal(), stub=LocalEmbeddingStub(dims=8), dims=8)
    assert maybe_preload_embeddings(emb, {"ASTLOOM_EMBEDDING_PRELOAD": "1"}) is True
    assert calls == ["preload"]
    assert maybe_preload_embeddings(emb, {"ASTLOOM_EMBEDDING_PRELOAD": "false"}) is False


def test_hf_unauth_noise_filter_drops_nag(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGING_FACE_HUB_TOKEN", raising=False)
    import code_graph_service.local_embeddings as le

    monkeypatch.setattr(le, "_hf_noise_filter_installed", False)
    _quiet_huggingface_hub_auth_noise()
    filt = _DropUnauthenticatedHfHubNoise()
    nag = logging.LogRecord(
        name="huggingface_hub",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg=(
            "Warning: You are sending unauthenticated requests to the HF Hub. "
            "Please set a HF_TOKEN"
        ),
        args=(),
        exc_info=None,
    )
    keep = logging.LogRecord(
        name="huggingface_hub",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="Failed to download model weights",
        args=(),
        exc_info=None,
    )
    assert filt.filter(nag) is False
    assert filt.filter(keep) is True

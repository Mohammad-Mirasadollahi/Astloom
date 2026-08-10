"""Local sentence-transformers embedding backend (BGE and similar)."""

from __future__ import annotations

import logging
import os
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

from .domain.models import EmbeddingResult

DEFAULT_LOCAL_MODEL = "BAAI/bge-large-en-v1.5"
DEFAULT_LOCAL_DIMS = 1024
DEFAULT_CACHE_DIR = "/opt/astloom-models"

_HF_UNAUTH_NOISE = "unauthenticated requests to the HF Hub"
_hf_noise_filter_installed = False
_MODEL_LOAD_LOCK = threading.Lock()
_MODEL_SLOTS = threading.BoundedSemaphore(4)
_MODEL_SLOTS_LOCK = threading.Lock()


def configure_local_embed_slots(max_concurrency: int) -> int:
    """Replace the process-wide local BGE encode semaphore (call before sync work)."""
    global _MODEL_SLOTS
    slots = max(1, int(max_concurrency))
    with _MODEL_SLOTS_LOCK:
        _MODEL_SLOTS = threading.BoundedSemaphore(slots)
    return slots


class _DropUnauthenticatedHfHubNoise(logging.Filter):
    """Drop huggingface_hub rate-limit nags when operating without HF_TOKEN."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        return _HF_UNAUTH_NOISE not in msg


def _quiet_huggingface_hub_auth_noise() -> None:
    """Local BGE does not require HF_TOKEN; hide the unauthenticated-request nag.

    Operators who set ``HF_TOKEN`` / ``HUGGING_FACE_HUB_TOKEN`` keep default hub logs.
    """
    global _hf_noise_filter_installed
    if _hf_noise_filter_installed:
        return
    if os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN"):
        return
    import warnings

    warnings.filterwarnings(
        "ignore",
        message=r".*unauthenticated requests to the HF Hub.*",
    )
    filt = _DropUnauthenticatedHfHubNoise()
    for name in ("huggingface_hub", "huggingface_hub.utils", "huggingface_hub.utils._http"):
        logging.getLogger(name).addFilter(filt)
    _hf_noise_filter_installed = True


def embedding_settings_from_env(environ: dict[str, str] | None = None) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    provider = str(env.get("ASTLOOM_EMBEDDING_PROVIDER", "local_bge")).strip().lower() or "local_bge"
    if provider in {"bge", "local", "sentence_transformers"}:
        provider = "local_bge"
    model = str(env.get("ASTLOOM_EMBEDDING_MODEL", DEFAULT_LOCAL_MODEL)).strip() or DEFAULT_LOCAL_MODEL
    cache_dir = str(env.get("ASTLOOM_EMBEDDING_CACHE_DIR", DEFAULT_CACHE_DIR)).strip() or DEFAULT_CACHE_DIR
    dims_raw = str(env.get("ASTLOOM_EMBEDDING_DIMS", str(DEFAULT_LOCAL_DIMS))).strip()
    dims = int(dims_raw) if dims_raw else DEFAULT_LOCAL_DIMS
    device = str(env.get("ASTLOOM_EMBEDDING_DEVICE", "cpu")).strip() or "cpu"
    local_enabled_raw = str(env.get("ASTLOOM_EMBEDDING_LOCAL_ENABLED", "true")).strip().lower()
    local_enabled = local_enabled_raw not in {"0", "false", "no", "off"}
    preload_raw = str(env.get("ASTLOOM_EMBEDDING_PRELOAD", "false")).strip().lower()
    preload = preload_raw in {"1", "true", "yes", "on"}
    return {
        "provider": provider,
        "model": model,
        "cache_dir": cache_dir,
        "dims": dims,
        "device": device,
        "local_enabled": local_enabled,
        "preload": preload,
    }


def _prepare_cache_env(cache_dir: str) -> Path:
    root = Path(cache_dir).expanduser().resolve()
    hf = root / "huggingface"
    st = root / "sentence-transformers"
    hf.mkdir(parents=True, exist_ok=True)
    st.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(hf))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(hf / "hub"))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(hf / "transformers"))
    os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", str(st))
    _quiet_huggingface_hub_auth_noise()
    return st


@lru_cache(maxsize=2)
def _load_sentence_transformer(model_name: str, cache_dir: str, device: str) -> Any:
    st_home = _prepare_cache_env(cache_dir)
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        model_name,
        cache_folder=str(st_home),
        device=device,
    )


class LocalBgeEmbeddings:
    """Embed text with a local SentenceTransformer model (default BAAI/bge-large-en-v1.5)."""

    def __init__(
        self,
        *,
        model_name: str = DEFAULT_LOCAL_MODEL,
        cache_dir: str = DEFAULT_CACHE_DIR,
        dims: int = DEFAULT_LOCAL_DIMS,
        device: str = "cpu",
    ) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.dims = dims
        self.device = device
        self.model = model_name
        self._encoder = None

    def _ensure_loaded(self) -> Any:
        if self._encoder is None:
            with _MODEL_LOAD_LOCK:
                if self._encoder is None:
                    self._encoder = _load_sentence_transformer(self.model_name, self.cache_dir, self.device)
        return self._encoder

    def preload(self) -> None:
        """Force model download/load into cache."""
        self._ensure_loaded()

    def embed(self, text: str, *, is_query: bool = False) -> EmbeddingResult:
        return self.embed_many([text], is_query=is_query)[0]

    def embed_many(
        self,
        texts: list[str],
        *,
        is_query: bool = False,
    ) -> list[EmbeddingResult]:
        with _MODEL_SLOTS:
            encoder = self._ensure_loaded()
            payloads = [text or "" for text in texts]
            if is_query and "bge" in self.model_name.lower():
                payloads = [
                    f"Represent this sentence for searching relevant passages: {text}"
                    for text in payloads
                ]
            vectors = encoder.encode(
                payloads,
                batch_size=32,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        rows = list(vectors)
        if len(payloads) == 1 and rows and isinstance(rows[0], (int, float)):
            rows = [rows]
        results: list[EmbeddingResult] = []
        for vector in rows:
            values = [float(value) for value in list(vector)]
            if len(values) < self.dims:
                values.extend([0.0] * (self.dims - len(values)))
            elif len(values) > self.dims:
                values = values[: self.dims]
            results.append(
                EmbeddingResult(values, "ready", self.model_name, self.dims)
            )
        return results

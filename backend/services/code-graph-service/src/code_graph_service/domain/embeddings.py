"""Local embedding stub for semantic ranking (swap point for pgvector)."""

from __future__ import annotations

import re

from .hashing import digest
from .models import EmbeddingResult


def embed_text(text: str, dims: int = 16) -> list[float]:
    """Cheap local embedding for tests and offline semantic ranking."""
    vec = [0.0] * dims
    tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower())
    if not tokens:
        return vec
    for token in tokens:
        idx = int(digest(token)[:8], 16) % dims
        vec[idx] += 1.0
    norm = sum(v * v for v in vec) ** 0.5 or 1.0
    return [round(v / norm, 6) for v in vec]


class LocalEmbeddingStub:
    """In-process embedding stub — swap for pgvector-backed provider later."""

    def __init__(self, dims: int = 16, model: str = "local-hash-v1") -> None:
        self.dims = dims
        self.model = model

    def embed(self, text: str, *, is_query: bool = False) -> EmbeddingResult:
        """Embed text. ``is_query`` is accepted for API parity with BGE (ignored here)."""
        _ = is_query
        if not text.strip():
            return EmbeddingResult([0.0] * self.dims, "empty", self.model, self.dims)
        return EmbeddingResult(embed_text(text, self.dims), "ready", self.model, self.dims)

    def embed_many(
        self,
        texts: list[str],
        *,
        is_query: bool = False,
    ) -> list[EmbeddingResult]:
        return [self.embed(text, is_query=is_query) for text in texts]


def cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=False))

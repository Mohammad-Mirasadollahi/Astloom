"""Cheap local embedder for memory-service when a production provider is unset."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re


@dataclass(frozen=True)
class EmbeddingResult:
    vector: list[float]
    model: str
    dims: int


class LocalHashEmbedder:
    """Deterministic bag-of-tokens embedder for offline / unit paths."""

    def __init__(self, dims: int = 1024, model: str = "local-hash-v1") -> None:
        if dims <= 0:
            raise ValueError("dims must be positive")
        self.dims = int(dims)
        self.model = model

    def embed(self, text: str, *, is_query: bool = False) -> EmbeddingResult:
        _ = is_query
        vec = [0.0] * self.dims
        tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", (text or "").lower())
        if not tokens:
            return EmbeddingResult(vec, self.model, self.dims)
        for token in tokens:
            idx = int(sha256(token.encode("utf-8")).hexdigest()[:8], 16) % self.dims
            vec[idx] += 1.0
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        return EmbeddingResult([v / norm for v in vec], self.model, self.dims)

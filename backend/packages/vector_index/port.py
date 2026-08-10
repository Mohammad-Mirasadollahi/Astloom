"""VectorIndexPort — optional ANN acceleration seam (not embedding SoR).

Role: Protocol for quantized / in-process dense search used after Stage-1 ACL filters.
Source of truth: PostgreSQL + pgvector remains durable embeddings SoR; this port is a rebuildable replica.
Allowed: fail open to SoR when the accelerator is missing or search fails.
Forbidden: bypassing Stage-1 allowlists; importing vendor packages in domain layers.
"""

from __future__ import annotations

from typing import Protocol, Sequence

import numpy as np
from numpy.typing import NDArray


class VectorIndexPort(Protocol):
    """Infrastructure port for optional ANN acceleration (e.g. turbovec IdMapIndex)."""

    def upsert(self, ids: Sequence[int], vectors: NDArray[np.float32]) -> None:
        """Insert or replace vectors keyed by stable uint64 external ids."""

    def remove(self, ids: Sequence[int]) -> int:
        """Remove ids; return count of ids that were present."""

    def search(
        self,
        query: NDArray[np.float32],
        k: int,
        *,
        allowlist: Sequence[int] | None = None,
    ) -> tuple[NDArray[np.float32], NDArray[np.uint64]]:
        """Dense top-k. Prefer allowlist after Stage-1; empty allowlist must not be passed."""

    def write_snapshot(self, uri: str) -> None:
        """Persist derivative snapshot (local path or file URI)."""

    def load_snapshot(self, uri: str) -> None:
        """Load derivative snapshot; reject on dim/bit_width mismatch."""

    def rebuild_from_rows(self, ids: Sequence[int], vectors: NDArray[np.float32]) -> None:
        """Replace replica contents from SoR-derived (id, vector) rows."""

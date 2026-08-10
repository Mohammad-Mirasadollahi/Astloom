"""TurboVec IdMapIndex adapter behind VectorIndexPort.

Role: Optional in-process ANN replica wrapping turbovec.IdMapIndex only (never TurboQuantIndex).
Source of truth: pgvector SoR; this adapter is a rebuildable derivative (snapshots are not SoR).
Allowed: lazy import; return unavailable / fail open to SoR when the wheel is missing.
Forbidden: using positional TurboQuantIndex; searching with an empty allowlist; widening ACL.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)


class TurboVecUnavailable(RuntimeError):
    """Raised when turbovec cannot be imported or constructed."""


def turbovec_importable() -> bool:
    try:
        import turbovec  # noqa: F401
    except ImportError:
        return False
    return True


def turbovec_available() -> bool:
    """Alias used by service hooks."""
    return turbovec_importable()


def _local_path(uri: str) -> str:
    text = str(uri).strip()
    if text.startswith("file://"):
        text = text[7:]
    return text


class TurboVecIndexAdapter:
    """VectorIndexPort implementation backed by turbovec.IdMapIndex."""

    def __init__(self, dim: int, bit_width: int = 4) -> None:
        if dim <= 0 or dim % 8 != 0 or dim > 65536:
            raise ValueError("dim must be a positive multiple of 8 and ≤ 65536")
        if bit_width not in {2, 3, 4}:
            raise ValueError("bit_width must be 2, 3, or 4")
        try:
            from turbovec import IdMapIndex
        except ImportError as exc:  # pragma: no cover - exercised via try_create
            raise TurboVecUnavailable("turbovec package is not installed") from exc
        self._dim = dim
        self._bit_width = bit_width
        self._idx: Any = IdMapIndex(dim=dim, bit_width=bit_width)

    @classmethod
    def try_create(cls, *, dim: int, bit_width: int = 4) -> TurboVecIndexAdapter | None:
        """Build adapter or return None when turbovec is missing / invalid."""
        try:
            return cls(dim=dim, bit_width=bit_width)
        except (TurboVecUnavailable, ValueError) as exc:
            logger.warning("turbovec accelerator disabled: %s", exc)
            return None

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def bit_width(self) -> int:
        return self._bit_width

    def upsert(self, ids: Sequence[int], vectors: NDArray[np.float32]) -> None:
        arr = np.ascontiguousarray(vectors, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        id_arr = np.asarray(list(ids), dtype=np.uint64)
        if id_arr.shape[0] != arr.shape[0]:
            raise ValueError("ids length must match vectors rows")
        if arr.shape[1] != self._dim:
            raise ValueError(f"expected dim {self._dim}, got {arr.shape[1]}")
        # IdMapIndex rejects duplicate ids — remove then re-add for upsert semantics.
        for uid in id_arr.tolist():
            self._idx.remove(int(uid))
        self._idx.add_with_ids(arr, id_arr)

    def remove(self, ids: Sequence[int]) -> int:
        removed = 0
        for uid in ids:
            if self._idx.remove(int(uid)):
                removed += 1
        return removed

    def search(
        self,
        query: NDArray[np.float32],
        k: int,
        *,
        allowlist: Sequence[int] | None = None,
    ) -> tuple[NDArray[np.float32], NDArray[np.uint64]]:
        q = np.ascontiguousarray(query, dtype=np.float32).reshape(1, -1)
        if q.shape[1] != self._dim:
            raise ValueError(f"query dim {q.shape[1]} != index dim {self._dim}")
        al = None
        if allowlist is not None:
            al = np.asarray(list(allowlist), dtype=np.uint64)
            if al.size == 0:
                raise ValueError("allowlist must be non-empty when provided")
        scores, hit_ids = self._idx.search(q, max(1, int(k)), allowlist=al)
        # Vendor returns (nq, effective_k); flatten single-query batch for the port.
        return (
            np.asarray(scores[0], dtype=np.float32),
            np.asarray(hit_ids[0], dtype=np.uint64),
        )

    def write_snapshot(self, uri: str) -> None:
        path = Path(_local_path(uri))
        path.parent.mkdir(parents=True, exist_ok=True)
        self._idx.write(str(path))

    def load_snapshot(self, uri: str) -> None:
        from turbovec import IdMapIndex

        loaded = IdMapIndex.load(_local_path(uri))
        loaded_dim = getattr(loaded, "dim", None)
        loaded_bw = getattr(loaded, "bit_width", None)
        if loaded_dim is not None and int(loaded_dim) != self._dim:
            raise ValueError(f"snapshot dim {loaded_dim} != adapter dim {self._dim}")
        if loaded_bw is not None and int(loaded_bw) != self._bit_width:
            raise ValueError(f"snapshot bit_width {loaded_bw} != adapter bit_width {self._bit_width}")
        self._idx = loaded

    def size(self) -> int:
        ntotal = getattr(self._idx, "ntotal", None)
        if ntotal is not None:
            return int(ntotal)
        return 0

    def rebuild_from_rows(self, ids: Sequence[int], vectors: NDArray[np.float32]) -> None:
        """Clear-and-reload replica from SoR rows (derivative rebuild)."""
        from turbovec import IdMapIndex

        self._idx = IdMapIndex(dim=self._dim, bit_width=self._bit_width)
        if len(ids) == 0:
            return
        self.upsert(ids, vectors)

"""In-memory VectorIndexPort fake for unit tests (no native wheel)."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Sequence

import numpy as np
from numpy.typing import NDArray


class InMemoryVectorIndex:
    """Deterministic cosine ANN fake implementing VectorIndexPort."""

    def __init__(self, *, dim: int | None = None) -> None:
        self._dim = dim
        self._vectors: dict[int, NDArray[np.float32]] = {}
        self._lock = threading.RLock()

    @property
    def dim(self) -> int | None:
        return self._dim

    def upsert(self, ids: Sequence[int], vectors: NDArray[np.float32]) -> None:
        arr = np.asarray(vectors, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        if arr.ndim != 2:
            raise ValueError("vectors must be 2-D float32")
        if len(ids) != arr.shape[0]:
            raise ValueError("ids length must match vectors rows")
        if self._dim is None:
            self._dim = int(arr.shape[1])
        elif int(arr.shape[1]) != self._dim:
            raise ValueError(f"expected dim {self._dim}, got {arr.shape[1]}")
        with self._lock:
            for uid, row in zip(ids, arr, strict=True):
                self._vectors[int(uid)] = np.ascontiguousarray(row, dtype=np.float32)

    def remove(self, ids: Sequence[int]) -> int:
        removed = 0
        with self._lock:
            for uid in ids:
                if self._vectors.pop(int(uid), None) is not None:
                    removed += 1
        return removed

    def search(
        self,
        query: NDArray[np.float32],
        k: int,
        *,
        allowlist: Sequence[int] | None = None,
    ) -> tuple[NDArray[np.float32], NDArray[np.uint64]]:
        q = np.asarray(query, dtype=np.float32).reshape(-1)
        if self._dim is not None and q.shape[0] != self._dim:
            raise ValueError(f"query dim {q.shape[0]} != index dim {self._dim}")
        k = max(1, int(k))
        with self._lock:
            if allowlist is not None:
                allowed = {int(x) for x in allowlist}
                if not allowed:
                    raise ValueError("allowlist must be non-empty when provided")
                items = [(uid, vec) for uid, vec in self._vectors.items() if uid in allowed]
            else:
                items = list(self._vectors.items())
        if not items:
            return (
                np.zeros((0,), dtype=np.float32),
                np.zeros((0,), dtype=np.uint64),
            )
        qn = float(np.linalg.norm(q)) or 1.0
        scored: list[tuple[float, int]] = []
        for uid, vec in items:
            vn = float(np.linalg.norm(vec)) or 1.0
            scored.append((float(np.dot(q, vec) / (qn * vn)), uid))
        scored.sort(key=lambda item: (-item[0], item[1]))
        top = scored[: min(k, len(scored))]
        scores = np.asarray([s for s, _ in top], dtype=np.float32)
        ids_out = np.asarray([uid for _, uid in top], dtype=np.uint64)
        return scores, ids_out

    def write_snapshot(self, uri: str) -> None:
        path = _local_path(uri)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            ids = list(self._vectors.keys())
            rows = [self._vectors[i] for i in ids]
            dim = self._dim
        np.savez_compressed(
            path,
            dim=np.asarray([-1 if dim is None else dim], dtype=np.int64),
            ids=np.asarray(ids, dtype=np.uint64),
            vectors=(
                np.asarray(rows, dtype=np.float32)
                if rows
                else np.zeros((0, 0), dtype=np.float32)
            ),
        )

    def load_snapshot(self, uri: str) -> None:
        path = _local_path(uri)
        data = np.load(path)
        dim_raw = int(data["dim"][0])
        dim = None if dim_raw < 0 else dim_raw
        ids = data["ids"].astype(np.uint64)
        vectors = data["vectors"].astype(np.float32)
        with self._lock:
            self._dim = dim
            self._vectors = {}
            if vectors.size == 0:
                return
            for uid, row in zip(ids, vectors, strict=True):
                self._vectors[int(uid)] = np.ascontiguousarray(row, dtype=np.float32)

    def size(self) -> int:
        with self._lock:
            return len(self._vectors)

    def rebuild_from_rows(self, ids: Sequence[int], vectors: NDArray[np.float32]) -> None:
        arr = np.asarray(vectors, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        if len(ids) != arr.shape[0]:
            raise ValueError("ids length must match vectors rows")
        with self._lock:
            self._vectors = {}
            self._dim = int(arr.shape[1]) if arr.size else self._dim
        if arr.size:
            self.upsert(ids, arr)


def _local_path(uri: str) -> Path:
    text = str(uri).strip()
    if text.startswith("file://"):
        text = text[7:]
    return Path(text)

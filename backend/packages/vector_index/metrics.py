"""Process-local ANN accelerator metrics (fail-open; not a telemetry exporter).

Role: Counters/timers for Stage-2 search, sync, fallback, and replica lag proxies.
Source of truth: in-process only; dump for tests/CLI; pgvector remains SoR.
Allowed: best-effort increments; reset in unit tests.
Forbidden: sending metrics outside the private boundary; blocking retrieve on metric errors.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AcceleratorMetrics:
    """Mutable process-local counters for optional ANN acceleration."""

    search_count: int = 0
    search_latency_ms_total: float = 0.0
    fallback_total: int = 0
    sync_total: int = 0
    remove_total: int = 0
    snapshot_write_total: int = 0
    snapshot_load_total: int = 0
    snapshot_load_fail_total: int = 0
    replica_size: int = 0
    queue_depth: int = 0
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def record_search(self, latency_ms: float, *, replica_size: int | None = None) -> None:
        with self._lock:
            self.search_count += 1
            self.search_latency_ms_total += max(0.0, float(latency_ms))
            if replica_size is not None:
                self.replica_size = max(0, int(replica_size))

    def record_fallback(self) -> None:
        with self._lock:
            self.fallback_total += 1

    def record_sync(self, *, replica_size: int | None = None) -> None:
        with self._lock:
            self.sync_total += 1
            if replica_size is not None:
                self.replica_size = max(0, int(replica_size))

    def record_remove(self, *, replica_size: int | None = None) -> None:
        with self._lock:
            self.remove_total += 1
            if replica_size is not None:
                self.replica_size = max(0, int(replica_size))

    def record_snapshot_write(self) -> None:
        with self._lock:
            self.snapshot_write_total += 1

    def record_snapshot_load(self, *, ok: bool) -> None:
        with self._lock:
            if ok:
                self.snapshot_load_total += 1
            else:
                self.snapshot_load_fail_total += 1

    def set_queue_depth(self, depth: int) -> None:
        with self._lock:
            self.queue_depth = max(0, int(depth))

    def mean_search_latency_ms(self) -> float:
        with self._lock:
            if self.search_count <= 0:
                return 0.0
            return self.search_latency_ms_total / float(self.search_count)

    def public(self) -> dict[str, Any]:
        with self._lock:
            return {
                "rag.accelerator.search_count": self.search_count,
                "rag.accelerator.search_latency_ms_mean": self.mean_search_latency_ms(),
                "rag.accelerator.fallback_total": self.fallback_total,
                "rag.accelerator.sync_total": self.sync_total,
                "rag.accelerator.remove_total": self.remove_total,
                "rag.accelerator.replica_size": self.replica_size,
                "rag.accelerator.snapshot_write_total": self.snapshot_write_total,
                "rag.accelerator.snapshot_load_total": self.snapshot_load_total,
                "rag.accelerator.snapshot_load_fail_total": self.snapshot_load_fail_total,
                "rag.accelerator.queue_depth": self.queue_depth,
            }

    def reset(self) -> None:
        with self._lock:
            self.search_count = 0
            self.search_latency_ms_total = 0.0
            self.fallback_total = 0
            self.sync_total = 0
            self.remove_total = 0
            self.snapshot_write_total = 0
            self.snapshot_load_total = 0
            self.snapshot_load_fail_total = 0
            self.replica_size = 0
            self.queue_depth = 0


_GLOBAL = AcceleratorMetrics()


def get_accelerator_metrics() -> AcceleratorMetrics:
    return _GLOBAL


def reset_accelerator_metrics() -> None:
    _GLOBAL.reset()


class InstrumentedVectorIndex:
    """VectorIndexPort wrapper: metrics + optional local snapshot persistence."""

    def __init__(
        self,
        inner: Any,
        *,
        metrics: AcceleratorMetrics | None = None,
        snapshot_uri: str = "",
    ) -> None:
        self._inner = inner
        self._metrics = metrics if metrics is not None else get_accelerator_metrics()
        self._snapshot_uri = str(snapshot_uri or "").strip()

    @property
    def dim(self) -> Any:
        return getattr(self._inner, "dim", None)

    @property
    def bit_width(self) -> Any:
        return getattr(self._inner, "bit_width", None)

    @property
    def inner(self) -> Any:
        return self._inner

    def _size(self) -> int | None:
        size_fn = getattr(self._inner, "size", None)
        if callable(size_fn):
            try:
                return int(size_fn())
            except Exception:
                return None
        vectors = getattr(self._inner, "_vectors", None)
        if isinstance(vectors, dict):
            return len(vectors)
        idx = getattr(self._inner, "_idx", None)
        ntotal = getattr(idx, "ntotal", None)
        if ntotal is not None:
            try:
                return int(ntotal)
            except Exception:
                return None
        return None

    def _persist(self) -> None:
        if not self._snapshot_uri:
            return
        try:
            self._inner.write_snapshot(self._snapshot_uri)
            self._metrics.record_snapshot_write()
        except Exception:
            return

    def upsert(self, ids, vectors) -> None:
        self._inner.upsert(ids, vectors)
        self._metrics.record_sync(replica_size=self._size())
        self._persist()

    def remove(self, ids) -> int:
        removed = self._inner.remove(ids)
        self._metrics.record_remove(replica_size=self._size())
        self._persist()
        return removed

    def search(self, query, k, *, allowlist=None):
        started = time.perf_counter()
        try:
            return self._inner.search(query, k, allowlist=allowlist)
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            self._metrics.record_search(elapsed_ms, replica_size=self._size())

    def write_snapshot(self, uri: str) -> None:
        self._inner.write_snapshot(uri)
        self._metrics.record_snapshot_write()

    def load_snapshot(self, uri: str) -> None:
        self._inner.load_snapshot(uri)
        self._metrics.record_snapshot_load(ok=True)

    def rebuild_from_rows(self, ids, vectors) -> None:
        rebuild = getattr(self._inner, "rebuild_from_rows", None)
        if callable(rebuild):
            rebuild(ids, vectors)
        else:
            # Clear by removing known ids then upsert — callers should prefer native rebuild.
            self._inner.upsert(ids, vectors)
        self._metrics.record_sync(replica_size=self._size())
        self._persist()

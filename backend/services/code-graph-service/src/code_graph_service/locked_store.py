"""Serialize store mutations / cap Neo4j concurrency; resolve sync CPU budget.

Role: cap concurrent store ops (reads and mutations) with a re-entrant semaphore —
never a process-wide exclusive write lock (that left parallel workers on futex).
Postgres adapters use checkout/checkin pools (see pg_thread_local) and share the
same LockedStore slot budget as Neo4j for mutations. Resolve operator CPU budget
into file workers, local-embed slots, and Torch/OMP thread caps.
Source of truth: ASTLOOM_SYNC_CPU_PERCENT / ASTLOOM_SYNC_MAX_FILE_WORKERS /
ASTLOOM_LITELLM_RPM at plan resolve; apply_sync_compute_limits mutates process
env before model load.
Fail closed on invalid percent (fall back to auto). Never leave Torch/OMP uncapped
when a plan is applied — uncapped intra-op threads × workers exhaust host RAM.
Locking every read (old behavior) left parallel workers idle on futex while one
thread scanned the full graph — CPU budget could not be realized.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Any

_DEFAULT_AUTO_EMBED_CAP = 4
# Typical cloud cost per changed file when docs + embeds share one RPM gate:
# ~1 batched docs complete/file + ~1 embed batch/file (+ file embed). Oversizing
# workers to min(cpu, rpm) exhausts the start budget immediately and serializes
# on the gate while the UI still shows "N active / W workers".
_LLM_HOT_CALLS_PER_FILE = 2

# Names treated as mutations when ``lock_reads`` is False (slot-budgeted, not
# exclusive). Postgres and Neo4j both use slots under production bootstrap.
_STORE_MUTATIONS = frozenset(
    {
        "put_symbol",
        "delete_symbol",
        "delete_symbols",
        "delete_file_edges",
        "delete_edge",
        "delete_edges",
        "put_edge",
        "put_edges",
        "begin_idempotency",
        "complete_idempotency",
        "append_event",
        "wipe_scope",
        "upsert",
        "delete",
        "index_embedding",
        "delete_embedding",
        "wipe",
    }
)


@dataclass(frozen=True)
class SyncCpuPlan:
    """Resolved sync compute budget (workers + embed slots + Torch threads)."""

    mode: str
    workers: int
    embed_concurrency: int
    torch_threads: int
    cpu_count: int
    cpu_percent: int | None = None
    store_concurrency: int = 8


def _rpm_from_env(env: dict[str, str]) -> int:
    raw = str(env.get("ASTLOOM_LITELLM_RPM", "") or "").strip()
    if not raw:
        try:
            from llm_gateway.settings import DEFAULT_RPM

            return int(DEFAULT_RPM)
        except Exception:  # noqa: BLE001
            return 30
    try:
        return max(1, int(raw))
    except ValueError:
        return 30


def _parse_cpu_percent(raw: str) -> int | None:
    text = str(raw or "").strip().lower()
    if not text or text in {"auto", "0"}:
        return None
    if text.endswith("%"):
        text = text[:-1].strip()
    try:
        value = int(text)
    except ValueError:
        return None
    if value < 1 or value > 100:
        return None
    return value


def _parse_explicit_workers(raw: str) -> int | None:
    text = str(raw or "").strip().lower()
    if not text or text in {"auto", "0"}:
        return None
    try:
        return max(1, int(text))
    except ValueError:
        return None


def _env_flag_true(env: dict[str, str], key: str, *, default: str) -> bool:
    raw = str(env.get(key, default) or default).strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _cloud_llm_sync_hot(env: dict[str, str]) -> bool:
    """True when sync will burn shared LiteLLM RPM on docs and/or cloud embeds."""
    if _env_flag_true(env, "ASTLOOM_LITELLM_DOCS_ENABLED", default="true"):
        return True
    if not _env_flag_true(env, "ASTLOOM_LITELLM_EMBEDDINGS_ENABLED", default="false"):
        return False
    provider = str(env.get("ASTLOOM_EMBEDDING_PROVIDER", "") or "").strip().lower()
    # local_bge / stub do not consume the LiteLLM RPM gate for embeds.
    if provider in {"local_bge", "stub"}:
        return False
    if provider in {"litellm", "openrouter", "remote"}:
        return True
    # Empty / unknown with embeddings enabled → assume cloud (fail closed on oversize).
    return True


def _llm_aware_worker_cap(env: dict[str, str], *, cpu_count: int) -> int:
    """Upper bound on file workers given RPM and multi-call-per-file cost."""
    rpm = _rpm_from_env(env)
    if not _cloud_llm_sync_hot(env):
        return max(1, min(int(cpu_count), int(rpm)))
    return max(1, min(int(cpu_count), int(rpm) // _LLM_HOT_CALLS_PER_FILE))


def _auto_file_workers(env: dict[str, str], *, cpu_count: int) -> int:
    """Derive worker count from CPU cores and LiteLLM RPM (LLM-aware when hot)."""
    return _llm_aware_worker_cap(env, cpu_count=cpu_count)


def resolve_sync_cpu_plan(
    environ: dict[str, str] | None = None,
    *,
    cpu_count: int | None = None,
) -> SyncCpuPlan:
    """Resolve sync parallelism from env.

    Precedence:
    1. Explicit ``ASTLOOM_SYNC_MAX_FILE_WORKERS`` integer (advanced override)
    2. ``ASTLOOM_SYNC_CPU_PERCENT`` 1..100 — workers from that share of CPUs,
       then capped by the LLM-aware RPM budget when docs/cloud embeds are on
    3. Auto — ``min(cpu_count, RPM)`` when LLM-cold; ``min(cpu, RPM // 2)`` when hot

    Local-embed slots are always capped at ``_DEFAULT_AUTO_EMBED_CAP`` (4) so
    BGE encode does not fan out with file workers. Torch/OMP intra-op threads
    are always 1 so workers do not multiply into thousands of native threads.
    """
    env = environ if environ is not None else os.environ
    cpus = max(1, int(cpu_count if cpu_count is not None else (os.cpu_count() or 1)))
    llm_cap = _llm_aware_worker_cap(env, cpu_count=cpus)

    explicit = _parse_explicit_workers(str(env.get("ASTLOOM_SYNC_MAX_FILE_WORKERS", "") or ""))
    if explicit is not None:
        workers = explicit
        return SyncCpuPlan(
            mode="workers",
            workers=workers,
            # BGE encode slots stay capped even when file workers are higher.
            embed_concurrency=max(1, min(_DEFAULT_AUTO_EMBED_CAP, workers)),
            torch_threads=1,
            cpu_count=cpus,
            cpu_percent=None,
            store_concurrency=max(2, min(8, workers)),
        )

    percent = _parse_cpu_percent(str(env.get("ASTLOOM_SYNC_CPU_PERCENT", "") or ""))
    if percent is not None:
        workers = max(1, int(round(cpus * percent / 100.0)))
        # Percent alone used to spawn ~0.6×CPUs (often ≈RPM) and starve the gate.
        workers = min(workers, llm_cap)
        return SyncCpuPlan(
            mode="percent",
            workers=workers,
            embed_concurrency=max(1, min(_DEFAULT_AUTO_EMBED_CAP, workers)),
            torch_threads=1,
            cpu_count=cpus,
            cpu_percent=percent,
            store_concurrency=max(2, min(8, workers)),
        )

    workers = _auto_file_workers(env, cpu_count=cpus)
    return SyncCpuPlan(
        mode="auto",
        workers=workers,
        embed_concurrency=max(1, min(_DEFAULT_AUTO_EMBED_CAP, workers)),
        torch_threads=1,
        cpu_count=cpus,
        cpu_percent=None,
        store_concurrency=max(2, min(8, workers)),
    )


def sync_max_file_workers(environ: dict[str, str] | None = None) -> int:
    """Return parallel file-worker count (see ``resolve_sync_cpu_plan``)."""
    return resolve_sync_cpu_plan(environ).workers


def apply_sync_compute_limits(plan: SyncCpuPlan | None = None) -> SyncCpuPlan:
    """Pin Torch/OMP/tokenizers thread caps and local-embed slots from ``plan``.

    Call before loading sentence-transformers / Torch. Safe to call more than once.
    """
    resolved = plan if plan is not None else resolve_sync_cpu_plan()
    threads = str(max(1, int(resolved.torch_threads)))
    os.environ["OMP_NUM_THREADS"] = threads
    os.environ["MKL_NUM_THREADS"] = threads
    os.environ["OPENBLAS_NUM_THREADS"] = threads
    os.environ["NUMEXPR_NUM_THREADS"] = threads
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    try:
        from code_graph_service.local_embeddings import configure_local_embed_slots

        configure_local_embed_slots(resolved.embed_concurrency)
    except Exception:  # noqa: BLE001 — embed package optional in some test paths
        pass
    try:
        import torch

        torch.set_num_threads(max(1, int(resolved.torch_threads)))
        interop = getattr(torch, "set_num_interop_threads", None)
        if callable(interop):
            try:
                interop(1)
            except RuntimeError:
                # Torch forbids changing interop threads after parallel work starts.
                pass
    except Exception:  # noqa: BLE001 — Torch may be absent in stub-only environments
        pass
    return resolved


class LockedStore:
    """Cap concurrent store ops (Neo4j Bolt or per-thread Postgres).

    The concurrency semaphore is re-entrant per thread so nested store calls
    (put → helper → get) cannot deadlock on the same BoundedSemaphore.
    ``lock_reads=True`` remains available for non-thread-safe adapters (tests).
    """

    def __init__(
        self,
        store: Any,
        *,
        lock_reads: bool = False,
        max_concurrent: int | None = None,
    ) -> None:
        object.__setattr__(self, "_store", store)
        object.__setattr__(self, "_lock", threading.RLock())
        object.__setattr__(self, "_lock_reads", bool(lock_reads))
        slots = None
        if not lock_reads and max_concurrent is not None and int(max_concurrent) > 0:
            slots = threading.BoundedSemaphore(max(1, int(max_concurrent)))
        object.__setattr__(self, "_slots", slots)
        object.__setattr__(self, "_slot_depth", threading.local())

    def _acquire_slot(self) -> bool:
        slots = self._slots
        if slots is None:
            return False
        depth = getattr(self._slot_depth, "n", 0)
        if depth == 0:
            slots.acquire()
        self._slot_depth.n = depth + 1
        return True

    def _release_slot(self) -> None:
        slots = self._slots
        if slots is None:
            return
        depth = getattr(self._slot_depth, "n", 0) - 1
        self._slot_depth.n = depth
        if depth == 0:
            slots.release()

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._store, name)
        if not callable(attr):
            return attr
        exclusive = self._lock_reads or name in _STORE_MUTATIONS

        def locked(*args: Any, **kwargs: Any) -> Any:
            # lock_reads: exclusive RLock for all traffic (legacy / unsafe adapters).
            # Otherwise: bounded re-entrant slots for reads and mutations so N
            # workers are not parked on one futex while one write runs.
            if self._lock_reads:
                with self._lock:
                    return attr(*args, **kwargs)

            if exclusive and self._slots is None:
                with self._lock:
                    return attr(*args, **kwargs)

            held = self._acquire_slot()
            try:
                return attr(*args, **kwargs)
            finally:
                if held:
                    self._release_slot()

        return locked


class LockedEmbeddings:
    """Bound concurrent embed calls to avoid overwhelming a shared local model."""

    def __init__(self, embeddings: Any, *, max_concurrency: int = 4) -> None:
        self._inner = embeddings
        self._slots = threading.BoundedSemaphore(max(1, int(max_concurrency)))
        self.model = getattr(embeddings, "model", "")
        self.max_concurrency = max(1, int(max_concurrency))

    @property
    def backend_name(self) -> str:
        return str(getattr(self._inner, "backend_name", self.model) or self.model)

    def preload(self) -> None:
        with self._slots:
            preload = getattr(self._inner, "preload", None)
            if callable(preload):
                preload()

    def embed(self, text: str, *, is_query: bool = False) -> Any:
        with self._slots:
            embed_fn = self._inner.embed
            try:
                return embed_fn(text, is_query=is_query)
            except TypeError:
                return embed_fn(text)

    def embed_many(self, texts: list[str], *, is_query: bool = False) -> list[Any]:
        with self._slots:
            batch = getattr(self._inner, "embed_many", None)
            if callable(batch):
                return list(batch(texts, is_query=is_query))
            return [self._inner.embed(text, is_query=is_query) for text in texts]

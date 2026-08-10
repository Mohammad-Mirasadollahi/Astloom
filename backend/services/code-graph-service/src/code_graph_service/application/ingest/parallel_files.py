"""Cancel-aware parallel file work for ingest/sync."""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from typing import TypeVar

from code_graph_service.domain.errors import ClientDisconnected

T = TypeVar("T")

# After Ctrl+C / disconnect, do not block forever on hung LiteLLM/HTTP worker threads.
SHUTDOWN_GRACE_SEC = 15.0


def _shutdown_log(message: str) -> None:
    print(f"   →  {message}", flush=True)


def _cancel_pool(
    *,
    pool: ThreadPoolExecutor,
    futures: list[Future[None]],
    shutdown_grace_sec: float,
    reason: str,
) -> bool:
    """Cancel pending futures; return True if stuck workers were abandoned."""
    cancelled = 0
    for fut in futures:
        if fut.cancel():
            cancelled += 1
    in_flight = sum(1 for fut in futures if fut.running())
    _shutdown_log(
        f"Stopping sync ({reason}): cancelling {cancelled} queued file(s); "
        f"waiting up to {shutdown_grace_sec:g}s for {in_flight} still running"
    )
    _shutdown_log("Stopping sync: finishing in-progress workers")
    grace = max(0.0, float(shutdown_grace_sec))
    running = [fut for fut in futures if not fut.done()]
    if running and grace > 0:
        wait(running, timeout=grace)
    still = [fut for fut in futures if not fut.done()]
    pool.shutdown(wait=False, cancel_futures=True)
    if still:
        _shutdown_log(
            f"Stopping sync: abandoning {len(still)} stuck worker(s) "
            "(likely blocked in provider HTTP)"
        )
        return True
    _shutdown_log("Stopping sync: workers finished")
    return False


def run_parallel_file_jobs(
    *,
    workers: int,
    items: Sequence[T],
    fn: Callable[[int, T], None],
    shutdown_grace_sec: float = SHUTDOWN_GRACE_SEC,
    should_cancel: Callable[[], bool] | None = None,
) -> None:
    """Run ``fn(index, item)`` over ``items``.

    On ``KeyboardInterrupt`` or ``should_cancel()``: cancel pending futures, wait
    briefly for in-flight work, then abandon stuck workers so the CLI can exit
    (non-daemon pool threads would otherwise block until LiteLLM timeouts).
    HTTP disconnect uses ``ClientDisconnected`` and never ``os._exit``.
    """
    if not items:
        return
    workers = max(1, min(int(workers), len(items)))
    if workers == 1:
        for index, item in enumerate(items):
            if should_cancel is not None and should_cancel():
                raise ClientDisconnected()
            fn(index, item)
        return

    pool = ThreadPoolExecutor(max_workers=workers)
    futures: list[Future[None]] = []
    shut_down = False
    try:
        futures = [pool.submit(fn, index, item) for index, item in enumerate(items)]
        pending: set[Future[None]] = set(futures)
        while pending:
            if should_cancel is not None and should_cancel():
                raise ClientDisconnected()
            done, pending = wait(
                pending,
                timeout=0.25,
                return_when=FIRST_COMPLETED,
            )
            for fut in done:
                fut.result()
    except KeyboardInterrupt:
        shut_down = True
        abandoned = _cancel_pool(
            pool=pool,
            futures=futures,
            shutdown_grace_sec=shutdown_grace_sec,
            reason="Ctrl+C",
        )
        if abandoned:
            # Non-daemon ThreadPoolExecutor threads keep the interpreter alive otherwise.
            os._exit(130)
        raise
    except ClientDisconnected:
        shut_down = True
        _cancel_pool(
            pool=pool,
            futures=futures,
            shutdown_grace_sec=shutdown_grace_sec,
            reason="client disconnect",
        )
        raise
    finally:
        if not shut_down:
            pool.shutdown(wait=True, cancel_futures=False)

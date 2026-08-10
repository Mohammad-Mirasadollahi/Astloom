"""Run blocking push work until disconnect or explicit job cancel.

Role: bind long sync handlers to Starlette disconnect + ``X-Sync-Job-Id`` cancel.
SoT: cooperative ``should_cancel`` flag; explicit cancel POST is primary signal.
Invariants: work runs off the event loop (``asyncio.to_thread``); cancel is
  fail-closed — once set, the sync worker must stop starting new units;
  registry entries are scope-bound and never shared across jobs.
Allowed: raise ``ClientDisconnected`` from the worker when cancel fires.
Forbidden: blocking the event loop with sync ingest; cancelling sibling jobs.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from typing import TypeVar

from starlette.requests import Request

from code_graph_service.domain.errors import ClientDisconnected

from .job_cancel_registry import register_job, unregister_job

T = TypeVar("T")


async def watch_disconnect(
    request: Request,
    cancel: threading.Event,
    *,
    poll_sec: float = 0.2,
) -> None:
    """Set ``cancel`` once the client disconnects; returns once set by anyone."""
    while not cancel.is_set():
        try:
            if await request.is_disconnected():
                cancel.set()
                return
        except Exception:  # noqa: BLE001 — treat probe failures as still connected
            pass
        await asyncio.sleep(poll_sec)


def register_cancel(
    job_id: str | None,
    *,
    tenant_id: str | None = None,
    workspace_id: str | None = None,
    project_id: str | None = None,
) -> tuple[threading.Event, str | None]:
    """Bind a cancel flag to ``job_id`` (cancel-POST visible) or a local-only flag."""
    jid = str(job_id or "").strip() or None
    if jid:
        return (
            register_job(
                jid,
                tenant_id=str(tenant_id or ""),
                workspace_id=str(workspace_id or ""),
                project_id=str(project_id or ""),
            ),
            jid,
        )
    return threading.Event(), None


async def run_until_client_disconnect(
    request: Request,
    work: Callable[[Callable[[], bool]], T],
    *,
    job_id: str | None = None,
    tenant_id: str | None = None,
    workspace_id: str | None = None,
    project_id: str | None = None,
    poll_sec: float = 0.2,
) -> T:
    """Run ``work(should_cancel)`` in a thread; cancel on disconnect or job signal."""
    cancel, jid = register_cancel(
        job_id, tenant_id=tenant_id, workspace_id=workspace_id, project_id=project_id
    )

    watcher = asyncio.create_task(watch_disconnect(request, cancel, poll_sec=poll_sec))
    try:
        return await asyncio.to_thread(work, cancel.is_set)
    finally:
        cancel.set()
        if jid:
            unregister_job(jid, cancel)
        watcher.cancel()
        try:
            await watcher
        except asyncio.CancelledError:
            pass


__all__ = [
    "ClientDisconnected",
    "register_cancel",
    "run_until_client_disconnect",
    "watch_disconnect",
]

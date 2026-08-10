"""In-process registry of cancel Events for content-push jobs.

Role: map exact ``(scope, job_id)`` → cooperative cancel flag for one push.
SoT: process-local Events; cancel POST must match the same scope that registered.
Invariants: one live registration per job_id; unregister only the same Event object;
  unknown / wrong-scope cancel is a no-op (never touches other jobs).
Allowed: fail-closed cancel once set for that exact handle.
Forbidden: cancelling by scope alone; overwriting another in-flight job_id;
  wildcard / empty job_id cancel.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from code_graph_service.domain.errors import ConflictError, ValidationError


@dataclass(frozen=True, slots=True)
class JobHandle:
    event: threading.Event
    tenant_id: str
    workspace_id: str
    project_id: str


_lock = threading.Lock()
_jobs: dict[str, JobHandle] = {}


def _norm_job_id(job_id: str) -> str:
    jid = str(job_id or "").strip()
    if not jid:
        raise ValidationError("job_id is required")
    if len(jid) > 128:
        raise ValidationError("job_id exceeds 128 characters")
    return jid


def _norm_scope(tenant_id: str, workspace_id: str, project_id: str) -> tuple[str, str, str]:
    tenant = str(tenant_id or "").strip()
    workspace = str(workspace_id or "").strip()
    project = str(project_id or "").strip()
    if not tenant or not workspace or not project:
        raise ValidationError("tenant_id, workspace_id, and project_id are required")
    return tenant, workspace, project


def register_job(
    job_id: str,
    *,
    tenant_id: str,
    workspace_id: str,
    project_id: str,
) -> threading.Event:
    jid = _norm_job_id(job_id)
    tenant, workspace, project = _norm_scope(tenant_id, workspace_id, project_id)
    event = threading.Event()
    handle = JobHandle(
        event=event,
        tenant_id=tenant,
        workspace_id=workspace,
        project_id=project,
    )
    with _lock:
        existing = _jobs.get(jid)
        if existing is not None and not existing.event.is_set():
            raise ConflictError(f"sync job_id already in flight: {jid}")
        _jobs[jid] = handle
    return event


def cancel_job(
    job_id: str,
    *,
    tenant_id: str,
    workspace_id: str,
    project_id: str,
) -> bool:
    """Cancel only the exact in-flight job matching job_id + scope.

    Returns True when that handle was found and signalled. Wrong scope, missing
    job, or empty id never mutates other jobs.
    """
    try:
        jid = _norm_job_id(job_id)
        tenant, workspace, project = _norm_scope(tenant_id, workspace_id, project_id)
    except ValidationError:
        return False
    with _lock:
        handle = _jobs.get(jid)
        if handle is None:
            return False
        if (
            handle.tenant_id != tenant
            or handle.workspace_id != workspace
            or handle.project_id != project
        ):
            return False
        handle.event.set()
        return True


def unregister_job(job_id: str, event: threading.Event | None = None) -> None:
    """Drop registration for ``job_id`` only if it still points at ``event``."""
    try:
        jid = _norm_job_id(job_id)
    except ValidationError:
        return
    with _lock:
        handle = _jobs.get(jid)
        if handle is None:
            return
        if event is not None and handle.event is not event:
            return
        _jobs.pop(jid, None)


def clear_jobs_for_tests() -> None:
    with _lock:
        _jobs.clear()

"""Local Accept queue for the Astloom CLI (first GAP-004 surface)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from .modes import RouteDecision, decide_route, resolve_effective_mode


def _queue_path(state_root: Path, tenant_id: str, workspace_id: str, project_id: str) -> Path:
    return state_root / tenant_id / workspace_id / f"{project_id}.approvals.json"


def _load_queue(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"items": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ValueError(f"invalid approval queue: {path}")
    return data


def _save_queue(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def enqueue_gate(
    state_root: Path,
    *,
    tenant_id: str,
    workspace_id: str,
    project_id: str,
    subject_ref: str,
    subject_class: str = "",
    risk_level: str = "medium",
    actor: str = "cli",
    reason: str = "",
    project_state: dict[str, Any] | None = None,
    now_iso: str,
) -> dict[str, Any]:
    profile = resolve_effective_mode(project_state=project_state)
    decision: RouteDecision = decide_route(
        subject_class=subject_class,
        risk_level=risk_level,
        profile=profile,
    )
    item: dict[str, Any] = {
        "id": str(uuid4()),
        "tenant_id": tenant_id,
        "workspace_id": workspace_id,
        "project_id": project_id,
        "subject_ref": subject_ref,
        "subject_class": subject_class,
        "risk_level": risk_level,
        "status": "pending",
        "actor_id": actor,
        "reason": reason,
        "mode_effective": decision.mode_effective,
        "route_decision": decision.to_dict(),
        "created_at": now_iso,
        "updated_at": now_iso,
        "resolved_by": None,
        "resolution": None,
        "decision_reason": None,
    }
    if decision.route == "auto":
        item["status"] = "approved"
        item["resolved_by"] = "system:auto_approve"
        item["resolution"] = "accepted"
        item["decision_reason"] = decision.reason
        item["updated_at"] = now_iso
    path = _queue_path(state_root, tenant_id, workspace_id, project_id)
    data = _load_queue(path)
    data["items"].append(item)
    _save_queue(path, data)
    return item


def list_pending(
    state_root: Path,
    *,
    tenant_id: str,
    workspace_id: str,
    project_id: str,
    include_resolved: bool = False,
) -> list[dict[str, Any]]:
    return list_gates(
        state_root,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        project_id=project_id,
        include_resolved=include_resolved,
    )


def get_gate(
    state_root: Path,
    *,
    tenant_id: str,
    workspace_id: str,
    project_id: str,
    approval_id: str,
) -> dict[str, Any]:
    path = _queue_path(state_root, tenant_id, workspace_id, project_id)
    for item in _load_queue(path).get("items") or []:
        if str(item.get("id")) == approval_id:
            return item
    raise KeyError(f"approval not found: {approval_id}")


def list_gates(
    state_root: Path,
    *,
    tenant_id: str,
    workspace_id: str,
    project_id: str,
    include_resolved: bool = False,
    approval_id: str | None = None,
    subject_ref: str | None = None,
    status: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> list[dict[str, Any]]:
    """List Accept gates with optional id / subject / status / time filters.

    Time filters compare against ``created_at`` (ISO). ``since``/``until`` or an
    explicit ``approval_id``/``status`` implies full history (not pending-only).
    """
    path = _queue_path(state_root, tenant_id, workspace_id, project_id)
    items = list(_load_queue(path).get("items") or [])
    want_history = bool(
        include_resolved
        or approval_id
        or status
        or since
        or until
        or subject_ref
    )
    if not want_history:
        items = [item for item in items if item.get("status") == "pending"]
    if approval_id:
        items = [item for item in items if str(item.get("id")) == approval_id]
    if subject_ref:
        items = [item for item in items if str(item.get("subject_ref") or "") == subject_ref]
    if status:
        items = [item for item in items if str(item.get("status") or "") == status]
    if since:
        items = [item for item in items if str(item.get("created_at") or "") >= since]
    if until:
        items = [item for item in items if str(item.get("created_at") or "") <= until]
    items.sort(key=lambda item: str(item.get("created_at") or ""))
    return items


def _resolve(
    state_root: Path,
    *,
    tenant_id: str,
    workspace_id: str,
    project_id: str,
    approval_id: str,
    status: str,
    actor: str,
    reason: str,
    now_iso: str,
) -> dict[str, Any]:
    path = _queue_path(state_root, tenant_id, workspace_id, project_id)
    data = _load_queue(path)
    for item in data["items"]:
        if str(item.get("id")) != approval_id:
            continue
        if item.get("status") != "pending":
            raise ValueError(f"approval is not pending: {approval_id}")
        item["status"] = status
        item["resolved_by"] = actor
        item["resolution"] = "accepted" if status == "approved" else "rejected"
        item["decision_reason"] = reason
        item["updated_at"] = now_iso
        _save_queue(path, data)
        return item
    raise KeyError(f"approval not found: {approval_id}")


def accept_gate(
    state_root: Path,
    *,
    tenant_id: str,
    workspace_id: str,
    project_id: str,
    approval_id: str,
    actor: str,
    reason: str,
    now_iso: str,
) -> dict[str, Any]:
    return _resolve(
        state_root,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        project_id=project_id,
        approval_id=approval_id,
        status="approved",
        actor=actor,
        reason=reason,
        now_iso=now_iso,
    )


def reject_gate(
    state_root: Path,
    *,
    tenant_id: str,
    workspace_id: str,
    project_id: str,
    approval_id: str,
    actor: str,
    reason: str,
    now_iso: str,
) -> dict[str, Any]:
    return _resolve(
        state_root,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        project_id=project_id,
        approval_id=approval_id,
        status="rejected",
        actor=actor,
        reason=reason,
        now_iso=now_iso,
    )

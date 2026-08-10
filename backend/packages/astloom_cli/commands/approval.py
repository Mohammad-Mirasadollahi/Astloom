"""CLI: first human Accept surface (GAP-004)."""

from __future__ import annotations

import argparse
from pathlib import Path

import astloom_cli.state as state
from astloom_cli.util import now_iso, print_json, repo_root, require_scope


def _state_root() -> Path:
    return state.default_state_root(repo_root())


def cmd_approval_mode_show(args: argparse.Namespace) -> int:
    from approval_modes import resolve_effective_mode

    tenant, workspace, project = require_scope(args, with_defaults=True)
    project_state = state.load_project(_state_root(), tenant, workspace, project)
    profile = resolve_effective_mode(project_state=project_state)
    print_json(profile)
    return 0


def cmd_approval_mode_set(args: argparse.Namespace) -> int:
    from approval_modes import save_mode_override

    tenant, workspace, project = require_scope(args, with_defaults=True)
    root = _state_root()
    project_state = state.load_project(root, tenant, workspace, project)
    if project_state is None:
        raise SystemExit(
            f"error: project not registered ({tenant}/{workspace}/{project}); run: astloom project register …"
        )
    actor = str(getattr(args, "actor", "") or "cli").strip() or "cli"
    save_mode_override(project_state, args.mode, actor=actor)
    state.save_project(root, project_state)
    print_json(project_state.get("approval_mode_profile") or {"mode": args.mode})
    return 0


def cmd_approval_queue(args: argparse.Namespace) -> int:
    from approval_modes import list_gates
    from astloom_cli.mcp_token_report import parse_time_range

    tenant, workspace, project = require_scope(args, with_defaults=True)
    status = str(getattr(args, "status", "") or "").strip()
    if status and status not in {"pending", "approved", "rejected"}:
        raise SystemExit("error: --status must be pending, approved, or rejected")
    since_raw = str(getattr(args, "since", "") or "").strip() or None
    until_raw = str(getattr(args, "until", "") or "").strip() or None
    since_iso = until_iso = None
    if since_raw or until_raw:
        tr = parse_time_range(since_raw, until_raw)
        since_iso = tr.start.isoformat().replace("+00:00", "Z")
        until_iso = tr.end.isoformat().replace("+00:00", "Z")
    items = list_gates(
        _state_root(),
        tenant_id=tenant,
        workspace_id=workspace,
        project_id=project,
        include_resolved=bool(getattr(args, "all", False)),
        approval_id=str(getattr(args, "id", "") or "").strip() or None,
        subject_ref=str(getattr(args, "subject_ref", "") or "").strip() or None,
        status=status or None,
        since=since_iso,
        until=until_iso,
    )
    print_json(
        {
            "count": len(items),
            "filters": {
                "id": str(getattr(args, "id", "") or "") or None,
                "subject_ref": str(getattr(args, "subject_ref", "") or "") or None,
                "status": status or None,
                "since": since_iso,
                "until": until_iso,
                "all": bool(getattr(args, "all", False)),
            },
            "items": items,
        }
    )
    return 0


def cmd_approval_show(args: argparse.Namespace) -> int:
    from approval_modes import get_gate

    tenant, workspace, project = require_scope(args, with_defaults=True)
    try:
        item = get_gate(
            _state_root(),
            tenant_id=tenant,
            workspace_id=workspace,
            project_id=project,
            approval_id=args.approval_id,
        )
    except KeyError as exc:
        raise SystemExit(f"error: {exc}") from exc
    print_json(item)
    return 0


def cmd_approval_enqueue(args: argparse.Namespace) -> int:
    from approval_modes import enqueue_gate

    tenant, workspace, project = require_scope(args, with_defaults=True)
    root = _state_root()
    project_state = state.load_project(root, tenant, workspace, project)
    item = enqueue_gate(
        root,
        tenant_id=tenant,
        workspace_id=workspace,
        project_id=project,
        subject_ref=args.subject_ref,
        subject_class=args.subject_class or "",
        risk_level=args.risk_level or "medium",
        actor=str(getattr(args, "actor", "") or "cli"),
        reason=args.reason or "",
        project_state=project_state,
        now_iso=now_iso(),
    )
    print_json(item)
    return 0


def cmd_approval_accept(args: argparse.Namespace) -> int:
    from approval_modes import accept_gate

    tenant, workspace, project = require_scope(args, with_defaults=True)
    item = accept_gate(
        _state_root(),
        tenant_id=tenant,
        workspace_id=workspace,
        project_id=project,
        approval_id=args.approval_id,
        actor=str(getattr(args, "actor", "") or "cli"),
        reason=args.reason or "accepted",
        now_iso=now_iso(),
    )
    print_json(item)
    return 0


def cmd_approval_reject(args: argparse.Namespace) -> int:
    from approval_modes import reject_gate

    tenant, workspace, project = require_scope(args, with_defaults=True)
    item = reject_gate(
        _state_root(),
        tenant_id=tenant,
        workspace_id=workspace,
        project_id=project,
        approval_id=args.approval_id,
        actor=str(getattr(args, "actor", "") or "cli"),
        reason=args.reason or "rejected",
        now_iso=now_iso(),
    )
    print_json(item)
    return 0

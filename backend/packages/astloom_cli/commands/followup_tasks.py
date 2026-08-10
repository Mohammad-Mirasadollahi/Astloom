"""CLI: list / reconcile / purge automated follow-up Tasks."""

from __future__ import annotations

import argparse
from types import SimpleNamespace
from uuid import uuid4

from astloom_cli.followup_task_lifecycle import (
    ORIGIN_QUALITY,
    ORIGIN_SYNC,
    OPEN_STATUSES,
    RETENTION_CLASS,
    TERMINAL_STATUSES,
    adopt_legacy_quality_tasks,
    collect_active_fingerprints,
    expand_active_for_incomplete_audits,
    list_automated_followup_tasks,
    open_platform_backends,
    purge_terminal_automated_followup_tasks,
    reconcile_automated_followup_tasks,
    retention_days,
    terminal_purge_candidates,
)
from astloom_cli.util import print_json, require_scope


def _scope_ns(args: argparse.Namespace) -> SimpleNamespace:
    tenant, workspace, project = require_scope(args, with_defaults=True)
    return SimpleNamespace(tenant_id=tenant, workspace_id=workspace, project_id=project)


def _origin_set(raw: str) -> frozenset[str] | None:
    text = str(raw or "all").strip().lower()
    if text in {"", "all"}:
        return None
    if text in {"sync", "sync-followup"}:
        return frozenset({ORIGIN_SYNC})
    if text in {"quality", "mcp-quality"}:
        return frozenset({ORIGIN_QUALITY})
    raise SystemExit(
        "error: --origin must be all, sync-followup (sync), or mcp-quality (quality)"
    )


def _status_group(raw: str) -> str:
    text = str(raw or "all").strip().lower()
    if text not in {"all", "open", "terminal"}:
        raise SystemExit("error: --status must be all, open, or terminal")
    return text


def _summarize(tasks: list[dict]) -> dict[str, int]:
    by_status: dict[str, int] = {}
    by_origin: dict[str, int] = {}
    open_n = terminal_n = 0
    for row in tasks:
        status = str(row.get("status") or "")
        by_status[status] = by_status.get(status, 0) + 1
        if status in OPEN_STATUSES:
            open_n += 1
        if status in TERMINAL_STATUSES:
            terminal_n += 1
        data = row.get("data") if isinstance(row.get("data"), dict) else {}
        origin = str(data.get("origin") or "")
        by_origin[origin] = by_origin.get(origin, 0) + 1
    return {
        "total": len(tasks),
        "open": open_n,
        "terminal": terminal_n,
        "by_status": by_status,
        "by_origin": by_origin,
    }


def cmd_followup_tasks_adopt_legacy(args: argparse.Namespace) -> int:
    scope = _scope_ns(args)
    dry_run = bool(getattr(args, "dry_run", False))
    if not dry_run and not bool(getattr(args, "yes", False)):
        raise SystemExit("error: adopt-legacy requires --yes (or use --dry-run)")
    backends = None
    try:
        backends, core_scope, scope_dict = open_platform_backends(scope)
        result = adopt_legacy_quality_tasks(
            backends.core,
            scope=core_scope,
            actor=str(getattr(args, "actor", "") or "astloom-cli-followup"),
            correlation_id=f"cli-followup-adopt-{uuid4()}",
            dry_run=dry_run,
        )
        print_json({"scope": scope_dict, **result})
        return 1 if result.get("errors") else 0
    finally:
        if backends is not None:
            try:
                backends.close()
            except Exception:  # noqa: BLE001
                pass


def cmd_followup_tasks_list(args: argparse.Namespace) -> int:
    scope = _scope_ns(args)
    backends = None
    try:
        backends, core_scope, scope_dict = open_platform_backends(scope)
        tasks = list_automated_followup_tasks(
            backends.core,
            scope=core_scope,
            origins=_origin_set(getattr(args, "origin", "all")),
            status_group=_status_group(getattr(args, "status", "all")),
        )
        print_json(
            {
                "scope": scope_dict,
                "count": len(tasks),
                "summary": _summarize(tasks),
                "tasks": tasks,
            }
        )
        return 0
    finally:
        if backends is not None:
            try:
                backends.close()
            except Exception:  # noqa: BLE001
                pass


def cmd_followup_tasks_status(args: argparse.Namespace) -> int:
    scope = _scope_ns(args)
    backends = None
    try:
        backends, core_scope, scope_dict = open_platform_backends(scope)
        tasks = list_automated_followup_tasks(
            backends.core,
            scope=core_scope,
            origins=_origin_set(getattr(args, "origin", "all")),
            status_group="all",
        )
        active = collect_active_fingerprints(
            include_sync=True,
            include_quality=True,
        )
        open_fps = {
            str((t.get("data") or {}).get("fingerprint") or "")
            for t in tasks
            if str(t.get("status") or "") in OPEN_STATUSES
        }
        open_fps.discard("")
        active, quality_incomplete = expand_active_for_incomplete_audits(
            active, open_fingerprints=open_fps
        )
        print_json(
            {
                "scope": scope_dict,
                "retention_days": retention_days(),
                "summary": _summarize(tasks),
                "active_fingerprints": sorted(active),
                "open_fingerprints": sorted(open_fps),
                "stale_open_fingerprints": sorted(open_fps - active),
                "quality_audit_incomplete": quality_incomplete,
            }
        )
        return 0
    finally:
        if backends is not None:
            try:
                backends.close()
            except Exception:  # noqa: BLE001
                pass


def cmd_followup_tasks_reconcile(args: argparse.Namespace) -> int:
    scope = _scope_ns(args)
    origins = _origin_set(getattr(args, "origin", "all"))
    include_sync = origins is None or ORIGIN_SYNC in origins
    include_quality = origins is None or ORIGIN_QUALITY in origins
    active = collect_active_fingerprints(
        include_sync=include_sync,
        include_quality=include_quality,
    )
    dry_run = bool(getattr(args, "dry_run", False))
    backends = None
    try:
        backends, core_scope, scope_dict = open_platform_backends(scope)
        open_tasks = list_automated_followup_tasks(
            backends.core,
            scope=core_scope,
            origins=origins,
            status_group="open",
        )
        open_fps = {
            str((t.get("data") or {}).get("fingerprint") or "")
            for t in open_tasks
        }
        open_fps.discard("")
        active, quality_incomplete = expand_active_for_incomplete_audits(
            active, open_fingerprints=open_fps
        )
        if dry_run:
            would_cancel = [
                {
                    "id": t.get("id"),
                    "title": (t.get("data") or {}).get("title"),
                    "fingerprint": (t.get("data") or {}).get("fingerprint"),
                    "origin": (t.get("data") or {}).get("origin"),
                }
                for t in open_tasks
                if str((t.get("data") or {}).get("fingerprint") or "") not in active
                and str((t.get("data") or {}).get("fingerprint") or "").strip()
            ]
            print_json(
                {
                    "dry_run": True,
                    "scope": scope_dict,
                    "active_fingerprints": sorted(active),
                    "quality_audit_incomplete": quality_incomplete,
                    "would_cancel_count": len(would_cancel),
                    "would_cancel": would_cancel,
                }
            )
            return 0
        result = reconcile_automated_followup_tasks(
            backends.core,
            scope=core_scope,
            actor=str(getattr(args, "actor", "") or "astloom-cli-followup"),
            correlation_id=f"cli-followup-reconcile-{uuid4()}",
            active_fingerprints=active,
            origins=origins,
        )
        print_json(
            {
                "dry_run": False,
                "scope": scope_dict,
                "active_fingerprints": sorted(active),
                "quality_audit_incomplete": quality_incomplete,
                **result,
            }
        )
        return 1 if result.get("errors") else 0
    finally:
        if backends is not None:
            try:
                backends.close()
            except Exception:  # noqa: BLE001
                pass


def cmd_followup_tasks_purge(args: argparse.Namespace) -> int:
    scope = _scope_ns(args)
    days = getattr(args, "days", None)
    retention = retention_days() if days is None else max(0, int(days))
    dry_run = bool(getattr(args, "dry_run", False))
    if not dry_run and not bool(getattr(args, "yes", False)):
        raise SystemExit("error: purge requires --yes (or use --dry-run)")
    backends = None
    try:
        backends, core_scope, scope_dict = open_platform_backends(scope)
        if dry_run:
            would = [
                {
                    "id": task.id,
                    "status": task.status,
                    "updated_at": task.updated_at,
                    "fingerprint": (task.data or {}).get("fingerprint"),
                }
                for task in terminal_purge_candidates(
                    backends.core,
                    scope=core_scope,
                    retention_days_value=retention,
                )
            ]
            print_json(
                {
                    "dry_run": True,
                    "scope": scope_dict,
                    "retention_days": retention,
                    "retention_class": RETENTION_CLASS,
                    "would_purge_count": len(would),
                    "would_purge": would,
                }
            )
            return 0
        result = purge_terminal_automated_followup_tasks(
            backends.core,
            scope=core_scope,
            actor=str(getattr(args, "actor", "") or "astloom-cli-followup"),
            correlation_id=f"cli-followup-purge-{uuid4()}",
            retention_days_value=retention,
        )
        print_json({"dry_run": False, "scope": scope_dict, **result})
        return 1 if result.get("errors") else 0
    finally:
        if backends is not None:
            try:
                backends.close()
            except Exception:  # noqa: BLE001
                pass

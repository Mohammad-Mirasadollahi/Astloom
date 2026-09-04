"""Quality-audit MCP handlers (docs + code debt for coding agents)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from .platform import PlatformBackends


def quality_audit(
    backends: PlatformBackends,
    arguments: dict[str, Any],
    *,
    scope: dict[str, str],
    correlation_id: str,
    base: dict[str, Any],
) -> dict[str, Any]:
    """Return compact quality-audit findings; optionally create durable follow-up tasks."""
    from astloom_cli.commands.quality_audit.collect import build_quality_audit_report
    from astloom_cli.commands.quality_audit.mcp_payload import compact_quality_audit_payload
    from astloom_cli.followup_task_lifecycle import (
        ORIGIN_QUALITY,
        create_automated_followup_task,
        purge_terminal_automated_followup_tasks,
        quality_fingerprint,
        reconcile_automated_followup_tasks,
        retention_days,
    )

    top_n = int(arguments.get("top_n") or 25)
    top_n = max(1, min(top_n, 100))
    severities_raw = arguments.get("severities")
    severities: list[str] | None = None
    if isinstance(severities_raw, list):
        severities = [str(x).strip().lower() for x in severities_raw if str(x).strip()]
    elif isinstance(severities_raw, str) and severities_raw.strip():
        severities = [p.strip().lower() for p in severities_raw.split(",") if p.strip()]

    docs_registry_hygiene: dict[str, Any] = {
        "deleted_count": 0,
        "deleted": [],
        "errors": [],
    }
    try:
        from astloom_cli.docs_registry_hygiene import purge_docs_registry_fixture_noise

        docs_registry_hygiene = purge_docs_registry_fixture_noise(
            backends.docs,
            backends.docs_scope(scope),
        )
    except Exception as exc:  # noqa: BLE001 — audit must still return
        docs_registry_hygiene = {
            "deleted_count": 0,
            "deleted": [],
            "errors": [f"{type(exc).__name__}: {exc}"],
        }

    from pathlib import Path

    from astloom_cli.software_paths import software_paths_for_project

    pinned = software_paths_for_project(
        str(scope.get("tenant_id") or ""),
        str(scope.get("workspace_id") or ""),
        str(scope.get("project_id") or ""),
        must_exist=False,
    )
    if not pinned:
        return {
            **base,
            "ok": False,
            "error": (
                "no software paths pinned for this MCP project; "
                "run `astloom paths add /path/to/app` (or init --path) on the Astloom host"
            ),
            "repo": None,
            "repos": [],
            "scope": scope,
            "findings": [],
            "findings_total": 0,
            "docs_registry_hygiene": docs_registry_hygiene,
            "tasks_created": [],
            "tasks_created_count": 0,
        }

    report = build_quality_audit_report(repos=[Path(p) for p in pinned])
    payload = compact_quality_audit_payload(
        report,
        top_n=top_n,
        severities=severities,
    )

    created: list[dict[str, Any]] = []
    tasks_canceled = 0
    tasks_purged = 0
    create_errors: list[str] = []
    reconcile_errors: list[str] = []
    purge_errors: list[str] = []

    create_tasks = bool(arguments.get("create_tasks"))
    reconcile_tasks = bool(arguments.get("reconcile_tasks")) or create_tasks
    findings = list(payload.get("findings") or [])
    active: set[str] = set()
    for row in findings:
        severity = str(row.get("severity") or "").lower()
        if severity not in {"high", "medium"}:
            continue
        category = str(row.get("category") or "quality")
        path = str(row.get("path") or "").strip() or "(unknown)"
        active.add(quality_fingerprint(category, path))

    if create_tasks:
        created, create_errors = _create_tasks_for_findings(
            backends,
            findings=findings,
            scope=scope,
            correlation_id=correlation_id,
        )

    if reconcile_tasks:
        try:
            recon = reconcile_automated_followup_tasks(
                backends.core,
                scope=backends.core_scope(scope),
                actor=backends.actor_id,
                correlation_id=correlation_id or str(uuid4()),
                active_fingerprints=active,
                origins={ORIGIN_QUALITY},
            )
            tasks_canceled = int(recon.get("tasks_canceled") or 0)
            reconcile_errors.extend(str(e) for e in (recon.get("errors") or []))
            purged = purge_terminal_automated_followup_tasks(
                backends.core,
                scope=backends.core_scope(scope),
                actor=backends.actor_id,
                correlation_id=correlation_id or str(uuid4()),
                retention_days_value=retention_days(),
            )
            tasks_purged = int(purged.get("tasks_purged") or 0)
            purge_errors.extend(str(e) for e in (purged.get("errors") or []))
        except Exception as exc:  # noqa: BLE001
            reconcile_errors.append(f"{type(exc).__name__}: {exc}")

    return {
        **base,
        "ok": True,
        **payload,
        "docs_registry_hygiene": docs_registry_hygiene,
        "tasks_created": created,
        "tasks_created_count": len(created),
        "tasks_canceled": tasks_canceled,
        "tasks_purged": tasks_purged,
        "create_errors": create_errors,
        "reconcile_errors": reconcile_errors,
        "purge_errors": purge_errors,
        "origin": ORIGIN_QUALITY,
    }


def _create_tasks_for_findings(
    backends: PlatformBackends,
    *,
    findings: list[dict[str, Any]],
    scope: dict[str, str],
    correlation_id: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    """One durable task per high/medium finding path (stable fingerprint key)."""
    from astloom_cli.followup_task_lifecycle import (
        ORIGIN_QUALITY,
        create_automated_followup_task,
        quality_fingerprint,
    )

    out: list[dict[str, Any]] = []
    errors: list[str] = []
    project_id = str(scope.get("project_id") or "astloom")
    core_scope = backends.core_scope(scope)
    for row in findings:
        severity = str(row.get("severity") or "").lower()
        if severity not in {"high", "medium"}:
            continue
        category = str(row.get("category") or "quality")
        path = str(row.get("path") or "").strip() or "(unknown)"
        title = f"Quality: {category} — {path}"
        instructions = (
            f"Remediate Astloom quality finding.\n"
            f"category={category}\n"
            f"severity={severity}\n"
            f"path={path}\n"
            f"detail={row.get('detail') or ''}\n"
            f"fix_hint={row.get('fix_hint') or ''}\n"
            f"Use skill astloom-quality-audit / astloom-standards-on-edit."
        )
        fingerprint = quality_fingerprint(category, path)
        try:
            public = create_automated_followup_task(
                backends.core,
                scope=core_scope,
                actor=backends.actor_id,
                correlation_id=correlation_id,
                project_id=project_id,
                title=title,
                instructions=instructions,
                origin=ORIGIN_QUALITY,
                followup_kind=category,
                paths=[path],
                fingerprint=fingerprint,
                acceptance_criteria=[
                    "Finding cleared in astloom_quality_audit",
                    "Tests pass when code changed",
                ],
            )
            out.append(public)
        except Exception as exc:  # noqa: BLE001 — best-effort; audit payload still returns
            errors.append(f"{fingerprint}: {type(exc).__name__}: {exc}")
    return out, errors

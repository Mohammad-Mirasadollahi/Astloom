"""After sync standards gate: durable follow-up tasks for skipped/stale debt.

Module contract:
- Role: turn skipped nonconforming docs (and optional quality code debt) into
  CoreData tasks + a local JSON mirror; reconcile/purge per
  as.doc.core.automated-followup-task-lifecycle-and-retention.
- Source of truth: standards_gate skipped paths; optional quality-audit code rows;
  CoreData for durable Task lifecycle.
- Failures: store/create/reconcile/purge are best-effort — never fail sync;
  surface create_errors / reconcile_errors / purge_errors.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from astloom_cli.followup_task_lifecycle import (
    ORIGIN_SYNC,
    create_automated_followup_task,
    open_platform_backends,
    purge_terminal_automated_followup_tasks,
    reconcile_automated_followup_tasks,
    retention_days,
    sync_fingerprint,
)
from astloom_cli.util import now_iso, repo_root


def _write_mirror(rows: list[dict[str, Any]]) -> Path:
    base = Path(repo_root()).resolve() / ".astloom"
    base.mkdir(parents=True, exist_ok=True)
    path = base / "quality-followup-tasks.json"
    payload = {
        "generated_at": now_iso(),
        "count": len(rows),
        "tasks": rows,
        "agent_instruction": (
            "Remediate listed paths (skill astloom-quality-audit / "
            "astloom-standards-on-edit), then re-run astloom_quality_audit / sync."
        ),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def create_sync_followup_tasks(
    *,
    scope: Any,
    standards_gate: Any,
    include_code_audit: bool = True,
) -> dict[str, Any]:
    """Create follow-up tasks for skipped docs (+ optional stale/never-ingested code)."""
    specs: list[dict[str, Any]] = []
    skipped_docs = list(getattr(standards_gate, "skipped_docs", None) or [])
    skipped_code = list(getattr(standards_gate, "skipped_code", None) or [])

    if skipped_docs:
        paths = "\n".join(f"- {p}" for p in skipped_docs[:40])
        more = len(skipped_docs) - 40
        if more > 0:
            paths += f"\n- … and {more} more"
        specs.append(
            {
                "kind": "docs.standards_skipped",
                "title": f"Remediate {len(skipped_docs)} sync-skipped nonconforming doc(s)",
                "instructions": (
                    "These paths failed Full-tier docs-standards and were excluded from sync.\n"
                    "Fix with astloom-standards-on-edit / docs remediator, then re-sync.\n"
                    f"{paths}"
                ),
                "paths": skipped_docs,
            }
        )
    if skipped_code:
        specs.append(
            {
                "kind": "code.standards_skipped",
                "title": f"Remediate {len(skipped_code)} sync-skipped code path(s)",
                "instructions": (
                    "Code paths excluded by the standards gate — remediate then re-sync.\n"
                    + "\n".join(f"- {p}" for p in skipped_code[:40])
                ),
                "paths": skipped_code,
            }
        )

    create_errors: list[str] = []
    code_sync_debt_evaluated = False
    if include_code_audit:
        try:
            from astloom_cli.commands.quality_audit.collect import build_quality_audit_report

            report = build_quality_audit_report()
            never = [
                f["path"]
                for f in report.get("findings") or []
                if f.get("category") == "code.never_ingested"
            ]
            stale = [
                f["path"]
                for f in report.get("findings") or []
                if f.get("category") == "code.stale_edited"
            ]
            code_sync_debt_evaluated = True
            if never or stale:
                specs.append(
                    {
                        "kind": "code.sync_debt",
                        "title": (
                            f"Code graph debt: {len(never)} never-ingested, "
                            f"{len(stale)} stale-edited"
                        ),
                        "instructions": (
                            "Run astloom sync (AST-only ok if cloud LLM blocked) for:\n"
                            "Never ingested:\n"
                            + "\n".join(f"- {p}" for p in never[:30])
                            + "\nStale edited:\n"
                            + "\n".join(f"- {p}" for p in stale[:30])
                        ),
                        "paths": never + stale,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            create_errors.append(f"code_audit: {type(exc).__name__}: {exc}")

    created: list[dict[str, Any]] = []
    reconcile_errors: list[str] = []
    purge_errors: list[str] = []
    mirrored: list[dict[str, Any]] = []
    project = str(getattr(scope, "project_id", "") or "astloom")
    active: set[str] = set()
    for spec in specs:
        mirrored.append(spec)
        fp = sync_fingerprint(str(spec["kind"]))
        active.add(fp)
    if not code_sync_debt_evaluated:
        # Unknown or out-of-scope: keep code.sync_debt open during reconcile.
        active.add(sync_fingerprint("code.sync_debt"))

    tasks_canceled = 0
    tasks_purged = 0
    docs_registry_hygiene: dict[str, Any] = {
        "deleted_count": 0,
        "deleted": [],
        "errors": [],
    }
    backends = None
    try:
        backends, core_scope, scope_dict = open_platform_backends(scope)
        try:
            from astloom_cli.docs_registry_hygiene import purge_docs_registry_fixture_noise

            docs_registry_hygiene = purge_docs_registry_fixture_noise(
                backends.docs,
                backends.docs_scope(scope_dict),
            )
        except Exception as exc:  # noqa: BLE001 — never fail sync
            docs_registry_hygiene = {
                "deleted_count": 0,
                "deleted": [],
                "errors": [f"{type(exc).__name__}: {exc}"],
            }
        corr = f"cli-sync-followup-{uuid4()}"
        for spec in specs:
            fp = sync_fingerprint(str(spec["kind"]))
            try:
                public = create_automated_followup_task(
                    backends.core,
                    scope=core_scope,
                    actor="astloom-cli-sync",
                    correlation_id=corr,
                    project_id=project,
                    title=str(spec["title"]),
                    instructions=str(spec["instructions"]),
                    origin=ORIGIN_SYNC,
                    followup_kind=str(spec["kind"]),
                    paths=list(spec.get("paths") or []),
                    fingerprint=fp,
                )
                created.append(public)
            except Exception as exc:  # noqa: BLE001
                create_errors.append(f"{spec['kind']}: {type(exc).__name__}: {exc}")

        recon = reconcile_automated_followup_tasks(
            backends.core,
            scope=core_scope,
            actor="astloom-cli-sync",
            correlation_id=corr,
            active_fingerprints=active,
            origins={ORIGIN_SYNC},
        )
        tasks_canceled = int(recon.get("tasks_canceled") or 0)
        reconcile_errors.extend(str(e) for e in (recon.get("errors") or []))

        purged = purge_terminal_automated_followup_tasks(
            backends.core,
            scope=core_scope,
            actor="astloom-cli-sync",
            correlation_id=corr,
            retention_days_value=retention_days(),
        )
        tasks_purged = int(purged.get("tasks_purged") or 0)
        purge_errors.extend(str(e) for e in (purged.get("errors") or []))
    except Exception as exc:  # noqa: BLE001
        create_errors.append(f"platform: {type(exc).__name__}: {exc}")
    finally:
        if backends is not None:
            try:
                backends.close()
            except Exception:  # noqa: BLE001
                pass

    mirror_path = _write_mirror(mirrored)
    return {
        "ok": True,
        "specs_count": len(specs),
        "tasks_created_count": len(created),
        "tasks_created": created,
        "tasks_canceled": tasks_canceled,
        "tasks_purged": tasks_purged,
        "create_errors": create_errors,
        "reconcile_errors": reconcile_errors,
        "purge_errors": purge_errors,
        "docs_registry_hygiene": docs_registry_hygiene,
        "mirror_path": str(mirror_path),
        "specs": mirrored,
        "active_fingerprints": sorted(active),
    }

"""Automated follow-up Task identity, reconcile, and retention.

Module contract:
- Role: stable fingerprints + cancel-when-cleared + terminal purge for
  sync/quality automated Tasks (as.doc.core.automated-followup-task-lifecycle-and-retention).
- Source of truth: CoreData Task records with retention_class=automated_followup.
- Allowed: best-effort create/reconcile/purge; never fail caller sync/audit.
- Forbidden: applying Memory decay; purging Tasks without automated_followup class.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

RETENTION_CLASS = "automated_followup"
ORIGIN_SYNC = "sync-followup"
ORIGIN_QUALITY = "mcp-quality"
CANCEL_REASON = "finding_cleared"
DEFAULT_RETENTION_DAYS = 30
QUALITY_AUDIT_INCOMPLETE_MARKER = f"{ORIGIN_QUALITY}:__audit_incomplete__"

OPEN_STATUSES = frozenset(
    {"proposed", "ready", "in_progress", "blocked", "review", "reopened"}
)
TERMINAL_STATUSES = frozenset({"done", "canceled"})


def ensure_platform_imports() -> None:
    """Make core-data + MCP platform backends importable from the CLI process."""
    import sys
    from pathlib import Path

    from astloom_cli.cli_defaults import load_dotenv_files
    from astloom_cli.util import repo_root

    root = Path(repo_root()).resolve()
    load_dotenv_files(root=root)
    try:
        from astloom_cli.remote_client import apply_compose_env_to_os
        import os

        apply_compose_env_to_os(os.environ, root)
    except Exception:  # noqa: BLE001
        pass
    for rel in (
        ("backend", "services", "mcp-gateway-service", "src"),
        ("backend", "services", "core-data-service", "src"),
        ("backend", "services", "memory-service", "src"),
        ("backend", "services", "code-graph-service", "src"),
        ("backend", "services", "docs-sync-service", "src"),
        ("backend", "services", "common-context-service", "src"),
        ("backend", "packages"),
    ):
        path = root.joinpath(*rel)
        text = str(path)
        if path.is_dir() and text not in sys.path:
            sys.path.insert(0, text)


def open_platform_backends(scope: Any) -> tuple[Any, Any, dict[str, str]]:
    """Return ``(backends, core_scope, scope_dict)`` for follow-up Task operations."""
    ensure_platform_imports()
    from mcp_gateway_service.backends.platform import PlatformBackends

    backends = PlatformBackends.from_env()
    scope_dict = {
        "tenant_id": str(getattr(scope, "tenant_id", "") or "astloom"),
        "workspace_id": str(getattr(scope, "workspace_id", "") or "dev"),
        "project_id": str(getattr(scope, "project_id", "") or "astloom"),
    }
    return backends, backends.core_scope(scope_dict), scope_dict


def collect_active_fingerprints(
    *,
    include_sync: bool = True,
    include_quality: bool = True,
    root_path: Any | None = None,
) -> set[str]:
    """Build active debt fingerprints from current gate + quality-audit findings."""
    active: set[str] = set()
    if include_sync:
        try:
            from pathlib import Path

            from astloom_cli.sync_config import resolve_sync_filters
            from astloom_cli.sync_standards_gate import resolve_standards_gate
            from astloom_cli.util import repo_root

            root = Path(root_path) if root_path is not None else Path(repo_root())
            filters = resolve_sync_filters(root=root)
            filters = {**filters, "max_files": int(filters.get("max_files") or 2000)}
            _, gate = resolve_standards_gate(
                root_path=root,
                filters=filters,
                skip_nonconforming=True,
                sync_nonconforming=False,
            )
            if list(getattr(gate, "skipped_docs", None) or []):
                active.add(sync_fingerprint("docs.standards_skipped"))
            if list(getattr(gate, "skipped_code", None) or []):
                active.add(sync_fingerprint("code.standards_skipped"))
            try:
                from astloom_cli.commands.quality_audit.collect import (
                    build_quality_audit_report,
                )

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
                if never or stale:
                    active.add(sync_fingerprint("code.sync_debt"))
            except Exception:  # noqa: BLE001
                # Audit unknown — preserve code.sync_debt so reconcile does not cancel.
                active.add(sync_fingerprint("code.sync_debt"))
        except Exception:  # noqa: BLE001
            pass
    if include_quality:
        try:
            from astloom_cli.commands.quality_audit.collect import build_quality_audit_report

            report = build_quality_audit_report()
            for row in report.get("findings") or []:
                severity = str(row.get("severity") or "").lower()
                if severity not in {"high", "medium"}:
                    continue
                category = str(row.get("category") or "quality")
                path = str(row.get("path") or "").strip() or "(unknown)"
                active.add(quality_fingerprint(category, path))
        except Exception:  # noqa: BLE001
            # Incomplete quality scan — marker consumed by expand_active_for_incomplete_audits.
            active.add(QUALITY_AUDIT_INCOMPLETE_MARKER)
    return active


def expand_active_for_incomplete_audits(
    active: set[str],
    *,
    open_fingerprints: set[str],
) -> tuple[set[str], bool]:
    """Preserve open mcp-quality fingerprints when quality audit collection failed."""
    out = set(active)
    incomplete = QUALITY_AUDIT_INCOMPLETE_MARKER in out
    out.discard(QUALITY_AUDIT_INCOMPLETE_MARKER)
    if incomplete:
        prefix = f"{ORIGIN_QUALITY}:"
        for fp in open_fingerprints:
            if str(fp).startswith(prefix):
                out.add(str(fp))
    return out, incomplete


def list_automated_followup_tasks(
    core: Any,
    *,
    scope: Any,
    origins: set[str] | frozenset[str] | None = None,
    status_group: str = "all",
) -> list[dict[str, Any]]:
    """Return public Task dicts for automated follow-ups (optional filters)."""
    from core_data_service.core import Kind

    origin_filter = {str(o) for o in origins} if origins is not None else None
    out: list[dict[str, Any]] = []
    for task in core.store.list(Kind.TASK, scope):
        if not is_automated_followup(task):
            continue
        task_origin = str((task.data or {}).get("origin") or "").strip()
        if origin_filter is not None and task_origin not in origin_filter:
            continue
        if status_group == "open" and task.status not in OPEN_STATUSES:
            continue
        if status_group == "terminal" and task.status not in TERMINAL_STATUSES:
            continue
        out.append(task.public())
    return out


def retention_days(environ: dict[str, str] | None = None) -> int:
    env = environ if environ is not None else os.environ
    raw = str(env.get("ASTLOOM_FOLLOWUP_TASK_RETENTION_DAYS", "") or "").strip()
    if not raw:
        return DEFAULT_RETENTION_DAYS
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_RETENTION_DAYS


def sync_fingerprint(followup_kind: str) -> str:
    return f"{ORIGIN_SYNC}:{str(followup_kind or '').strip()}"


def quality_fingerprint(category: str, path: str) -> str:
    return f"{ORIGIN_QUALITY}:{str(category or '').strip()}:{str(path or '').strip()}"


def idempotency_key(project_id: str, fingerprint: str) -> str:
    return f"followup:{project_id}:{fingerprint}"[:200]


def is_automated_followup(record: Any) -> bool:
    data = getattr(record, "data", None) or {}
    if not isinstance(data, dict):
        return False
    return str(data.get("retention_class") or "") == RETENTION_CLASS


def build_task_payload(
    *,
    title: str,
    instructions: str,
    origin: str,
    followup_kind: str,
    paths: list[str],
    fingerprint: str,
    acceptance_criteria: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "title": title[:240],
        "assignee_type": "backend",
        "instructions": instructions,
        "acceptance_criteria": acceptance_criteria
        or [
            "Finding remediated",
            "astloom_quality_audit clean for path",
        ],
        "origin": origin,
        "followup_kind": followup_kind,
        "paths": list(paths),
        "fingerprint": fingerprint,
        "retention_class": RETENTION_CLASS,
    }


def create_automated_followup_task(
    core: Any,
    *,
    scope: Any,
    actor: str,
    correlation_id: str,
    project_id: str,
    title: str,
    instructions: str,
    origin: str,
    followup_kind: str,
    paths: list[str],
    fingerprint: str,
    acceptance_criteria: list[str] | None = None,
) -> dict[str, Any]:
    """Create or return existing Task for fingerprint (stable identity).

    Prefer an open Task with the same fingerprint. Refresh title/instructions/paths
    in place when the aggregate set changes. Reopen a terminal Task when debt
    returns. Fall back to idempotent create.
    """
    from core_data_service.core import ConflictError, Kind

    payload = build_task_payload(
        title=title,
        instructions=instructions,
        origin=origin,
        followup_kind=followup_kind,
        paths=paths,
        fingerprint=fingerprint,
        acceptance_criteria=acceptance_criteria,
    )

    def _refresh(record: Any) -> dict[str, Any]:
        record.data = {**record.data, **payload}
        record.updated_at = datetime.now(UTC).isoformat()
        record.version += 1
        core.store.put(record)
        return record.public()

    matched = [
        t
        for t in core.store.list(Kind.TASK, scope)
        if is_automated_followup(t)
        and str((t.data or {}).get("fingerprint") or "") == fingerprint
    ]
    for existing in matched:
        if existing.status in OPEN_STATUSES:
            return _refresh(existing)
    for existing in matched:
        if existing.status in TERMINAL_STATUSES:
            current = existing
            if current.status in {"canceled", "done"}:
                current = core.transition(
                    scope,
                    actor,
                    correlation_id,
                    f"followup-reopen:{current.id}:{uuid4()}",
                    current.id,
                    "reopened",
                    "debt_returned",
                    current.version,
                    Kind.TASK,
                )
            return _refresh(current)

    key = idempotency_key(project_id, fingerprint)
    try:
        record = core.create(
            Kind.TASK,
            scope,
            actor,
            correlation_id,
            key,
            payload,
        )
        return record.public()
    except ConflictError:
        prior = None
        try:
            # Same key, different payload — recover prior id via list fingerprint.
            for existing in core.store.list(Kind.TASK, scope):
                if str((existing.data or {}).get("fingerprint") or "") == fingerprint:
                    prior = existing
                    break
        except Exception:
            prior = None
        if prior is not None:
            if prior.status in OPEN_STATUSES:
                return _refresh(prior)
            if prior.status in TERMINAL_STATUSES:
                current = prior
                if current.status in {"canceled", "done"}:
                    current = core.transition(
                        scope,
                        actor,
                        correlation_id,
                        f"followup-reopen:{current.id}:{uuid4()}",
                        current.id,
                        "reopened",
                        "debt_returned",
                        current.version,
                        Kind.TASK,
                    )
                return _refresh(current)
        raise


def _parse_ts(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except ValueError:
        return None


def _cancel_to_terminal(
    core: Any,
    *,
    scope: Any,
    actor: str,
    correlation_id: str,
    record: Any,
) -> Any:
    """Move an open Task to canceled (review requires in_progress hop)."""
    from core_data_service.core import Kind

    current = record
    if current.status == "review":
        current = core.transition(
            scope,
            actor,
            correlation_id,
            f"followup-cancel-hop:{current.id}:{uuid4()}",
            current.id,
            "in_progress",
            "finding_cleared_pre_cancel",
            current.version,
            Kind.TASK,
        )
    if current.status in TERMINAL_STATUSES:
        return current
    if current.status not in OPEN_STATUSES and current.status != "in_progress":
        return current
    return core.transition(
        scope,
        actor,
        correlation_id,
        f"followup-cancel:{current.id}:{uuid4()}",
        current.id,
        "canceled",
        CANCEL_REASON,
        current.version,
        Kind.TASK,
    )


def reconcile_automated_followup_tasks(
    core: Any,
    *,
    scope: Any,
    actor: str,
    correlation_id: str,
    active_fingerprints: set[str],
    origins: set[str] | frozenset[str] | None = None,
) -> dict[str, Any]:
    """Cancel open automated Tasks whose fingerprint is no longer in the active set.

    When ``origins`` is set, only Tasks with matching ``data.origin`` are considered
    so quality-audit reconcile cannot cancel sync-followup Tasks (and vice versa).
    """
    from core_data_service.core import Kind

    canceled = 0
    errors: list[str] = []
    kept = 0
    origin_filter = {str(o) for o in origins} if origins is not None else None
    try:
        tasks = core.store.list(Kind.TASK, scope)
    except Exception as exc:  # noqa: BLE001
        return {"tasks_canceled": 0, "tasks_kept_open": 0, "errors": [str(exc)]}

    for task in tasks:
        if not is_automated_followup(task):
            continue
        if task.status not in OPEN_STATUSES:
            continue
        task_origin = str((task.data or {}).get("origin") or "").strip()
        if origin_filter is not None and task_origin not in origin_filter:
            continue
        fingerprint = str((task.data or {}).get("fingerprint") or "").strip()
        if not fingerprint:
            # Legacy automated-ish titles without fingerprint: leave alone.
            continue
        if fingerprint in active_fingerprints:
            kept += 1
            continue
        try:
            _cancel_to_terminal(
                core,
                scope=scope,
                actor=actor,
                correlation_id=correlation_id,
                record=task,
            )
            canceled += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{task.id}: {exc}")
    return {
        "tasks_canceled": canceled,
        "tasks_kept_open": kept,
        "errors": errors,
    }


def parse_legacy_quality_title(title: str) -> tuple[str, str] | None:
    """Parse ``Quality: {category} — {path}`` (em dash or hyphen) into parts."""
    text = str(title or "").strip()
    if not text.lower().startswith("quality:"):
        return None
    rest = text.split(":", 1)[1].strip()
    for sep in ("\u2014", " — ", " – ", " - "):
        if sep in rest:
            category, path = rest.split(sep, 1)
            category = category.strip()
            path = path.strip()
            if category and path:
                return category, path
    return None


def parse_legacy_sync_title(title: str) -> tuple[str, str] | None:
    """Map pre-lifecycle sync follow-up titles to ``(followup_kind, fingerprint)``."""
    text = str(title or "").strip()
    lower = text.lower()
    if lower.startswith("remediate") and "sync-skipped" in lower:
        kind = "docs.standards_skipped"
        return kind, sync_fingerprint(kind)
    if lower.startswith("code graph debt"):
        kind = "code.sync_debt"
        return kind, sync_fingerprint(kind)
    return None


def adopt_legacy_quality_tasks(
    core: Any,
    *,
    scope: Any,
    actor: str,
    correlation_id: str,
    dry_run: bool = False,
    cancel_unparseable_quality: bool = True,
) -> dict[str, Any]:
    """Stamp retention metadata onto legacy automated-ish Tasks and collapse dupes.

    Covers:
    - ``Quality: {category} — {path}`` (mcp-quality)
    - ``Remediate … sync-skipped …`` / ``Code graph debt: …`` (sync-followup)
    - optional cancel of other open ``Quality:`` titles that cannot be parsed
    """
    from core_data_service.core import Kind

    adopted = 0
    canceled_dupes = 0
    canceled_orphans = 0
    skipped = 0
    errors: list[str] = []
    would_adopt: list[dict[str, Any]] = []
    by_fp: dict[str, list[Any]] = {}

    try:
        tasks = list(core.store.list(Kind.TASK, scope))
    except Exception as exc:  # noqa: BLE001
        return {
            "tasks_adopted": 0,
            "tasks_canceled_dupes": 0,
            "tasks_canceled_orphans": 0,
            "skipped": 0,
            "errors": [str(exc)],
            "dry_run": dry_run,
        }

    for task in tasks:
        data = task.data if isinstance(task.data, dict) else {}
        if is_automated_followup(task):
            fp = str(data.get("fingerprint") or "").strip()
            if fp and task.status in OPEN_STATUSES:
                by_fp.setdefault(fp, []).append(task)
            continue
        title = str(data.get("title") or "")
        payload_extra: dict[str, Any] | None = None
        fingerprint = ""

        parsed_q = parse_legacy_quality_title(title)
        if parsed_q is not None:
            category, path = parsed_q
            fingerprint = quality_fingerprint(category, path)
            payload_extra = {
                "origin": ORIGIN_QUALITY,
                "followup_kind": category,
                "paths": [path],
                "fingerprint": fingerprint,
                "retention_class": RETENTION_CLASS,
            }
        else:
            parsed_s = parse_legacy_sync_title(title)
            if parsed_s is not None:
                kind, fingerprint = parsed_s
                payload_extra = {
                    "origin": ORIGIN_SYNC,
                    "followup_kind": kind,
                    "paths": list(data.get("paths") or []),
                    "fingerprint": fingerprint,
                    "retention_class": RETENTION_CLASS,
                }
            elif title.lower().startswith("quality:") and task.status in OPEN_STATUSES:
                if cancel_unparseable_quality:
                    would_adopt.append(
                        {
                            "id": task.id,
                            "status": task.status,
                            "fingerprint": None,
                            "title": title[:120],
                            "action": "cancel_orphan",
                        }
                    )
                    if dry_run:
                        canceled_orphans += 1
                        continue
                    try:
                        _cancel_to_terminal(
                            core,
                            scope=scope,
                            actor=actor,
                            correlation_id=correlation_id,
                            record=task,
                        )
                        canceled_orphans += 1
                    except Exception as exc:  # noqa: BLE001
                        errors.append(f"orphan:{task.id}: {exc}")
                else:
                    skipped += 1
                continue
            else:
                continue

        would_adopt.append(
            {
                "id": task.id,
                "status": task.status,
                "fingerprint": fingerprint,
                "title": title[:120],
                "action": "adopt",
            }
        )
        if dry_run:
            adopted += 1
            if task.status in OPEN_STATUSES:
                by_fp.setdefault(fingerprint, []).append(task)
            continue
        try:
            task.data = {**data, **payload_extra}
            task.updated_at = datetime.now(UTC).isoformat()
            task.version += 1
            core.store.put(task)
            adopted += 1
            if task.status in OPEN_STATUSES:
                by_fp.setdefault(fingerprint, []).append(task)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{task.id}: {exc}")

    for fingerprint, group in by_fp.items():
        opens = [t for t in group if t.status in OPEN_STATUSES]
        if len(opens) <= 1:
            continue
        opens.sort(key=lambda t: str(t.updated_at or ""), reverse=True)
        for dupe in opens[1:]:
            if dry_run:
                canceled_dupes += 1
                continue
            try:
                _cancel_to_terminal(
                    core,
                    scope=scope,
                    actor=actor,
                    correlation_id=correlation_id,
                    record=dupe,
                )
                canceled_dupes += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"dupe:{dupe.id}: {exc}")

    result: dict[str, Any] = {
        "tasks_adopted": adopted,
        "tasks_canceled_dupes": canceled_dupes,
        "tasks_canceled_orphans": canceled_orphans,
        "skipped": skipped,
        "errors": errors,
        "dry_run": dry_run,
    }
    if dry_run:
        result["would_adopt"] = would_adopt
        result["would_adopt_count"] = len(would_adopt)
    return result


def terminal_purge_candidates(
    core: Any,
    *,
    scope: Any,
    retention_days_value: int | None = None,
    now: datetime | None = None,
) -> list[Any]:
    """Return terminal automated Task records older than the retention window."""
    from core_data_service.core import Kind

    days = DEFAULT_RETENTION_DAYS if retention_days_value is None else retention_days_value
    if days <= 0:
        return []
    stamp = now or datetime.now(UTC)
    cutoff = stamp - timedelta(days=days)
    out: list[Any] = []
    try:
        tasks = core.store.list(Kind.TASK, scope)
    except Exception:  # noqa: BLE001
        return []
    for task in tasks:
        if not is_automated_followup(task):
            continue
        if task.status not in TERMINAL_STATUSES:
            continue
        updated = _parse_ts(str(task.updated_at or ""))
        if updated is None or updated > cutoff:
            continue
        out.append(task)
    return out


def purge_terminal_automated_followup_tasks(
    core: Any,
    *,
    scope: Any,
    actor: str,
    correlation_id: str,
    retention_days_value: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Hard-delete terminal automated Tasks older than the retention window."""
    from core_data_service.core import Kind

    days = DEFAULT_RETENTION_DAYS if retention_days_value is None else retention_days_value
    if days <= 0:
        return {"tasks_purged": 0, "errors": [], "retention_days": days}

    purged = 0
    errors: list[str] = []
    for task in terminal_purge_candidates(
        core,
        scope=scope,
        retention_days_value=days,
        now=now,
    ):
        try:
            core.delete_record(
                scope,
                actor,
                correlation_id,
                f"followup-purge:{task.id}",
                task.id,
                kind=Kind.TASK,
                reason="retention_purge",
            )
            purged += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{task.id}: {exc}")
    return {"tasks_purged": purged, "errors": errors, "retention_days": days}

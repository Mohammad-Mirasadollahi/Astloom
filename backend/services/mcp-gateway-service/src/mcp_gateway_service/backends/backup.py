"""MCP backup status / dry-run (no large file transfer)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from astloom_backup.job_state import read_job
from astloom_backup.orchestrator import dry_run_bundle
from astloom_backup.scope import Remap
from astloom_cli.util import repo_root


def backup_status(*, base: dict[str, Any], scope: dict[str, str] | None = None) -> dict[str, Any]:
    job = read_job(repo_root())
    if job and scope:
        job_scope = job.get("scope") if isinstance(job.get("scope"), dict) else {}
        if not _job_matches_scope(job_scope, scope):
            return {
                **base,
                "ok": True,
                "job": None,
                "job_omitted": "last backup job belongs to a different MCP project scope",
            }
    return {**base, "ok": True, "job": job}


def _job_matches_scope(job_scope: dict[str, Any], scope: dict[str, str]) -> bool:
    for key in ("tenant_id", "workspace_id", "project_id"):
        left = str(job_scope.get(key) or "").strip()
        right = str(scope.get(key) or "").strip()
        if not left or left != right:
            return False
    return True


def backup_dry_run(
    arguments: dict[str, Any],
    *,
    base: dict[str, Any],
) -> dict[str, Any]:
    path = str(arguments.get("bundle_path") or "").strip()
    if not path:
        raise ValueError("bundle_path is required")
    remap = Remap(
        tenant_id=str(arguments.get("remap_tenant") or "").strip() or None,
        workspace_id=str(arguments.get("remap_workspace") or "").strip() or None,
        project_id=str(arguments.get("remap_project") or "").strip() or None,
    )
    replace = bool(arguments.get("replace") or False)
    report = dry_run_bundle(
        Path(path),
        repo_root=repo_root(),
        remap=remap if remap.active else None,
        replace=replace,
    )
    return {**base, **report}

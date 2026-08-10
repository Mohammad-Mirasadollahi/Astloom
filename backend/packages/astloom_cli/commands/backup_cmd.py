"""`astloom backup` commands."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from astloom_backup.job_state import read_job
from astloom_backup.orchestrator import (
    dry_run_bundle,
    export_bundle,
    restore_bundle,
    validate_bundle,
)
from astloom_backup.scope import Remap, Scope
from astloom_cli.cli_defaults import load_dotenv_files, resolve_operator_scope
from astloom_cli.util import print_json, repo_root


def _ensure_backup_env() -> None:
    """Load dotenv + compose-derived ASTLOOM_DATABASE_URL (same as status/graph)."""
    load_dotenv_files()
    if str(os.environ.get("ASTLOOM_DATABASE_URL") or "").strip():
        return
    try:
        from astloom_cli.remote_client import apply_compose_env_to_os

        apply_compose_env_to_os(os.environ, repo_root())
    except SystemExit:
        pass


def _remap_from_args(args: argparse.Namespace) -> Remap | None:
    remap = Remap(
        tenant_id=(getattr(args, "remap_tenant", "") or "").strip() or None,
        workspace_id=(getattr(args, "remap_workspace", "") or "").strip() or None,
        project_id=(getattr(args, "remap_project", "") or "").strip() or None,
    )
    return remap if remap.active else None


def cmd_backup_export(args: argparse.Namespace) -> int:
    _ensure_backup_env()
    tenant, workspace, project = resolve_operator_scope(
        tenant=getattr(args, "tenant", "") or "",
        workspace=getattr(args, "workspace", "") or "",
        project=getattr(args, "project", "") or "",
    )
    scope = Scope(tenant_id=tenant, workspace_id=workspace, project_id=project)
    result = export_bundle(scope, Path(args.output), repo_root=repo_root())
    print_json(result)
    return 0


def cmd_backup_validate(args: argparse.Namespace) -> int:
    result = validate_bundle(
        Path(args.input),
        check_contract=not bool(getattr(args, "skip_contract", False)),
    )
    print_json(result)
    return 0


def cmd_backup_restore(args: argparse.Namespace) -> int:
    _ensure_backup_env()
    result = restore_bundle(
        Path(args.input),
        repo_root=repo_root(),
        remap=_remap_from_args(args),
        replace=bool(getattr(args, "replace", False)),
        yes=bool(getattr(args, "yes", False)),
        check_contract=not bool(getattr(args, "skip_contract", False)),
    )
    print_json(result)
    return 0


def cmd_backup_dry_run(args: argparse.Namespace) -> int:
    _ensure_backup_env()
    result = dry_run_bundle(
        Path(args.input),
        repo_root=repo_root(),
        remap=_remap_from_args(args),
        replace=bool(getattr(args, "replace", False)),
        check_contract=not bool(getattr(args, "skip_contract", False)),
    )
    print_json(result)
    return 0


def cmd_backup_status(args: argparse.Namespace) -> int:
    job = read_job(repo_root())
    if job is None:
        print_json({"ok": True, "job": None, "message": "no backup job recorded"})
        return 0
    print_json({"ok": True, "job": job})
    return 0

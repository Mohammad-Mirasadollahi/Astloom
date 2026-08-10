"""Local project state commands."""

from __future__ import annotations

import argparse
from pathlib import Path

from astloom_cli import state
from astloom_cli.util import now_iso, print_json, repo_root, require_scope
from usage_profile import load_usage_profile, resolve_effective_profile


def project_path_msg(root: Path, tenant: str, workspace: str, project: str) -> str:
    return str(root / tenant / workspace / f"{project}.json")


def cmd_project_register(args: argparse.Namespace) -> int:
    tenant, workspace, project_id = require_scope(args)
    root = state.default_state_root(repo_root())
    existing = state.load_project(root, tenant, workspace, project_id)
    if existing and not args.force:
        raise SystemExit(
            f"error: project already registered at "
            f"{project_path_msg(root, tenant, workspace, project_id)} (use --force)"
        )
    usage_profile = str(args.usage_profile or "programming-cursor-mcp").strip()
    catalog = load_usage_profile(usage_profile)
    project = {
        "tenant_id": tenant,
        "workspace_id": workspace,
        "project_id": project_id,
        "name": str(args.name or project_id).strip(),
        "usage_profile": usage_profile,
        "domain_pack": str(args.domain_pack or catalog["domain_pack"]),
        "feature_profile": str(args.feature_profile or catalog["feature_profile"]),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "status": "active",
    }
    path = state.save_project(root, project)
    print_json({"saved": str(path), "project": project})
    return 0


def cmd_project_activate(args: argparse.Namespace) -> int:
    tenant, workspace, project_id = require_scope(args)
    root = state.default_state_root(repo_root())
    project = state.load_project(root, tenant, workspace, project_id)
    if project is None:
        raise SystemExit("error: project not found; run: astloom project register ...")
    usage_profile = str(args.usage_profile or "").strip()
    if not usage_profile:
        raise SystemExit("error: --usage-profile is required")
    catalog = load_usage_profile(usage_profile)
    project["usage_profile"] = usage_profile
    if args.apply_catalog_defaults:
        project["domain_pack"] = catalog["domain_pack"]
        project["feature_profile"] = catalog["feature_profile"]
    project["updated_at"] = now_iso()
    path = state.save_project(root, project)
    print_json({"saved": str(path), "project": project})
    return 0


def cmd_project_show(args: argparse.Namespace) -> int:
    tenant, workspace, project_id = require_scope(args)
    project = state.load_project(state.default_state_root(repo_root()), tenant, workspace, project_id)
    if project is None:
        raise SystemExit("error: project not found")
    print_json(project)
    return 0


def cmd_project_effective(args: argparse.Namespace) -> int:
    tenant, workspace, project_id = require_scope(args)
    project = state.load_project(state.default_state_root(repo_root()), tenant, workspace, project_id)
    if project is None:
        raise SystemExit("error: project not found")
    effective = resolve_effective_profile(
        str(project.get("usage_profile") or "programming-cursor-mcp"),
        tenant_id=tenant,
        workspace_id=workspace,
        project_id=project_id,
        overrides={
            "domain_pack": project.get("domain_pack"),
            "feature_profile": project.get("feature_profile"),
        },
    )
    print_json(effective)
    return 0

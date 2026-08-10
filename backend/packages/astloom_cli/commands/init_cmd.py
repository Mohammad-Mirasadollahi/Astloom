"""`astloom init` — create first tenant + workspace and pin software paths."""

from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path

from astloom_cli import state
from astloom_cli import ui
from astloom_cli.identity import (
    identity_path,
    merge_identity_into_connect_yaml,
    peek_identity,
    slugify,
)
from astloom_cli.software_paths import peek_software_paths, persist_software_paths
from astloom_cli.util import now_iso, print_json, repo_root
from usage_profile import load_usage_profile


def _require_id(raw: str, *, label: str) -> str:
    value = slugify(str(raw or "").strip(), fallback="")
    if not value:
        raise SystemExit(
            f"error: {label} id is required (letters, digits, hyphens). "
            f"Example: astloom init --tenant acme --workspace eng --path ."
        )
    return value


def cmd_init(args: argparse.Namespace) -> int:
    existing = peek_identity()
    if existing.get("tenant") and existing.get("workspace") and not args.force:
        ui.blank()
        ui.heading("Identity already set", success=True)
        ui.blank()
        ui.kv(
            "Scope",
            ui.scope_line(
                existing["tenant"],
                existing["workspace"],
                existing.get("project") or "?",
            ),
        )
        ui.kv("File", str(identity_path()))
        pinned = peek_software_paths()
        if pinned:
            ui.kv("Paths", f"{len(pinned)} root(s)")
            for p in pinned:
                ui.bullet(p)
        else:
            ui.kv("Paths", ui.warn("none — add with: astloom paths add /path/to/app"))
        ui.next_steps(
            [
                "Edit roots: astloom paths list | add | remove",
                "Replace scope: astloom init --tenant … --workspace … --path … --force",
                "Tear down: astloom destroy-profile … (interactive confirmations)",
            ]
        )
        ui.blank()
        return 0

    tenant = _require_id(args.tenant, label="tenant")
    workspace = _require_id(args.workspace, label="workspace")
    project_raw = str(args.project or "").strip() or Path.cwd().name or "project"
    project = _require_id(project_raw, label="project")
    display = str(args.name or "").strip() or getpass.getuser() or tenant

    path_args = list(args.path or [])
    if not path_args:
        raise SystemExit(
            "error: at least one --path is required (software root to sync)\n"
            "  Example: astloom init --tenant acme --workspace eng --path /opt/MyApp\n"
            "  Multiple:  … --path /opt/AppA --path /opt/AppB"
        )

    usage_profile = str(args.usage_profile or "programming-cursor-mcp").strip()
    catalog = load_usage_profile(usage_profile)

    root = state.default_state_root(repo_root())
    project_doc = {
        "tenant_id": tenant,
        "workspace_id": workspace,
        "project_id": project,
        "name": str(args.project_name or project).strip(),
        "usage_profile": usage_profile,
        "domain_pack": catalog["domain_pack"],
        "feature_profile": catalog["feature_profile"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "status": "active",
        "paths": [],
    }
    state.save_project(root, project_doc)

    paths = persist_software_paths(
        path_args,
        tenant=tenant,
        workspace=workspace,
        project=project,
        display_name=display,
    )
    connect_path = merge_identity_into_connect_yaml(
        tenant=tenant, workspace=workspace, project=project
    )
    # persist_software_paths already wrote .env; surface path for UI
    env_path = repo_root() / ".env"

    os.environ["ASTLOOM_TENANT_ID"] = tenant
    os.environ["ASTLOOM_WORKSPACE_ID"] = workspace
    os.environ["ASTLOOM_PROJECT_ID"] = project

    ui.blank()
    ui.heading("Init complete — IDs and paths saved")
    ui.blank()
    ui.kv("Scope", ui.scope_line(tenant, workspace, project))
    ui.kv("Display", display)
    ui.kv("Identity", str(identity_path()))
    ui.kv("Env", str(env_path))
    if connect_path:
        ui.kv("Connect", f"{connect_path} (scope updated)")
    ui.kv("Project", str(state.project_path(root, tenant, workspace, project)))
    ui.section("Software paths (sync roots)")
    for p in paths:
        ui.bullet(p)
    ui.blank()
    ui.section("What happened")
    ui.bullet("Pinned tenant / workspace / project as the active scope")
    ui.bullet("Pinned software path(s) used by astloom sync")
    ui.bullet("Wrote local project state + .env keys for later commands")
    ui.next_steps(
        [
            "astloom connect --local",
            "astloom status",
            "astloom sync",
            "astloom paths list   # add/remove later",
        ]
    )
    ui.blank()
    print_json(
        {
            "ok": True,
            "scope": {"tenant": tenant, "workspace": workspace, "project": project},
            "paths": paths,
            "display_name": display,
            "identity": str(identity_path()),
            "project_state": str(state.project_path(root, tenant, workspace, project)),
            "env": str(env_path),
            "connect": str(connect_path) if connect_path else None,
        }
    )
    return 0

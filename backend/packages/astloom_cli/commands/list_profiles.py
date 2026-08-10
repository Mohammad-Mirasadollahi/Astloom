"""`astloom list-profiles` — list local scope profiles (tenant/workspace/project)."""

from __future__ import annotations

import argparse

from astloom_cli import state
from astloom_cli import ui
from astloom_cli.cli_defaults import resolve_operator_scope
from astloom_cli.identity import identity_path, peek_identity
from astloom_cli.util import print_json, repo_root


def cmd_list_profiles(args: argparse.Namespace) -> int:
    """Show registered local profiles and which scope is currently active."""
    root = state.default_state_root(repo_root())
    profiles = state.list_projects(root)
    identity = peek_identity()
    active_tenant, active_workspace, active_project = resolve_operator_scope()

    rows: list[dict] = []
    for item in profiles:
        active = (
            item["tenant_id"] == active_tenant
            and item["workspace_id"] == active_workspace
            and item["project_id"] == active_project
        )
        rows.append({**item, "active": active})

    if identity.get("tenant") and identity.get("workspace") and identity.get("project"):
        keyed = {(r["tenant_id"], r["workspace_id"], r["project_id"]) for r in rows}
        id_key = (identity["tenant"], identity["workspace"], identity["project"])
        if id_key not in keyed:
            rows.insert(
                0,
                {
                    "tenant_id": identity["tenant"],
                    "workspace_id": identity["workspace"],
                    "project_id": identity["project"],
                    "name": identity.get("display_name") or identity["project"],
                    "usage_profile": "",
                    "domain_pack": "",
                    "feature_profile": "",
                    "status": "identity-only",
                    "created_at": "",
                    "updated_at": "",
                    "path": str(identity_path()),
                    "active": id_key == (active_tenant, active_workspace, active_project),
                },
            )

    payload = {
        "active_scope": {
            "tenant": active_tenant,
            "workspace": active_workspace,
            "project": active_project,
        },
        "identity_file": str(identity_path()) if identity_path().is_file() else None,
        "identity": identity or None,
        "count": len(rows),
        "profiles": rows,
    }

    if args.json:
        print_json(payload)
        return 0

    ui.blank()
    ui.heading("Local profiles")
    ui.blank()
    print(
        "   "
        + ui.dim(
            "Each row is one tenant + workspace + project "
            "(not Usage Profile templates — see: astloom profile list)"
        )
    )
    ui.blank()
    ui.kv("Active", ui.scope_line(active_tenant, active_workspace, active_project))
    if payload["identity_file"]:
        ui.kv("Identity", str(payload["identity_file"]))

    if not rows:
        ui.blank()
        print(f"   {ui.warn('(none)')}")
        ui.next_steps(["astloom init --tenant <id> --workspace <id>"])
        ui.blank()
        return 0

    ui.blank()
    header = (
        f"  {'':1}{'tenant':<14} {'workspace':<12} {'project':<16} "
        f"{'usage_profile':<24} {'status':<12} name"
    )
    print(ui.dim(header))
    ui.rule(100)
    for row in rows:
        mark = ui.ok("*") if row.get("active") else " "
        line = (
            f"  {mark} {row['tenant_id']:<14} {row['workspace_id']:<12} {row['project_id']:<16} "
            f"{(row.get('usage_profile') or '-'):<24} {(row.get('status') or '-'):<12} "
            f"{row.get('name') or ''}"
        )
        print(line if row.get("active") else ui.dim(line))

    ui.blank()
    print(f"   {ui.dim('* = currently active (flags / env / identity)')}")
    ui.next_steps(
        [
            "Destroy one: astloom destroy-profile --tenant … --workspace … --project …",
            "(then type two different confirmation phrases)",
        ]
    )
    ui.blank()
    if args.verbose:
        print_json(payload)
    return 0

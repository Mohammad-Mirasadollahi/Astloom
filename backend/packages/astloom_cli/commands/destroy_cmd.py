"""`astloom destroy-profile` — delete scope IDs + Astloom profile data (not source code)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from astloom_cli import state
from astloom_cli.commands.graph import _graph_service
from astloom_cli.identity import (
    clear_connect_scope_if_matches,
    clear_identity_if_matches,
    clear_repo_env_scope_if_matches,
)
from astloom_cli.mcp_client_targets import DEFAULT_SERVER_NAME, MCP_CLIENT_TARGETS
from astloom_cli.util import print_json, repo_root, require_scope
from astloom_cli import ui

# Two different confirmation phrases (typed by the operator; not CLI flags).
CONFIRM_PHRASE_1 = "DELETE PROFILE DATA"
CONFIRM_PHRASE_2_TEMPLATE = "{tenant}/{workspace}/{project}"


def _print_warning(*, tenant: str, workspace: str, project: str) -> None:
    ui.blank()
    ui.heading("Destroy profile data", success=False)
    ui.blank()
    ui.kv("Scope", ui.scope_line(tenant, workspace, project))
    ui.blank()
    ui.section("Will delete (profile / platform data only)")
    for line in (
        "code-graph symbols, edges, embeddings for this scope",
        "local Usage Profile project state under .astloom/projects/",
        ".astloom/identity.yaml if it pins this scope",
        "matching ASTLOOM_* scope keys in repo .env",
        "matching scope in .astloom/connect.yaml",
        "Astloom MCP server entries in this repo's IDE mcp.json files",
    ):
        ui.bullet(line)
    ui.blank()
    ui.section("Will NOT delete")
    ui.bullet("your source code, git history, or unrelated files")
    ui.bullet("other tenants / workspaces / projects")
    ui.blank()


def _read_confirm(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError as exc:
        raise SystemExit("error: confirmation aborted (no input). Nothing was deleted.") from exc


def confirm_destroy_interactively(*, tenant: str, workspace: str, project: str) -> None:
    """Require two different typed confirmations (no --yes flags)."""
    _print_warning(tenant=tenant, workspace=workspace, project=project)
    if not sys.stdin.isatty():
        raise SystemExit(
            "error: destroy-profile requires an interactive terminal "
            "(type two different confirmations). Nothing was deleted."
        )

    phrase1 = CONFIRM_PHRASE_1
    phrase2 = CONFIRM_PHRASE_2_TEMPLATE.format(
        tenant=tenant, workspace=workspace, project=project
    )

    first = _read_confirm(
        f"   Confirm 1/2 — type exactly: {ui.accent(phrase1)}\n   > "
    ).strip()
    if first != phrase1:
        raise SystemExit(
            f'error: confirmation 1 failed (expected "{phrase1}"). Nothing was deleted.'
        )

    second = _read_confirm(
        f"   Confirm 2/2 — type this exact scope: {ui.accent(phrase2)}\n   > "
    ).strip()
    if second != phrase2:
        raise SystemExit(
            f'error: confirmation 2 failed (expected "{phrase2}"). Nothing was deleted.'
        )


def _is_astloom_mcp_key(name: str) -> bool:
    key = str(name or "").strip().lower()
    if not key:
        return False
    if key == DEFAULT_SERVER_NAME.lower():
        return True
    return key.startswith("astloom")


def _strip_astloom_mcp_configs(project_dir: Path) -> list[str]:
    """Remove Astloom mcpServers entries from project-scoped IDE configs."""
    touched: list[str] = []
    for target in MCP_CLIENT_TARGETS:
        if target.scope != "project":
            continue
        path = target.project_path(project_dir)
        if path is None or not path.is_file():
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(doc, dict):
            continue
        root = target.prepare_root(doc)
        servers = root.get(target.servers_key)
        if not isinstance(servers, dict):
            continue
        remove = [k for k in list(servers) if _is_astloom_mcp_key(str(k))]
        if not remove:
            continue
        for key in remove:
            servers.pop(key, None)
        path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        touched.append(str(path))
    return touched


def destroy_profile_data(
    *,
    tenant: str,
    workspace: str,
    project: str,
    cwd: Path | None = None,
    wipe_graph: bool = True,
) -> dict[str, Any]:
    """Delete profile/platform data for one scope. Never touches source trees."""
    work = (cwd or Path.cwd()).resolve()
    root = state.default_state_root(repo_root())
    report: dict[str, Any] = {
        "scope": {"tenant": tenant, "workspace": workspace, "project": project},
        "deleted_source_code": False,
    }

    if wipe_graph:
        try:
            svc = _graph_service()
            from astloom_cli.commands.graph import _ensure_code_graph_import

            _ensure_code_graph_import()
            from code_graph_service.core import Scope

            report["graph"] = svc.purge_scope(Scope(tenant, workspace, project))
        except Exception as exc:  # noqa: BLE001 — still clear local profile pins
            report["graph"] = {"ok": False, "error": str(exc)}

    project_file = state.project_path(root, tenant, workspace, project)
    report["project_state_deleted"] = state.delete_project(root, tenant, workspace, project)
    report["project_state_path"] = str(project_file)

    report["identity_cleared"] = clear_identity_if_matches(
        tenant=tenant, workspace=workspace, project=project
    )
    report["env_cleared"] = clear_repo_env_scope_if_matches(
        repo_root(),
        tenant=tenant,
        workspace=workspace,
        project=project,
    )
    connect_path = clear_connect_scope_if_matches(
        tenant=tenant, workspace=workspace, project=project
    )
    report["connect_scope_cleared"] = str(connect_path) if connect_path else None
    report["mcp_configs_updated"] = _strip_astloom_mcp_configs(work)
    return report


def cmd_destroy_profile(args: argparse.Namespace) -> int:
    tenant, workspace, project = require_scope(args, with_defaults=True)
    confirm_destroy_interactively(tenant=tenant, workspace=workspace, project=project)
    report = destroy_profile_data(tenant=tenant, workspace=workspace, project=project)
    ui.blank()
    ui.heading("Profile destroyed")
    ui.blank()
    ui.kv("Scope", ui.scope_line(tenant, workspace, project))
    ui.bullet("Source code was not touched")
    ui.next_steps(["astloom init --tenant … --workspace …", "astloom connect --local"])
    ui.blank()
    print_json({"ok": True, "destroy_profile": report})
    return 0

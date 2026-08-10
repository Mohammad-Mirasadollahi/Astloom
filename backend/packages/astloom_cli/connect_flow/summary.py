"""Connect summary UI, MCP client writes, and MCP-first guidance seed."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from astloom_cli import state, ui
from astloom_cli.connect_config import ConnectSettings
from astloom_cli.mcp_client_targets import (
    DEFAULT_SERVER_NAME,
    resolve_client_ids,
    write_fragment_to_clients,
)
from astloom_cli.util import now_iso, repo_root
from usage_profile import load_usage_profile


def materialize_mcp_first_guidance(work: Path) -> dict[str, Any]:
    """Write always-apply MCP-first rule/skills so agents prefer Astloom without waiting on resolve."""
    try:
        from common_context_service.guidance_export import materialize_mcp_first_seed
    except ImportError:
        return {"written": [], "skipped": [], "conflicts": [], "error": "common_context_service unavailable"}
    return materialize_mcp_first_seed(work, layout="cursor", force=False)


def local_register(settings: ConnectSettings) -> Path:
    root = state.default_state_root(repo_root())
    catalog = load_usage_profile(settings.usage_profile)
    existing = state.load_project(root, settings.tenant, settings.workspace, settings.project)
    project = existing or {
        "tenant_id": settings.tenant,
        "workspace_id": settings.workspace,
        "project_id": settings.project,
        "created_at": now_iso(),
        "status": "active",
    }
    project.update(
        {
            "name": settings.project_name or settings.project,
            "usage_profile": settings.usage_profile,
            "domain_pack": catalog["domain_pack"],
            "feature_profile": catalog["feature_profile"],
            "updated_at": now_iso(),
        }
    )
    return state.save_project(root, project)


def write_clients(work: Path, fragment: dict[str, Any], settings: ConnectSettings) -> list[Path]:
    client_ids = resolve_client_ids(settings.clients)
    return write_fragment_to_clients(
        work,
        fragment,
        client_ids,
        server_name=DEFAULT_SERVER_NAME,
        include_user_clients=settings.include_user_clients,
    )


def guidance_connect_notes(guidance: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if guidance.get("error"):
        notes.append(f"MCP-first guidance skip: {guidance['error']}")
        return notes
    written = guidance.get("written") or []
    conflicts = guidance.get("conflicts") or []
    removed = guidance.get("removed") or []
    version = guidance.get("seed_pack_version")
    if written:
        ver = f" @ {version}" if version else ""
        notes.append(f"Materialized MCP-first guidance ({len(written)} file(s){ver})")
    elif version and not conflicts and not removed:
        notes.append(f"MCP-first guidance up to date ({version})")
    if removed:
        notes.append(f"Removed retired MCP-first guidance file(s): {len(removed)}")
    if conflicts:
        paths = ", ".join(str(c.get("path")) for c in conflicts[:3])
        more = "" if len(conflicts) <= 3 else f" (+{len(conflicts) - 3} more)"
        notes.append(f"Skipped conflicting guidance path(s): {paths}{more}")
    return notes


def print_connect_summary(
    *,
    settings: ConnectSettings,
    transport: str,
    project_state: Path | None,
    written: list[Path],
    work: Path,
    extra_notes: list[str] | None = None,
) -> None:
    ui.blank()
    ui.heading("Connect complete")
    ui.blank()
    ui.kv("Scope", ui.scope_line(settings.tenant, settings.workspace, settings.project))
    ui.kv("Profile", settings.usage_profile)
    ui.kv("Transport", transport)
    if project_state is not None:
        ui.kv("Project", str(project_state))
    ui.blank()
    ui.section("What happened")
    ui.bullet("Registered / refreshed local project state for this scope")
    ui.bullet("Wrote MCP server configs so your IDE can talk to Astloom")
    for note in extra_notes or []:
        ui.bullet(note)
    if written:
        ui.blank()
        ui.section("MCP configs written")
        for rel in ui.summarize_paths(written, relative_to=str(work)):
            ui.bullet(rel)
    steps = [
        "Reload MCP / the IDE window",
        "Check health: astloom status",
        "Fill the graph: astloom sync",
    ]
    ui.next_steps(steps)

    ui.blank()


_materialize_mcp_first_guidance = materialize_mcp_first_guidance
_local_register = local_register
_write_clients = write_clients
_guidance_connect_notes = guidance_connect_notes
_print_connect_summary = print_connect_summary

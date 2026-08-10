"""Local stdio MCP fragment (same-host dogfood / Astloom developing Astloom)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from astloom_cli.mcp_client_targets import DEFAULT_SERVER_NAME
from astloom_cli.remote_client import apply_compose_env_to_os, parse_env_file
from astloom_cli.util import repo_root
from usage_profile import materialize_cursor_mcp_config, resolve_effective_profile


def materialize_local_stdio_fragment(
    *,
    tenant: str,
    workspace: str,
    project_id: str,
    usage_profile: str = "programming-cursor-mcp",
    root: Path | None = None,
    server_name: str = DEFAULT_SERVER_NAME,
) -> dict[str, Any]:
    """Build mcpServers entry that runs MCP gateway in-process on this checkout."""
    checkout = (root or repo_root()).resolve()
    effective = resolve_effective_profile(
        usage_profile,
        tenant_id=tenant,
        workspace_id=workspace,
        project_id=project_id,
    )
    python = checkout / ".venv" / "bin" / "python"
    exe = str(python if python.is_file() else sys.executable)
    fragment = materialize_cursor_mcp_config(effective, python_executable=exe)
    old_name = next(iter(fragment["mcpServers"]))
    if old_name != server_name:
        fragment["mcpServers"][server_name] = fragment["mcpServers"].pop(old_name)

    abs_paths = [
        checkout / "backend" / "services" / "mcp-gateway-service" / "src",
        checkout / "backend" / "packages",
        checkout / "backend" / "packages" / "code-metadata",
        checkout / "backend" / "packages" / "common-context",
        checkout / "backend" / "services" / "core-data-service" / "src",
        checkout / "backend" / "services" / "memory-service" / "src",
        checkout / "backend" / "services" / "code-graph-service" / "src",
        checkout / "backend" / "services" / "docs-sync-service" / "src",
        checkout / "backend" / "services" / "common-context-service" / "src",
    ]
    env = fragment["mcpServers"][server_name]["env"]
    env["PYTHONPATH"] = os.pathsep.join(str(p) for p in abs_paths)
    env["ASTLOOM_ROOT"] = str(checkout)
    fragment["mcpServers"][server_name]["cwd"] = str(checkout)

    compose_env = checkout / "backend" / "deployments" / "compose" / ".env.local"
    if compose_env.is_file():
        try:
            merged = dict(os.environ)
            apply_compose_env_to_os(merged, checkout)
            for key in (
                "ASTLOOM_DATABASE_URL",
                "ASTLOOM_CODE_GRAPH_DATABASE_URL",
                "ASTLOOM_MCP_STORE_MODE",
                "ASTLOOM_NEO4J_URI",
                "ASTLOOM_NEO4J_USER",
                "ASTLOOM_NEO4J_PASSWORD",
                "ASTLOOM_CODE_GRAPH_STORE",
                "ASTLOOM_MCP_GRAPH_MODE",
            ):
                if merged.get(key):
                    env[key] = merged[key]
            # Belt: if compose only produced the shared URL, mirror it for pgvector.
            if env.get("ASTLOOM_DATABASE_URL") and not env.get(
                "ASTLOOM_CODE_GRAPH_DATABASE_URL"
            ):
                env["ASTLOOM_CODE_GRAPH_DATABASE_URL"] = env["ASTLOOM_DATABASE_URL"]
        except SystemExit:
            values = parse_env_file(compose_env)
            if values.get("ASTLOOM_NEO4J_PASSWORD"):
                env.setdefault("ASTLOOM_NEO4J_PASSWORD", values["ASTLOOM_NEO4J_PASSWORD"])
    return fragment

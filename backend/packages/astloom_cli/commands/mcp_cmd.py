"""MCP gateway helper commands."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

from astloom_cli import state
from astloom_cli.commands.mcp_tokens import cmd_mcp_tokens
from astloom_cli.util import repo_root, require_scope
from usage_profile import load_usage_profile

__all__ = ["cmd_mcp_tools", "cmd_mcp_serve", "cmd_mcp_serve_http", "cmd_mcp_tokens"]


def cmd_mcp_tools(args: argparse.Namespace) -> int:
    profile_id = str(args.usage_profile or "programming-cursor-mcp").strip()
    profile = load_usage_profile(profile_id)
    for tool in profile["mcp"]["tools"]:
        print(f"{tool['name']}\t{tool['maps_to']}\t{tool['description']}")
    return 0


def cmd_mcp_serve(args: argparse.Namespace) -> int:
    tenant, workspace, project_id = require_scope(args)
    root = repo_root()
    project = state.load_project(state.default_state_root(root), tenant, workspace, project_id)
    usage_profile = str(
        args.usage_profile or (project or {}).get("usage_profile") or "programming-cursor-mcp"
    )
    env = os.environ.copy()
    env["ASTLOOM_USAGE_PROFILE"] = usage_profile
    env["ASTLOOM_TENANT_ID"] = tenant
    env["ASTLOOM_WORKSPACE_ID"] = workspace
    env["ASTLOOM_PROJECT_ID"] = project_id
    env["ASTLOOM_ROOT"] = str(root)
    pythonpath = os.pathsep.join(
        [
            str(root / "backend" / "services" / "mcp-gateway-service" / "src"),
            str(root / "backend" / "packages"),
            str(root / "backend" / "services" / "core-data-service" / "src"),
            str(root / "backend" / "services" / "memory-service" / "src"),
            str(root / "backend" / "services" / "code-graph-service" / "src"),
            str(root / "backend" / "services" / "docs-sync-service" / "src"),
            env.get("PYTHONPATH", ""),
        ]
    ).strip(os.pathsep)
    env["PYTHONPATH"] = pythonpath
    python = root / ".venv" / "bin" / "python"
    exe = str(python if python.is_file() else sys.executable)
    return subprocess.call([exe, "-m", "mcp_gateway_service"], env=env, cwd=str(root))


def cmd_mcp_serve_http(args: argparse.Namespace) -> int:
    """Run Phase B Streamable HTTP MCP gateway (multi-client concurrent)."""
    root = repo_root()
    env = os.environ.copy()
    env["ASTLOOM_ROOT"] = str(root)
    if args.usage_profile:
        env["ASTLOOM_USAGE_PROFILE"] = str(args.usage_profile)
    if not env.get("ASTLOOM_MCP_TOKEN_SECRET") and not env.get("ASTLOOM_MCP_HTTP_TOKEN"):
        raise SystemExit(
            "error: set ASTLOOM_MCP_TOKEN_SECRET (scoped tokens) or ASTLOOM_MCP_HTTP_TOKEN (shared)"
        )
    pythonpath = os.pathsep.join(
        [
            str(root / "backend" / "services" / "mcp-gateway-service" / "src"),
            str(root / "backend" / "packages"),
            str(root / "backend" / "services" / "core-data-service" / "src"),
            str(root / "backend" / "services" / "memory-service" / "src"),
            str(root / "backend" / "services" / "code-graph-service" / "src"),
            str(root / "backend" / "services" / "docs-sync-service" / "src"),
            env.get("PYTHONPATH", ""),
        ]
    ).strip(os.pathsep)
    env["PYTHONPATH"] = pythonpath
    host = str(args.host or env.get("ASTLOOM_MCP_HTTP_HOST") or "0.0.0.0")
    port = int(args.port or env.get("ASTLOOM_MCP_HTTP_PORT") or "32500")
    python = root / ".venv" / "bin" / "python"
    exe = str(python if python.is_file() else sys.executable)
    print(f"MCP HTTP listening on http://{host}:{port}/mcp")
    return subprocess.call(
        [exe, "-m", "mcp_gateway_service", "--http", "--host", host, "--port", str(port)],
        env=env,
        cwd=str(root),
    )

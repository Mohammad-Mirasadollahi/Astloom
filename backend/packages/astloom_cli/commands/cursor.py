"""Cursor MCP export commands."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from astloom_cli import state
from astloom_cli.util import print_json, repo_root, require_scope
from usage_profile import materialize_cursor_mcp_config, resolve_effective_profile


def cmd_cursor_export(args: argparse.Namespace) -> int:
    tenant, workspace, project_id = require_scope(args)
    root = repo_root()
    project = state.load_project(state.default_state_root(root), tenant, workspace, project_id)
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
    python = str(root / ".venv" / "bin" / "python")
    if not Path(python).is_file():
        python = sys.executable
    fragment = materialize_cursor_mcp_config(effective, python_executable=python)
    abs_paths = [
        root / "backend" / "services" / "mcp-gateway-service" / "src",
        root / "backend" / "packages",
        root / "backend" / "services" / "core-data-service" / "src",
        root / "backend" / "services" / "memory-service" / "src",
        root / "backend" / "services" / "code-graph-service" / "src",
        root / "backend" / "services" / "docs-sync-service" / "src",
    ]
    server_name = next(iter(fragment["mcpServers"]))
    fragment["mcpServers"][server_name]["env"]["PYTHONPATH"] = os.pathsep.join(str(p) for p in abs_paths)
    fragment["mcpServers"][server_name]["cwd"] = str(root)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(fragment, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {out}")
    else:
        print_json(fragment)
    return 0

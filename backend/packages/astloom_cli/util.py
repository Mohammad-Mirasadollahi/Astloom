"""Shared CLI helpers."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    env = os.environ.get("ASTLOOM_ROOT", "").strip()
    if env:
        return Path(env).resolve()
    # backend/packages/astloom_cli/util.py → parents[3] = repo root
    return Path(__file__).resolve().parents[3]


def ensure_service_import_paths() -> None:
    """Put in-repo service packages on sys.path for the CLI process."""
    import sys

    package_root = Path(__file__).resolve().parents[3]
    roots = dict.fromkeys((repo_root(), package_root))
    for root in roots:
        for rel in (
            ("backend", "packages"),
            ("backend", "packages", "code-metadata"),
            ("backend", "packages", "common-context"),
            ("backend", "services", "code-graph-service", "src"),
            ("backend", "services", "docs-sync-service", "src"),
            ("backend", "services", "common-context-service", "src"),
        ):
            path = root.joinpath(*rel)
            text = str(path)
            if path.is_dir() and text not in sys.path:
                sys.path.insert(0, text)


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def add_scope_args(parser: argparse.ArgumentParser, *, required: bool = True) -> None:
    """Attach --tenant/--workspace/--project. When *required* is False, operator defaults apply."""
    parser.add_argument(
        "--tenant",
        default="",
        required=required,
        help="Tenant id (default: env / connect.yaml / astloom)",
    )
    parser.add_argument(
        "--workspace",
        default="",
        required=required,
        help="Workspace id (default: env / connect.yaml / dev)",
    )
    parser.add_argument(
        "--project",
        default="",
        required=required,
        help="Project id (default: env / connect.yaml / cwd name)",
    )


def require_scope(args: argparse.Namespace, *, with_defaults: bool = False) -> tuple[str, str, str]:
    if with_defaults:
        from astloom_cli.cli_defaults import resolve_operator_scope

        return resolve_operator_scope(
            tenant=str(args.tenant or ""),
            workspace=str(args.workspace or ""),
            project=str(args.project or ""),
        )
    tenant = str(args.tenant or "").strip()
    workspace = str(args.workspace or "").strip()
    project = str(args.project or "").strip()
    if not all((tenant, workspace, project)):
        raise SystemExit("error: --tenant, --workspace, and --project are required")
    return tenant, workspace, project

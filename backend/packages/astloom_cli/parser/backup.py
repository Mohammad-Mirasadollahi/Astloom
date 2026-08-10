"""`astloom backup` parser."""

from __future__ import annotations

import argparse

from astloom_cli.util import add_scope_args


def register(sub: argparse._SubParsersAction) -> None:
    backup = sub.add_parser(
        "backup",
        help="Export/restore project-scoped .asbak bundles",
    )
    backup_sub = backup.add_subparsers(dest="backup_command", required=True)

    export_p = backup_sub.add_parser("export", help="Export active project scope to .asbak")
    add_scope_args(export_p, required=False)
    export_p.add_argument(
        "--output",
        "-o",
        required=True,
        help="Output .asbak path",
    )

    validate_p = backup_sub.add_parser("validate", help="Validate a .asbak bundle")
    validate_p.add_argument("--input", "-i", required=True, help="Input .asbak path")
    validate_p.add_argument(
        "--skip-contract",
        action="store_true",
        help="Skip contract_version gate (schema fingerprint still checked)",
    )

    restore_p = backup_sub.add_parser("restore", help="Restore a .asbak bundle into this server")
    add_scope_args(restore_p, required=False)
    restore_p.add_argument("--input", "-i", required=True, help="Input .asbak path")
    restore_p.add_argument(
        "--replace",
        action="store_true",
        help="Wipe target scope before import (requires --yes)",
    )
    restore_p.add_argument(
        "--yes",
        action="store_true",
        help="Confirm destructive replace",
    )
    restore_p.add_argument("--remap-tenant", default="", help="Optional target tenant_id")
    restore_p.add_argument("--remap-workspace", default="", help="Optional target workspace_id")
    restore_p.add_argument("--remap-project", default="", help="Optional target project_id")
    restore_p.add_argument(
        "--skip-contract",
        action="store_true",
        help="Skip contract_version gate (still verifies checksums/schema)",
    )

    dry_p = backup_sub.add_parser(
        "dry-run",
        help="Validate bundle and report conflict/remap without writing",
    )
    dry_p.add_argument("--input", "-i", required=True, help="Input .asbak path")
    dry_p.add_argument("--replace", action="store_true")
    dry_p.add_argument("--remap-tenant", default="")
    dry_p.add_argument("--remap-workspace", default="")
    dry_p.add_argument("--remap-project", default="")
    dry_p.add_argument("--skip-contract", action="store_true")

    status_p = backup_sub.add_parser("status", help="Show last backup job summary")
    status_p.add_argument("--json", action="store_true", help="Print JSON")

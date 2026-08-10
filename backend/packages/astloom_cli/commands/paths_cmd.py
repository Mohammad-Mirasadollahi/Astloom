"""`astloom paths` — list / add / remove pinned software roots."""

from __future__ import annotations

import argparse

from astloom_cli import ui
from astloom_cli.identity import peek_identity
from astloom_cli.software_paths import (
    normalize_software_paths,
    peek_software_paths,
    persist_software_paths,
)
from astloom_cli.util import print_json


def _require_active_scope() -> tuple[str, str, str]:
    identity = peek_identity()
    tenant = identity.get("tenant") or ""
    workspace = identity.get("workspace") or ""
    project = identity.get("project") or ""
    if not (tenant and workspace and project):
        raise SystemExit(
            "error: no active identity — run first:\n"
            "  astloom init --tenant … --workspace … --path /path/to/app"
        )
    return tenant, workspace, project


def cmd_paths_list(_args: argparse.Namespace) -> int:
    _require_active_scope()
    paths = peek_software_paths()
    ui.blank()
    ui.heading("Software paths")
    ui.blank()
    if not paths:
        ui.kv("Paths", ui.warn("none"))
        ui.next_steps(["astloom paths add /path/to/app"])
    else:
        ui.kv("Count", str(len(paths)))
        for p in paths:
            ui.bullet(p)
        ui.next_steps(
            [
                "astloom paths add /other/app",
                "astloom paths remove /path/to/drop",
                "astloom sync",
            ]
        )
    ui.blank()
    print_json({"ok": True, "paths": paths})
    return 0


def cmd_paths_add(args: argparse.Namespace) -> int:
    tenant, workspace, project = _require_active_scope()
    current = peek_software_paths()
    added = normalize_software_paths(list(args.path or []), must_exist=True)
    if not added:
        raise SystemExit("error: pass at least one path: astloom paths add /path/to/app")
    merged = normalize_software_paths([*current, *added], must_exist=True)
    paths = persist_software_paths(
        merged,
        tenant=tenant,
        workspace=workspace,
        project=project,
    )
    ui.blank()
    ui.heading("Paths updated")
    ui.blank()
    for p in added:
        ui.kv("Added", p)
    ui.section("Current roots")
    for p in paths:
        ui.bullet(p)
    ui.blank()
    print_json({"ok": True, "added": added, "paths": paths})
    return 0


def cmd_paths_remove(args: argparse.Namespace) -> int:
    tenant, workspace, project = _require_active_scope()
    current = peek_software_paths()
    if not current:
        raise SystemExit("error: no software paths pinned")
    remove = set(normalize_software_paths(list(args.path or []), must_exist=False))
    if not remove:
        raise SystemExit("error: pass at least one path: astloom paths remove /path/to/drop")
    missing = sorted(remove - set(current))
    if missing:
        raise SystemExit(
            "error: path(s) not in the pinned list:\n  "
            + "\n  ".join(missing)
            + "\n  Run: astloom paths list"
        )
    remaining = [p for p in current if p not in remove]
    if not remaining:
        raise SystemExit(
            "error: cannot remove the last software path\n"
            "  Add another root first, or re-init with --path, or destroy-profile"
        )

    ui.blank()
    ui.heading("Removing software path(s)", success=False)
    ui.blank()
    for p in sorted(remove):
        ui.bullet(p)
    ui.blank()
    ui.section("Warning")
    ui.bullet(
        "Graph data already indexed from these trees stays in the database for this scope."
    )
    ui.bullet(
        "Removing a path only stops future sync from that root — it does NOT delete old symbols/edges."
    )
    ui.bullet(
        "To wipe graph data for this scope: astloom purge --yes  (then sync remaining roots)."
    )
    ui.blank()

    paths = persist_software_paths(
        remaining,
        tenant=tenant,
        workspace=workspace,
        project=project,
    )
    ui.heading("Paths updated")
    ui.section("Remaining roots")
    for p in paths:
        ui.bullet(p)
    ui.blank()
    print_json(
        {
            "ok": True,
            "removed": sorted(remove),
            "paths": paths,
            "warning": (
                "Previously synced graph data for removed paths remains until "
                "astloom purge --yes"
            ),
        }
    )
    return 0

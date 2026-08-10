"""``init`` and software ``paths``."""

from __future__ import annotations

import argparse


def register_init(sub: argparse._SubParsersAction) -> None:
    init = sub.add_parser(
        "init",
        help="Create tenant + workspace, pin software path(s), then save them",
    )
    init.add_argument("--name", default="", help="Display name (default: OS username)")
    init.add_argument("--tenant", required=True, help="Tenant id you choose (e.g. acme)")
    init.add_argument("--workspace", required=True, help="First workspace id you choose (e.g. eng)")
    init.add_argument(
        "--project",
        default="",
        help="Project id you choose (default: current directory name)",
    )
    init.add_argument("--project-name", default="", help="Human project title")
    init.add_argument(
        "--path",
        action="append",
        default=[],
        help="Software root directory to sync (required on create; repeatable for multiple apps)",
    )
    init.add_argument(
        "--usage-profile",
        default="programming-cursor-mcp",
        help="Usage profile for the first project",
    )
    init.add_argument(
        "--force",
        action="store_true",
        help="Replace existing .astloom/identity.yaml",
    )


def register_paths(sub: argparse._SubParsersAction) -> None:
    paths = sub.add_parser(
        "paths",
        help="List / add / remove pinned software roots used by sync",
    )
    paths_sub = paths.add_subparsers(dest="paths_command", required=True)
    paths_sub.add_parser("list", help="Show pinned software paths")
    paths_add = paths_sub.add_parser("add", help="Add one or more software roots")
    paths_add.add_argument(
        "path",
        nargs="+",
        help="Directory path(s) to add",
    )
    paths_rm = paths_sub.add_parser(
        "remove",
        help="Remove software root(s); graph data for removed trees is kept until purge",
    )
    paths_rm.add_argument(
        "path",
        nargs="+",
        help="Directory path(s) to remove from the pin list",
    )

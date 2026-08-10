"""``client``, ``path``, ``ports``."""

from __future__ import annotations

import argparse


def register_client_and_path(sub: argparse._SubParsersAction) -> None:
    client = sub.add_parser("client", help="Local coding-agent MCP client helpers")
    client_sub = client.add_subparsers(dest="client_command", required=True)
    client_sub.add_parser("list-mcp-clients", help="List supported coding-agent MCP config targets")

    path_cmd = sub.add_parser("path", help="Install astloom onto user PATH")
    path_sub = path_cmd.add_subparsers(dest="path_command", required=True)
    install = path_sub.add_parser("install", help="Symlink ~/.local/bin/astloom -> thin or full CLI")
    install.add_argument(
        "--shell-rc",
        default="",
        help="Override rc file for PATH export (default: auto .bashrc+.profile or .zshrc; create if missing)",
    )
    install.add_argument(
        "--no-shell-rc",
        action="store_true",
        help="Only create the symlink; do not modify shell rc files",
    )
    install.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress human status lines and JSON summary (errors still print)",
    )


def register(sub: argparse._SubParsersAction) -> None:
    register_client_and_path(sub)

    ports = sub.add_parser("ports", help="Port profile preflight")
    ports_sub = ports.add_subparsers(dest="ports_command", required=True)
    ports_show = ports_sub.add_parser("show", help="Show resolved ports from profile (env overrides)")
    ports_show.add_argument("--profile", default="", help="Port profile JSON path (default: astloom-dev)")
    ports_check = ports_sub.add_parser(
        "check",
        help="Preflight: bind check, owning process (ss/lsof), alternate ports; exit 1 on conflict",
    )
    ports_check.add_argument("--profile", default="", help="Port profile JSON path (default: astloom-dev)")
    ports_check.add_argument(
        "--write-map",
        nargs="?",
        const="1",
        default="",
        help="Write resolved port-map JSON (default path: .astloom/run/port-map.json)",
    )
    ports_check.add_argument(
        "--allow-ours",
        action="store_true",
        help="Do not block when the listener looks like an Astloom/docker-proxy process",
    )

"""``profile``, ``project``, ``cursor``, ``mcp``."""

from __future__ import annotations

import argparse

from astloom_cli.util import add_scope_args


def register_profile_and_project(sub: argparse._SubParsersAction) -> None:
    profile = sub.add_parser("profile", help="Usage Profile catalog commands")
    profile_sub = profile.add_subparsers(dest="profile_command", required=False)
    profile_sub.add_parser("list", help="List Usage Profiles (default)")
    show = profile_sub.add_parser("show", help="Show one Usage Profile JSON")
    show.add_argument("profile_id")

    project = sub.add_parser("project", help="Local project + Usage Profile state")
    project_sub = project.add_subparsers(dest="project_command", required=True)

    reg = project_sub.add_parser("register", help="Register a local project state file")
    add_scope_args(reg)
    reg.add_argument("--name", default="")
    reg.add_argument("--usage-profile", default="programming-cursor-mcp")
    reg.add_argument("--domain-pack", default="")
    reg.add_argument("--feature-profile", default="")
    reg.add_argument("--force", action="store_true")

    act = project_sub.add_parser("activate", help="Activate a Usage Profile on a project")
    add_scope_args(act)
    act.add_argument("--usage-profile", required=True)
    act.add_argument("--apply-catalog-defaults", action=argparse.BooleanOptionalAction, default=True)

    show_p = project_sub.add_parser("show", help="Show local project state")
    add_scope_args(show_p)
    eff = project_sub.add_parser("effective", help="Resolve effective Usage Profile")
    add_scope_args(eff)


def register(sub: argparse._SubParsersAction) -> None:
    register_profile_and_project(sub)

    cursor = sub.add_parser("cursor", help="Cursor MCP helpers")
    cursor_sub = cursor.add_subparsers(dest="cursor_command", required=True)
    export = cursor_sub.add_parser("export", help="Export mcpServers fragment for Cursor")
    add_scope_args(export)
    export.add_argument("--out", default="", help="Write JSON to this path")

    mcp = sub.add_parser("mcp", help="MCP gateway helpers")
    mcp_sub = mcp.add_subparsers(dest="mcp_command", required=True)
    tools = mcp_sub.add_parser("tools", help="List MCP tools for a Usage Profile")
    tools.add_argument("--usage-profile", default="programming-cursor-mcp")
    tokens = mcp_sub.add_parser(
        "tokens",
        help="Estimate MCP connect token cost + usage history by client/scope id",
    )
    tokens.add_argument("--usage-profile", default="programming-cursor-mcp")
    tokens.add_argument(
        "--since",
        "-s",
        default="",
        help="History start: 24h, 7d, 30d, or ISO (default: 7d)",
    )
    tokens.add_argument("--until", "-u", default="", help="History end ISO (default: now)")
    tokens.add_argument(
        "--clients",
        default="all",
        help="Client ids: all or comma-separated (cursor,vscode,…)",
    )
    tokens.add_argument(
        "--id",
        default="all",
        help="Scope ids for history: all or tenant/workspace/project[,…]",
    )
    tokens.add_argument(
        "--project-dir",
        default="",
        help="App repo root for client wiring check (default: cwd)",
    )
    tokens.add_argument(
        "--include-user-clients",
        action="store_true",
        help="Also check user-global MCP configs (cursor-user, claude-desktop)",
    )
    tokens.add_argument(
        "--format",
        "-f",
        choices=("text", "json"),
        default="text",
        help="Output format",
    )
    serve = mcp_sub.add_parser("serve", help="Run MCP gateway on stdio for a project scope")
    add_scope_args(serve)
    serve.add_argument("--usage-profile", default="")
    serve_http = mcp_sub.add_parser(
        "serve-http",
        help="Run Streamable HTTP MCP gateway (Phase B; concurrent agents)",
    )
    serve_http.add_argument("--host", default="")
    serve_http.add_argument("--port", type=int, default=0)
    serve_http.add_argument("--usage-profile", default="programming-cursor-mcp")

"""``service`` and ``boot`` subcommands."""

from __future__ import annotations

import argparse


def register(sub: argparse._SubParsersAction) -> None:
    service = sub.add_parser(
        "service",
        help="Start/stop/restart/status for Compose infra + MCP HTTP backend",
    )
    service_sub = service.add_subparsers(dest="service_command", required=True)
    service_start = service_sub.add_parser("start", help="Start postgres/neo4j + MCP HTTP daemon")
    service_start.add_argument("--json", action="store_true", help="Print JSON only")
    service_stop = service_sub.add_parser("stop", help="Stop MCP HTTP daemon + postgres/neo4j")
    service_stop.add_argument("--json", action="store_true", help="Print JSON only")
    service_restart = service_sub.add_parser("restart", help="Restart Compose infra + MCP HTTP")
    service_restart.add_argument("--json", action="store_true", help="Print JSON only")
    service_status = service_sub.add_parser(
        "status",
        help="Show Compose + MCP HTTP + boot enablement",
    )
    service_status.add_argument("--json", action="store_true", help="Print JSON only")
    service_detail = service_sub.add_parser(
        "detail",
        help="Status plus MCP HTTP / unhealthy Compose log tails (for failed starts)",
    )
    service_detail.add_argument("--json", action="store_true", help="Print JSON only")

    boot = sub.add_parser("boot", help="Enable/disable Astloom start on system boot")
    boot_sub = boot.add_subparsers(dest="boot_command", required=True)
    boot_enable = boot_sub.add_parser("enable", help="Install and enable systemd unit")
    boot_enable.add_argument(
        "--user",
        action="store_true",
        help="Use systemd --user unit (~/.config/systemd/user)",
    )
    boot_disable = boot_sub.add_parser("disable", help="Disable and remove systemd unit")
    boot_disable.add_argument(
        "--user",
        action="store_true",
        help="Target systemd --user unit",
    )

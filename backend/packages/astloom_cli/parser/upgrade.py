"""``upgrade`` CLI parser — server install, client refresh, control-plane jobs."""

from __future__ import annotations

import argparse

from astloom_cli.util import add_scope_args


def register_upgrade_client(sub: argparse._SubParsersAction) -> None:
    """Register client-safe upgrade subcommands (``client`` + ``finalize``)."""
    upgrade = sub.add_parser(
        "upgrade",
        help="Client CLI refresh and install finalize stamp",
    )
    up_sub = upgrade.add_subparsers(dest="upgrade_command", required=True)
    client = up_sub.add_parser("client", help="Refresh client CLI + optional connect rewire")
    client.add_argument("--project-dir", default="", help="App repo with connect.yaml (default cwd)")
    client.add_argument("--from-ping", default="", help="Optional server ping JSON for compat check")
    client.add_argument("--skip-venv", action="store_true")
    client.add_argument("--skip-connect", action="store_true")
    finalize = up_sub.add_parser(
        "finalize",
        help="Stamp versions/evidence after install.sh --upgrade (client or server)",
    )
    finalize.add_argument("--job-id", default="")
    finalize.add_argument("--runtime", default="")


def register(sub: argparse._SubParsersAction) -> None:
    upgrade = sub.add_parser(
        "upgrade",
        help="Upgrade Astloom server/client and run control-plane upgrade jobs",
    )
    up_sub = upgrade.add_subparsers(dest="upgrade_command", required=True)

    versions = up_sub.add_parser("versions", help="Show local product/contract versions")
    versions.set_defaults(upgrade_command="versions")

    check = up_sub.add_parser("check", help="Compare client vs server contract/product versions")
    check.add_argument("--from-ping", default="", help="JSON file from platform.ping structuredContent")
    check.add_argument(
        "--assume-local-server",
        action="store_true",
        help="Compare against this checkout's advertised server versions",
    )
    check.add_argument("--server-product", default="")
    check.add_argument("--server-contract", default="")
    check.add_argument("--min-client-contract", default="")

    plan = up_sub.add_parser("plan", help="Build an upgrade plan from install-state")
    plan.add_argument("--target", default="", help="Target product version (default: current)")
    plan.add_argument(
        "--mode",
        choices=["local", "control-plane", "client"],
        default="local",
    )
    plan.add_argument(
        "--risk-level",
        choices=["low", "medium", "high", "critical"],
        default="medium",
    )

    prepare = up_sub.add_parser("prepare", help="Create durable upgrade job (+ approval when required)")
    add_scope_args(prepare, required=False)
    prepare.add_argument("--target", default="")
    prepare.add_argument(
        "--mode",
        choices=["local", "control-plane", "client"],
        default="local",
    )
    prepare.add_argument(
        "--risk-level",
        choices=["low", "medium", "high", "critical"],
        default="medium",
    )
    prepare.add_argument("--actor", default="cli")
    prepare.add_argument("--no-approval", action="store_true", help="Do not enqueue Accept gate")

    run = up_sub.add_parser("run", help="Prepare (optional) and execute an upgrade job")
    add_scope_args(run, required=False)
    run.add_argument("job_id", nargs="?", default="", help="Existing job id (omit to prepare+run)")
    run.add_argument("--target", default="")
    run.add_argument(
        "--mode",
        choices=["local", "control-plane"],
        default="local",
    )
    run.add_argument(
        "--risk-level",
        choices=["low", "medium", "high", "critical"],
        default="medium",
    )
    run.add_argument("--actor", default="cli")
    run.add_argument("--no-approval", action="store_true")
    run.add_argument("--yes", action="store_true", help="Allow local non-critical without approval")
    run.add_argument(
        "--skip-deploy",
        action="store_true",
        help="Skip install.sh (tests / finalize-only)",
    )

    status = up_sub.add_parser("status", help="Show one upgrade job")
    status.add_argument("job_id")

    rollback = up_sub.add_parser("rollback", help="Restore install-state.env from job backup")
    rollback.add_argument("job_id")

    finalize = up_sub.add_parser(
        "finalize",
        help="Stamp versions/evidence after install.sh --upgrade",
    )
    finalize.add_argument("--job-id", default="")
    finalize.add_argument("--runtime", default="")

    client = up_sub.add_parser("client", help="Refresh client CLI + optional connect rewire")
    client.add_argument("--project-dir", default="", help="App repo with connect.yaml (default cwd)")
    client.add_argument("--from-ping", default="", help="Optional server ping JSON for compat check")
    client.add_argument("--skip-venv", action="store_true")
    client.add_argument("--skip-connect", action="store_true")

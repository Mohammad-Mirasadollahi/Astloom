"""Argument parser for the thin client CLI (allowlisted commands only)."""

from __future__ import annotations

import argparse

from astloom_cli.parser import profiles, remote, reporting, sync_llm, upgrade
from astloom_cli.parser._core import AstloomArgumentParser


def build_parser() -> argparse.ArgumentParser:
    parser = AstloomArgumentParser(
        prog="astloom-client",
        description=(
            "Astloom client CLI — connect, Usage Profile, and process control "
            "(sync/purge/status) for your scope on the Astloom server"
        ),
    )
    parser.add_argument("--version", action="store_true", help="Show version")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("version", help="Show CLI version and repo root")
    sub.add_parser("doctor", help="Check venv, imports, profiles, and PATH")
    reporting.register_status(sub)
    sync_llm.register_connect(sub)
    sync_llm.register_sync(sub)
    sync_llm.register_purge(sub)
    profiles.register_profile_and_project(sub)
    remote.register_client_and_path(sub)
    upgrade.register_upgrade_client(sub)

    return parser

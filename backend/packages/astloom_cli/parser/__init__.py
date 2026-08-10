"""Argument parser for the astloom CLI.

Split by domain under ``astloom_cli.parser``; public entry is ``build_parser``.
"""

from __future__ import annotations

import argparse

from astloom_cli.parser import (
    backup,
    governance,
    graph,
    identity,
    profiles,
    remote,
    reporting,
    service,
    sync_llm,
    upgrade,
)
from astloom_cli.parser._core import AstloomArgumentParser

__all__ = ["build_parser"]


def build_parser() -> argparse.ArgumentParser:
    parser = AstloomArgumentParser(
        prog="astloom",
        description="Astloom CLI — manage Usage Profiles, projects, and Cursor MCP",
    )
    parser.add_argument("--version", action="store_true", help="Show version")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("version", help="Show CLI version and repo root")
    sub.add_parser("doctor", help="Check venv, imports, profiles, and PATH")

    # Registration order matches historical help listing.
    service.register(sub)
    identity.register_init(sub)
    reporting.register(sub)
    sync_llm.register(sub)
    identity.register_paths(sub)
    profiles.register(sub)
    remote.register(sub)
    graph.register(sub)
    governance.register(sub)
    upgrade.register(sub)
    backup.register(sub)

    return parser

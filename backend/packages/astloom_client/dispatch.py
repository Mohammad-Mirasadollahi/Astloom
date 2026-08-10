"""Dispatch allowlisted client commands to astloom_cli handlers."""

from __future__ import annotations

import argparse

from astloom_cli.commands.client import cmd_client_list_mcp_clients
from astloom_cli.commands.connect import cmd_connect
from astloom_cli.commands.doctor import cmd_doctor, cmd_version
from astloom_cli.commands.path_cmd import cmd_path_install
from astloom_cli.commands.profile import cmd_profile_list, cmd_profile_show
from astloom_cli.commands.project import (
    cmd_project_activate,
    cmd_project_effective,
    cmd_project_register,
    cmd_project_show,
)
from astloom_cli.commands.status import cmd_status
from astloom_cli.commands.sync import cmd_purge, cmd_sync
from astloom_cli.commands.upgrade import cmd_upgrade_client, cmd_upgrade_finalize


def dispatch(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.version and not args.command:
        return cmd_version(args)
    if not args.command:
        parser.print_help()
        return 2
    if args.command == "version":
        return cmd_version(args)
    if args.command == "doctor":
        return cmd_doctor(args)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "connect":
        return cmd_connect(args)
    if args.command == "sync":
        return cmd_sync(args)
    if args.command == "purge":
        return cmd_purge(args)
    if args.command == "profile":
        if args.profile_command in (None, "list"):
            return cmd_profile_list(args)
        if args.profile_command == "show":
            return cmd_profile_show(args)
    if args.command == "project":
        if args.project_command == "register":
            return cmd_project_register(args)
        if args.project_command == "activate":
            return cmd_project_activate(args)
        if args.project_command == "show":
            return cmd_project_show(args)
        if args.project_command == "effective":
            return cmd_project_effective(args)
    if args.command == "client":
        if args.client_command == "list-mcp-clients":
            return cmd_client_list_mcp_clients(args)
    if args.command == "path":
        if args.path_command == "install":
            return cmd_path_install(args)
    if args.command == "upgrade":
        if args.upgrade_command == "client":
            return cmd_upgrade_client(args)
        if args.upgrade_command == "finalize":
            return cmd_upgrade_finalize(args)
    parser.print_help()
    return 2

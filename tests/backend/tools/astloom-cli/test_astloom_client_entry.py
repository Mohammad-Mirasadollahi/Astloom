"""Tests for thin astloom-client entry."""

from __future__ import annotations

import pytest

from astloom_client.parser import build_parser


def test_thin_help_omits_server_commands():
    parser = build_parser()
    help_text = parser.format_help()
    assert "connect" in help_text
    assert "purge" in help_text
    assert "sync" in help_text
    for banned in ("service", "graph", "approval", "inventory", "mcp", "boot"):
        # Subparser choices appear in help; ensure top-level banned names absent as commands.
        assert f"  {banned} " not in help_text and f"{{{banned}" not in help_text.replace(" ", "")


def test_thin_rejects_service_command():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["service", "start"])


def test_thin_parses_purge_yes():
    parser = build_parser()
    args = parser.parse_args(["purge", "--yes"])
    assert args.command == "purge"
    assert args.yes is True


def test_thin_upgrade_client_and_finalize():
    parser = build_parser()
    args = parser.parse_args(["upgrade", "client"])
    assert args.upgrade_command == "client"
    args_f = parser.parse_args(["upgrade", "finalize", "--runtime", "host"])
    assert args_f.upgrade_command == "finalize"
    assert args_f.runtime == "host"
    with pytest.raises(SystemExit):
        parser.parse_args(["upgrade", "run"])

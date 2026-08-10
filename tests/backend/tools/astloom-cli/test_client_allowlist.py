"""Tests for client-only command allowlist and full-CLI role gate."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from astloom_cli.client_allowlist import (
    CLIENT_TOP_LEVEL_COMMANDS,
    client_command_allowed,
    deny_message_for_client_role,
)


def test_client_allowlist_includes_process_and_profile_commands():
    for name in (
        "connect",
        "profile",
        "project",
        "sync",
        "purge",
        "status",
        "version",
        "doctor",
        "client",
        "path",
        "upgrade",
    ):
        assert name in CLIENT_TOP_LEVEL_COMMANDS


def test_client_allowlist_excludes_server_admin():
    for name in ("service", "boot", "graph", "mcp", "approval", "inventory", "llm"):
        assert name not in CLIENT_TOP_LEVEL_COMMANDS


def test_upgrade_client_safe_subcommands_allowed():
    assert client_command_allowed("upgrade", Namespace(upgrade_command="client"))
    assert client_command_allowed("upgrade", Namespace(upgrade_command="finalize"))
    assert not client_command_allowed("upgrade", Namespace(upgrade_command="run"))
    assert not client_command_allowed("upgrade", Namespace(upgrade_command="prepare"))


def test_full_cli_denies_graph_when_role_client(monkeypatch, tmp_path: Path):
    from astloom_cli import main as main_mod

    state = tmp_path / "install-state.env"
    state.write_text("role=client\n", encoding="utf-8")
    monkeypatch.setattr(main_mod, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        "astloom_cli.service_runtime.paths.install_role",
        lambda _root: "client",
    )
    assert (
        main_mod.main(["graph", "freshness", "--tenant", "t", "--workspace", "w", "--project", "p"])
        == 2
    )
    assert "client" in deny_message_for_client_role("graph").lower()


def test_full_cli_allows_upgrade_finalize_when_role_client(monkeypatch):
    from astloom_cli import main as main_mod

    monkeypatch.setattr(
        "astloom_cli.service_runtime.paths.install_role",
        lambda _root: "client",
    )
    called = {"n": 0}

    def _fake_finalize(args):
        called["n"] += 1
        return 0

    monkeypatch.setattr(main_mod, "cmd_upgrade_finalize", _fake_finalize)
    assert main_mod.main(["upgrade", "finalize", "--runtime", "host"]) == 0
    assert called["n"] == 1


def test_full_cli_allows_graph_when_role_server(monkeypatch):
    from astloom_cli import main as main_mod

    monkeypatch.setattr(
        "astloom_cli.service_runtime.paths.install_role",
        lambda _root: "server",
    )
    called = {"n": 0}

    def _fake_freshness(args):
        called["n"] += 1
        return 0

    monkeypatch.setattr(main_mod, "cmd_graph_freshness", _fake_freshness)
    assert main_mod.main(["graph", "freshness", "--tenant", "t", "--workspace", "w", "--project", "p"]) == 0
    assert called["n"] == 1

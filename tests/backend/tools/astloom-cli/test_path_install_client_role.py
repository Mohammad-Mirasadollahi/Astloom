"""Client role PATH shim is astloom-client only (no bare astloom)."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path


def test_path_install_client_role_uses_thin_name_only(monkeypatch, tmp_path: Path):
    from astloom_cli.commands import path_cmd

    root = tmp_path / "Astloom"
    venv_bin = root / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    thin = venv_bin / "astloom-client"
    thin.write_text("#!/bin/sh\n", encoding="utf-8")
    thin.chmod(0o755)
    full = venv_bin / "astloom"
    full.write_text("#!/bin/sh\n", encoding="utf-8")
    full.chmod(0o755)

    home = tmp_path / "home"
    home.mkdir()
    local_bin = home / ".local" / "bin"
    local_bin.mkdir(parents=True)
    stale = local_bin / "astloom"
    stale.symlink_to(full)

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(path_cmd, "repo_root", lambda: root)
    monkeypatch.setattr(
        "astloom_cli.service_runtime.paths.install_role",
        lambda _r: "client",
    )

    assert path_cmd.cmd_path_install(Namespace(quiet=True, no_shell_rc=True, shell_rc="")) == 0
    thin_link = local_bin / "astloom-client"
    assert thin_link.is_symlink()
    assert thin_link.resolve() == thin.resolve()
    assert not (local_bin / "astloom").exists()


def test_path_install_server_role_uses_full_name_only(monkeypatch, tmp_path: Path):
    from astloom_cli.commands import path_cmd

    root = tmp_path / "Astloom"
    venv_bin = root / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    thin = venv_bin / "astloom-client"
    thin.write_text("#!/bin/sh\n", encoding="utf-8")
    thin.chmod(0o755)
    full = venv_bin / "astloom"
    full.write_text("#!/bin/sh\n", encoding="utf-8")
    full.chmod(0o755)

    home = tmp_path / "home"
    home.mkdir()
    local_bin = home / ".local" / "bin"
    local_bin.mkdir(parents=True)
    stale_thin = local_bin / "astloom-client"
    stale_thin.symlink_to(thin)

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(path_cmd, "repo_root", lambda: root)
    monkeypatch.setattr(
        "astloom_cli.service_runtime.paths.install_role",
        lambda _r: "both",
    )

    assert path_cmd.cmd_path_install(Namespace(quiet=True, no_shell_rc=True, shell_rc="")) == 0
    full_link = local_bin / "astloom"
    assert full_link.is_symlink()
    assert full_link.resolve() == full.resolve()
    assert not (local_bin / "astloom-client").exists()

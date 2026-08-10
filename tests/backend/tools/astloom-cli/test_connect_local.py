"""Tests for local (same-host) MCP connect fragment."""

from __future__ import annotations

import json
from pathlib import Path

from astloom_cli.connect_config import load_connect_settings
from astloom_cli.local_mcp import materialize_local_stdio_fragment


def test_load_connect_settings_local_without_https(tmp_path: Path, monkeypatch):
    cfg = tmp_path / "connect.json"
    cfg.write_text(
        json.dumps(
            {
                "server": {"local": True, "remote_root": "/opt/Astloom"},
                "scope": {"tenant": "astloom", "workspace": "dev", "project": "Astloom"},
                "connect": {"prefer_http": False},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    settings = load_connect_settings(config_path=str(cfg))
    assert settings.local is True
    assert settings.api_url == ""
    assert settings.project == "Astloom"


def test_settings_for_local_uses_identity_scope(tmp_path: Path, monkeypatch):
    from argparse import Namespace

    from astloom_cli.commands.connect import _settings_for_local

    monkeypatch.setattr("astloom_cli.cli_defaults.load_dotenv_files", lambda **_: [])
    monkeypatch.setattr("astloom_cli.cli_defaults.peek_connect_scope", lambda: {})
    monkeypatch.setattr(
        "astloom_cli.cli_defaults.peek_identity_scope",
        lambda: {"tenant": "acme", "workspace": "eng", "project": "payments"},
    )
    monkeypatch.delenv("ASTLOOM_TENANT_ID", raising=False)
    monkeypatch.delenv("ASTLOOM_WORKSPACE_ID", raising=False)
    monkeypatch.delenv("ASTLOOM_PROJECT_ID", raising=False)
    monkeypatch.chdir(tmp_path)
    args = Namespace(
        tenant="",
        workspace="",
        project="",
        remote_root="",
        clients="all",
        include_user_clients=False,
    )
    settings = _settings_for_local(args, work=tmp_path)
    assert settings.tenant == "acme"
    assert settings.workspace == "eng"
    assert settings.project == "payments"
    assert settings.local is True


def test_source_path_for_connect_remote_does_not_use_client_cwd(tmp_path: Path):
    from astloom_cli.connect_flow.source_path import source_path_for_connect

    assert source_path_for_connect(local=False, work=tmp_path) == ""
    assert source_path_for_connect(local=True, work=tmp_path) == str(tmp_path)
    assert (
        source_path_for_connect(
            local=False,
            work=tmp_path,
            configured="/srv/repos/MyApp",
        )
        == "/srv/repos/MyApp"
    )


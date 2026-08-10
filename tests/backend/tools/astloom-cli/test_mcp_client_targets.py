"""Tests for multi–coding-agent MCP config targets."""

from __future__ import annotations

import json
from pathlib import Path

from astloom_cli.main import main
from astloom_cli.mcp_client_targets import (
    PROJECT_CLIENTS_ALL,
    resolve_client_ids,
    write_fragment_to_clients,
)


def test_resolve_client_ids_all():
    assert resolve_client_ids("all") == list(PROJECT_CLIENTS_ALL)


def test_resolve_client_ids_unknown():
    try:
        resolve_client_ids("not-a-client")
    except SystemExit as exc:
        assert "unknown" in str(exc).lower()
    else:
        raise AssertionError("expected SystemExit")


def test_write_fragment_to_clients_all_project_targets(tmp_path: Path):
    fragment = {
        "mcpServers": {
            "Astloom-Programming": {"command": "ssh", "args": ["u@h", "serve"]},
        }
    }
    written = write_fragment_to_clients(tmp_path, fragment, resolve_client_ids("all"))
    assert (tmp_path / ".cursor" / "mcp.json").is_file()
    assert (tmp_path / ".vscode" / "mcp.json").is_file()
    assert (tmp_path / ".astloom" / "mcp-servers.json").is_file()
    assert len(written) == len(PROJECT_CLIENTS_ALL)
    cursor = json.loads((tmp_path / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
    assert "Astloom-Programming" in cursor["mcpServers"]


def test_list_mcp_clients_command(capsys):
    assert main(["client", "list-mcp-clients"]) == 0
    payload = json.loads(capsys.readouterr().out)
    ids = {row["client_id"] for row in payload}
    assert "cursor" in ids
    assert "windsurf" in ids
    assert "claude-code" in ids

"""Tests for connect security helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from astloom_cli.connect_security import atomic_write_text, reject_secrets_in_connect_doc
from astloom_cli.mcp_client_targets import merge_mcp_servers_file


def test_reject_password_in_connect_doc():
    with pytest.raises(SystemExit):
        reject_secrets_in_connect_doc({"auth": {"password": "secret"}}, Path("/tmp/x.yaml"))


def test_atomic_merge_preserves_other_servers(tmp_path: Path):
    target = tmp_path / ".cursor" / "mcp.json"
    target.parent.mkdir(parents=True)
    target.write_text(
        json.dumps({"mcpServers": {"other": {"command": "echo", "args": []}}}) + "\n",
        encoding="utf-8",
    )
    fragment = {
        "mcpServers": {
            "Astloom-Programming": {"command": "ssh", "args": ["u@h", "serve"]},
        }
    }
    merge_mcp_servers_file(target, fragment)
    merged = json.loads(target.read_text(encoding="utf-8"))
    assert "other" in merged["mcpServers"]
    assert "Astloom-Programming" in merged["mcpServers"]


def test_atomic_write_text(tmp_path: Path):
    path = tmp_path / "out.json"
    atomic_write_text(path, "{}\n")
    assert path.read_text(encoding="utf-8") == "{}\n"

"""Tests for destroy-profile (interactive confirm + profile data cleanup)."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

from astloom_cli import state
from astloom_cli.commands.destroy_cmd import (
    CONFIRM_PHRASE_1,
    cmd_destroy_profile,
    confirm_destroy_interactively,
    destroy_profile_data,
)
from astloom_cli.identity import (
    clear_identity_if_matches,
    clear_repo_env_scope_if_matches,
    write_identity,
    write_repo_env_scope,
)
from astloom_cli.parser import build_parser


def test_parser_destroy_profile_has_no_yes_flag():
    parser = build_parser()
    args = parser.parse_args(
        ["destroy-profile", "--tenant", "acme", "--workspace", "eng", "--project", "app"]
    )
    assert args.command == "destroy-profile"
    assert not hasattr(args, "yes")


def test_confirm_rejects_wrong_first_phrase(monkeypatch):
    answers = iter(["wrong", "acme/eng/app"])
    monkeypatch.setattr("astloom_cli.commands.destroy_cmd.sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("astloom_cli.commands.destroy_cmd._read_confirm", lambda _p: next(answers))
    with pytest.raises(SystemExit) as exc:
        confirm_destroy_interactively(tenant="acme", workspace="eng", project="app")
    assert "confirmation 1 failed" in str(exc.value)
    assert "Nothing was deleted" in str(exc.value)


def test_confirm_rejects_wrong_second_phrase(monkeypatch):
    answers = iter([CONFIRM_PHRASE_1, "other/scope/x"])
    monkeypatch.setattr("astloom_cli.commands.destroy_cmd.sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("astloom_cli.commands.destroy_cmd._read_confirm", lambda _p: next(answers))
    with pytest.raises(SystemExit) as exc:
        confirm_destroy_interactively(tenant="acme", workspace="eng", project="app")
    assert "confirmation 2 failed" in str(exc.value)


def test_confirm_accepts_two_different_phrases(monkeypatch):
    answers = iter([CONFIRM_PHRASE_1, "acme/eng/app"])
    monkeypatch.setattr("astloom_cli.commands.destroy_cmd.sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("astloom_cli.commands.destroy_cmd._read_confirm", lambda _p: next(answers))
    confirm_destroy_interactively(tenant="acme", workspace="eng", project="app")


def test_cmd_destroy_profile_runs_after_confirm(monkeypatch):
    monkeypatch.setattr(
        "astloom_cli.commands.destroy_cmd.confirm_destroy_interactively",
        lambda **_: None,
    )
    monkeypatch.setattr(
        "astloom_cli.commands.destroy_cmd.destroy_profile_data",
        lambda **kw: {"ok": True, "scope": kw},
    )
    monkeypatch.setattr(
        "astloom_cli.commands.destroy_cmd.require_scope",
        lambda args, with_defaults=True: ("acme", "eng", "app"),
    )
    code = cmd_destroy_profile(Namespace(tenant="acme", workspace="eng", project="app"))
    assert code == 0


def test_destroy_profile_data_clears_pins_not_source(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("astloom_cli.util.repo_root", lambda: tmp_path)
    monkeypatch.setattr("astloom_cli.identity.Path.home", lambda: tmp_path)
    monkeypatch.setattr("astloom_cli.commands.destroy_cmd.repo_root", lambda: tmp_path)
    source = tmp_path / "src" / "app.py"
    source.parent.mkdir(parents=True)
    source.write_text("print('keep')\n", encoding="utf-8")

    write_identity(tenant="acme", workspace="eng", project="app", display_name="Ali")
    write_repo_env_scope(tmp_path, tenant="acme", workspace="eng", project="app")
    projects = state.default_state_root(tmp_path)
    state.save_project(
        projects,
        {
            "tenant_id": "acme",
            "workspace_id": "eng",
            "project_id": "app",
            "name": "app",
            "usage_profile": "programming-cursor-mcp",
            "status": "active",
        },
    )
    mcp = tmp_path / ".cursor" / "mcp.json"
    mcp.parent.mkdir(parents=True)
    mcp.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "astloom-programming": {"command": "x"},
                    "other": {"command": "y"},
                }
            }
        ),
        encoding="utf-8",
    )

    report = destroy_profile_data(
        tenant="acme",
        workspace="eng",
        project="app",
        cwd=tmp_path,
        wipe_graph=False,
    )
    assert report["deleted_source_code"] is False
    assert source.is_file()
    assert source.read_text(encoding="utf-8") == "print('keep')\n"
    assert report["project_state_deleted"] is True
    assert report["identity_cleared"] is True
    assert report["env_cleared"] is True
    assert "ASTLOOM_TENANT_ID" not in (tmp_path / ".env").read_text(encoding="utf-8")
    mcp_doc = json.loads(mcp.read_text(encoding="utf-8"))
    assert "astloom-programming" not in mcp_doc["mcpServers"]
    assert "other" in mcp_doc["mcpServers"]


def test_clear_identity_skips_other_scope(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("astloom_cli.util.repo_root", lambda: tmp_path)
    monkeypatch.setattr("astloom_cli.identity.Path.home", lambda: tmp_path)
    write_identity(tenant="acme", workspace="eng", project="app")
    assert clear_identity_if_matches(tenant="other", workspace="eng", project="app") is False
    assert (tmp_path / ".astloom" / "identity.yaml").is_file()


def test_clear_env_skips_mismatched_scope(tmp_path: Path):
    write_repo_env_scope(tmp_path, tenant="acme", workspace="eng", project="app")
    assert clear_repo_env_scope_if_matches(tmp_path, tenant="x", workspace="eng", project="app") is False
    text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "ASTLOOM_TENANT_ID=acme" in text

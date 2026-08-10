"""Tests for astloom init / identity."""

from __future__ import annotations

from pathlib import Path

from astloom_cli.cli_defaults import resolve_operator_scope
from astloom_cli.identity import peek_identity, slugify, write_identity
from astloom_cli.parser import build_parser


def test_slugify():
    assert slugify("Ali Reza!") == "ali-reza"
    assert slugify("") == "user"


def test_slugify_empty_fallback_blank():
    assert slugify("", fallback="") == ""


def test_write_and_peek_identity(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("astloom_cli.util.repo_root", lambda: tmp_path)
    monkeypatch.setattr("astloom_cli.identity.Path.home", lambda: tmp_path)
    path = write_identity(tenant="acme", workspace="eng", project="myapp", display_name="Ali")
    assert path.is_file()
    data = peek_identity()
    assert data["tenant"] == "acme"
    assert data["workspace"] == "eng"
    assert data["project"] == "myapp"


def test_resolve_prefers_identity(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("astloom_cli.cli_defaults.load_dotenv_files", lambda **_: [])
    monkeypatch.setattr("astloom_cli.cli_defaults.peek_connect_scope", lambda: {})
    monkeypatch.setattr(
        "astloom_cli.cli_defaults.peek_identity_scope",
        lambda: {"tenant": "from-id", "workspace": "ws", "project": "p1"},
    )
    monkeypatch.delenv("ASTLOOM_TENANT_ID", raising=False)
    monkeypatch.delenv("ASTLOOM_WORKSPACE_ID", raising=False)
    monkeypatch.delenv("ASTLOOM_PROJECT_ID", raising=False)
    t, w, p = resolve_operator_scope(cwd=tmp_path)
    assert (t, w, p) == ("from-id", "ws", "p1")


def test_parser_init_requires_tenant_workspace():
    parser = build_parser()
    args = parser.parse_args(
        ["init", "--tenant", "acme", "--workspace", "eng", "--path", ".", "--name", "Ali"]
    )
    assert args.command == "init"
    assert args.tenant == "acme"
    assert args.workspace == "eng"
    assert args.path == ["."]
    try:
        parser.parse_args(["init", "--name", "Ali"])
        raise AssertionError("expected SystemExit when --tenant/--workspace missing")
    except SystemExit:
        pass

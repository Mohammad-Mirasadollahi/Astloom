"""Tests for pinned software paths (init / paths / sync resolve)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from astloom_cli.parser import build_parser
from astloom_cli.software_paths import (
    peek_software_paths,
    persist_software_paths,
    require_software_paths,
    software_paths_for_project,
)
from astloom_cli.commands.paths_cmd import cmd_paths_remove


def test_persist_and_peek_paths(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("astloom_cli.software_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("astloom_cli.util.repo_root", lambda: tmp_path)
    monkeypatch.setattr("astloom_cli.identity.Path.home", lambda: tmp_path)
    app = tmp_path / "app"
    app.mkdir()
    paths = persist_software_paths(
        [str(app)],
        tenant="acme",
        workspace="eng",
        project="myapp",
        display_name="Ali",
    )
    assert paths == [str(app.resolve())]
    assert peek_software_paths() == [str(app.resolve())]
    id_doc = yaml.safe_load((tmp_path / ".astloom" / "identity.yaml").read_text(encoding="utf-8"))
    assert id_doc["paths"] == [str(app.resolve())]
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "ASTLOOM_SOFTWARE_PATHS=" in env


def test_require_paths_errors_when_empty(monkeypatch):
    monkeypatch.setattr(
        "astloom_cli.software_paths.peek_software_paths",
        lambda: [],
    )
    with pytest.raises(SystemExit) as exc:
        require_software_paths()
    assert "no software path configured" in str(exc.value)


def test_paths_remove_warns_and_keeps_other(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("astloom_cli.software_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("astloom_cli.util.repo_root", lambda: tmp_path)
    monkeypatch.setattr("astloom_cli.identity.Path.home", lambda: tmp_path)
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    persist_software_paths(
        [str(a), str(b)],
        tenant="acme",
        workspace="eng",
        project="myapp",
    )
    args = build_parser().parse_args(["paths", "remove", str(a)])
    code = cmd_paths_remove(args)
    assert code == 0
    assert peek_software_paths() == [str(b.resolve())]


def test_paths_remove_last_rejected(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("astloom_cli.software_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("astloom_cli.util.repo_root", lambda: tmp_path)
    monkeypatch.setattr("astloom_cli.identity.Path.home", lambda: tmp_path)
    a = tmp_path / "a"
    a.mkdir()
    persist_software_paths([str(a)], tenant="acme", workspace="eng", project="myapp")
    args = build_parser().parse_args(["paths", "remove", str(a)])
    with pytest.raises(SystemExit) as exc:
        cmd_paths_remove(args)
    assert "cannot remove the last" in str(exc.value)


def test_parser_init_accepts_path():
    parser = build_parser()
    args = parser.parse_args(
        ["init", "--tenant", "acme", "--workspace", "eng", "--path", "/tmp"]
    )
    assert args.path == ["/tmp"]


def test_parser_sync_path_optional_override():
    parser = build_parser()
    args = parser.parse_args(["sync"])
    assert args.path is None
    args2 = parser.parse_args(["sync", "--path", "/tmp", "--path", "/opt"])
    assert args2.path == ["/tmp", "/opt"]


def test_software_paths_for_project_ignores_cli_identity(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("astloom_cli.software_paths.repo_root", lambda: tmp_path)
    monkeypatch.setattr("astloom_cli.util.repo_root", lambda: tmp_path)
    monkeypatch.setattr("astloom_cli.identity.Path.home", lambda: tmp_path)
    app = tmp_path / "client-app"
    app.mkdir()
    persist_software_paths(
        [str(app)],
        tenant="mir",
        workspace="dev",
        project="ThinkingSOC",
    )
    assert software_paths_for_project("mir", "dev", "ThinkingSOC") == [str(app.resolve())]
    assert software_paths_for_project("other", "dev", "ThinkingSOC") == []

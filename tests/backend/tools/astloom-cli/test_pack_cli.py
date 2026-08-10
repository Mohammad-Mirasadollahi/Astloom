"""CLI tests for `astloom pack review`."""

from __future__ import annotations

import json
from argparse import Namespace

from astloom_cli.commands.pack_cmd import cmd_pack_review
from astloom_cli.parser import build_parser


def test_parser_pack_review():
    parser = build_parser()
    args = parser.parse_args(
        ["pack", "review", "--files", "a.py,b.py", "--token-budget", "1000", "--json"]
    )
    assert args.command == "pack"
    assert args.pack_command == "review"
    assert args.files == "a.py,b.py"
    assert args.token_budget == 1000


def test_cmd_pack_review_denies_remote_root(capsys):
    code = cmd_pack_review(
        Namespace(
            root="https://example.com/repo.git",
            files="a.py",
            from_git=False,
            staged=False,
            stdin=False,
            include_diff=False,
            token_budget=None,
            hotspot_min_tokens=50,
            max_file_bytes=200_000,
            allow_secrets=False,
            out=None,
            json=True,
        )
    )
    assert code == 2
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is False
    assert report["error"] == "remote_root_denied"


def test_cmd_pack_review_ok(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("ASTLOOM_ROOT", str(tmp_path))
    (tmp_path / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    code = cmd_pack_review(
        Namespace(
            root=str(tmp_path),
            files="a.py",
            from_git=False,
            staged=False,
            stdin=False,
            include_diff=False,
            token_budget=None,
            hotspot_min_tokens=50,
            max_file_bytes=200_000,
            allow_secrets=False,
            out=None,
            json=True,
        )
    )
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is True
    assert report["estimated_tokens"] > 0

"""CLI tests for `astloom context measure|stats`."""

from __future__ import annotations

import json
from argparse import Namespace

from astloom_cli.commands.context_cmd import cmd_context_measure, cmd_context_stats
from astloom_cli.parser import build_parser
from context_compression import reset_metrics


def test_parser_context_measure_and_stats():
    parser = build_parser()
    m = parser.parse_args(["context", "measure", "--file", "x.json", "--json"])
    assert m.command == "context"
    assert m.context_command == "measure"
    assert m.file == "x.json"
    assert m.json is True
    s = parser.parse_args(["context", "stats", "--json"])
    assert s.context_command == "stats"


def test_cmd_context_measure_reports_savings(capsys, tmp_path, monkeypatch):
    reset_metrics()
    monkeypatch.setenv("ASTLOOM_ROOT", str(tmp_path))
    # Avoid inheriting the developer machine data-root (would accumulate totals).
    monkeypatch.delenv("ASTLOOM_DATA_ROOT", raising=False)
    path = tmp_path / "blob.json"
    path.write_text(
        json.dumps({"rows": [{"n": i, "s": "y" * 200} for i in range(40)]}),
        encoding="utf-8",
    )
    code = cmd_context_measure(
        Namespace(
            file=str(path),
            payload=None,
            content_type="json",
            min_chars=100,
            json=True,
        )
    )
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is True
    assert report["chars_saved"] > 0
    assert report["pct_saved"] > 0
    assert report["totals"]["calls"] == 1

    code = cmd_context_stats(Namespace(json=True))
    assert code == 0
    stats = json.loads(capsys.readouterr().out)
    assert stats["cli_totals"]["calls"] == 1
    assert stats["cli_totals"]["chars_saved"] > 0

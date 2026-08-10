"""CLI tests for ``astloom sync jobs``."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from astloom_cli.parser import build_parser
from astloom_cli.parser._core import peel_sync_words


def test_peel_sync_jobs_list_and_detail():
    def error(msg):
        raise AssertionError(msg)

    out, mf, mode, jid = peel_sync_words(["sync", "jobs"], error)
    assert out == ["sync"]
    assert mode == "jobs"
    assert jid is None
    assert mf is None

    out2, _, mode2, jid2 = peel_sync_words(
        ["sync", "jobs", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "--json"],
        error,
    )
    assert mode2 == "jobs"
    assert jid2 == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert "--json" in out2


def test_parser_sync_jobs_sets_mode():
    parser = build_parser()
    args = parser.parse_args(["sync", "jobs", "--json"])
    assert args.command == "sync"
    assert args.sync_mode == "jobs"
    assert args.json is True


def test_cmd_sync_jobs_lists_empty(monkeypatch, tmp_path: Path, capsys):
    from astloom_cli.commands.sync import jobs as jobs_mod

    monkeypatch.setattr(jobs_mod, "_require_server_role", lambda: None)
    monkeypatch.setattr(jobs_mod, "_data_root_for_jobs", lambda: tmp_path)
    code = jobs_mod.cmd_sync_jobs(Namespace(sync_job_id="", json=False))
    assert code == 0
    assert "No live client sync jobs." in capsys.readouterr().out


def test_cmd_sync_jobs_lists_and_details(monkeypatch, tmp_path: Path, capsys):
    from code_graph_service.api.client_sync_job_snapshots import write_job_snapshot
    from astloom_cli.commands.sync import jobs as jobs_mod

    jid = "11111111-2222-3333-4444-555555555555"
    write_job_snapshot(
        jid,
        {
            "phase": "ingest",
            "status": "ok",
            "done": 17,
            "total": 814,
            "file_workers": 28,
            "files_in_flight": 3,
            "files_in_flight_paths": ["a.py", "b.py"],
            "file": "a.py",
            "symbols_indexed": 10,
            "edges_written": 20,
        },
        data_root=tmp_path,
        tenant_id="mir",
        workspace_id="dev",
        project_id="ThinkingSOC",
    )
    monkeypatch.setattr(jobs_mod, "_require_server_role", lambda: None)
    monkeypatch.setattr(jobs_mod, "_data_root_for_jobs", lambda: tmp_path)
    monkeypatch.setattr(jobs_mod, "_graph_pid", lambda _r: None)

    assert jobs_mod.cmd_sync_jobs(Namespace(sync_job_id="", json=False)) == 0
    listed = capsys.readouterr().out
    assert jid in listed
    assert "mir/dev/ThinkingSOC" in listed
    assert "17/814" in listed

    assert jobs_mod.cmd_sync_jobs(Namespace(sync_job_id=jid, json=False)) == 0
    detail = capsys.readouterr().out
    assert "3 active / 28 workers" in detail
    assert "a.py" in detail


def test_cmd_sync_jobs_rejects_client_role(monkeypatch):
    from astloom_cli.commands.sync import jobs as jobs_mod

    monkeypatch.setattr(
        "astloom_cli.commands.sync.jobs.install_role",
        lambda _r: "client",
    )
    with pytest.raises(SystemExit, match="server-only"):
        jobs_mod.cmd_sync_jobs(Namespace(sync_job_id="", json=False))

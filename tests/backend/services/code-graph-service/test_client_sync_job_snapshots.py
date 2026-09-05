"""Unit tests for client sync job disk snapshots."""

from __future__ import annotations

import json
import time
from pathlib import Path

from code_graph_service.api.client_sync_job_snapshots import (
    clear_job_snapshot,
    list_live_job_snapshots,
    read_job_snapshot,
    write_job_snapshot,
)


def test_write_list_read_clear_job_snapshot(tmp_path: Path):
    data_root = tmp_path / "data"
    jid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    path = write_job_snapshot(
        jid,
        {"phase": "ingest", "done": 3, "total": 10, "file_workers": 8, "files_in_flight": 2},
        data_root=data_root,
        tenant_id="mir",
        workspace_id="dev",
        project_id="demo-app",
    )
    assert path is not None
    assert path.is_file()
    live = list_live_job_snapshots(data_root=data_root)
    assert len(live) == 1
    assert live[0]["job_id"] == jid
    assert live[0]["done"] == 3
    assert live[0]["tenant_id"] == "mir"
    got = read_job_snapshot(jid, data_root=data_root)
    assert got is not None
    assert got["file_workers"] == 8
    clear_job_snapshot(jid, data_root=data_root)
    assert list_live_job_snapshots(data_root=data_root) == []


def test_list_skips_stale_and_inactive(tmp_path: Path):
    data_root = tmp_path / "data"
    write_job_snapshot(
        "job-fresh",
        {"done": 1, "total": 2},
        data_root=data_root,
        tenant_id="t",
        workspace_id="w",
        project_id="p",
    )
    write_job_snapshot(
        "job-dead",
        {"done": 1, "total": 2, "active": False},
        data_root=data_root,
        tenant_id="t",
        workspace_id="w",
        project_id="p",
    )
    stale_path = write_job_snapshot(
        "job-stale",
        {"done": 1, "total": 2},
        data_root=data_root,
        tenant_id="t",
        workspace_id="w",
        project_id="p",
    )
    assert stale_path is not None
    raw = json.loads(stale_path.read_text(encoding="utf-8"))
    raw["updated_at"] = time.time() - 120
    stale_path.write_text(json.dumps(raw), encoding="utf-8")
    live = list_live_job_snapshots(data_root=data_root, max_age_sec=60)
    ids = {j["job_id"] for j in live}
    assert ids == {"job-fresh"}


def test_write_rejects_path_traversal_job_id(tmp_path: Path):
    assert write_job_snapshot("../evil", {"done": 1}, data_root=tmp_path) is None


def test_late_progress_write_after_clear_does_not_recreate(tmp_path: Path):
    """Stuck workers must not resurrect a snapshot after cancel/clear (race)."""
    data_root = tmp_path / "data"
    jid = "bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert (
        write_job_snapshot(
            jid,
            {"phase": "ingest", "done": 96, "total": 815, "status": "ok", "active": True},
            data_root=data_root,
            project_id="demo-app",
        )
        is not None
    )
    clear_job_snapshot(jid, data_root=data_root)
    path = data_root / "run" / "client-sync-jobs" / f"{jid}.json"
    assert not path.is_file()
    # Late progress event from an abandoned worker (same as post-cancel race).
    assert (
        write_job_snapshot(
            jid,
            {"phase": "ingest", "done": 97, "total": 815, "status": "ok", "active": True},
            data_root=data_root,
            project_id="demo-app",
        )
        is None
    )
    assert not path.is_file()
    assert list_live_job_snapshots(data_root=data_root) == []


def test_registered_write_reopens_closed_job_id(tmp_path: Path):
    data_root = tmp_path / "data"
    jid = "cccccccc-bbbb-cccc-dddd-eeeeeeeeeeee"
    write_job_snapshot(jid, {"done": 1, "total": 2}, data_root=data_root)
    clear_job_snapshot(jid, data_root=data_root)
    path = write_job_snapshot(
        jid,
        {"phase": "ingest", "status": "registered", "done": 0, "total": 0, "active": True},
        data_root=data_root,
    )
    assert path is not None
    assert path.is_file()

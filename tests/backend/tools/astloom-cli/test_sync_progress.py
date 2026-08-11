"""Tests for sync progress tracker and ETA formatting."""

from __future__ import annotations

import json
import os
import stat
import time
from pathlib import Path

from astloom_cli.sync_progress import (
    SyncProgressTracker,
    format_bar,
    format_duration,
    read_live_progress,
)


def test_format_duration_and_bar():
    assert format_duration(5) == "5s"
    assert format_duration(65) == "1m 5s"
    assert format_bar(50, width=10) == "[#####-----]"


def test_progress_log_has_blank_lines_and_timestamp(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr("astloom_cli.ui._use_color", lambda: False)
    monkeypatch.setattr(
        "astloom_cli.sync_progress.tracker.wall_clock_now",
        lambda: "2026-07-22 12:00:00",
    )
    tracker = SyncProgressTracker(
        scope="t/w/p",
        path=str(tmp_path),
        interval_sec=30.0,
        progress_file=tmp_path / "sync-progress.json",
    )
    tracker(
        {
            "phase": "ingest",
            "done": 0,
            "total": 10,
            "status": "started",
            "files_in_flight": 1,
        }
    )
    out = capsys.readouterr().out
    assert "at 2026-07-22 12:00:00" in out
    assert "elapsed" in out
    # Blank line before and after each progress block
    assert out.startswith("\n")
    assert out.rstrip("\n").count("\n\n") >= 1 or out.endswith("\n\n")
    data = json.loads((tmp_path / "sync-progress.json").read_text(encoding="utf-8"))
    assert data["logged_at"] == "2026-07-22 12:00:00"
    tracker.finish()


def test_preparing_status_prints_before_queue_known(tmp_path: Path, monkeypatch, capsys):
    """Regression: Neo4j warmup had no console line, so sync looked hung after the banner."""
    monkeypatch.setattr("astloom_cli.ui._use_color", lambda: False)
    tracker = SyncProgressTracker(
        scope="t/w/p",
        path=str(tmp_path),
        interval_sec=30.0,
        progress_file=tmp_path / "sync-progress.json",
    )
    tracker(
        {
            "phase": "ingest",
            "done": 0,
            "total": 0,
            "status": "preparing",
            "file": "loading graph symbols",
        }
    )
    out = capsys.readouterr().out
    assert "preparing" in out.lower() or "loading graph" in out.lower()
    assert "0/0" not in out  # no fake percent theater
    data = json.loads((tmp_path / "sync-progress.json").read_text(encoding="utf-8"))
    assert data["status"] == "preparing"
    assert data["active"] is True
    tracker.finish()


def test_progress_explains_this_run_vs_prior(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr("astloom_cli.ui._use_color", lambda: False)
    tracker = SyncProgressTracker(
        scope="t/w/p",
        path=str(tmp_path),
        interval_sec=30.0,
        progress_file=tmp_path / "sync-progress.json",
    )
    tracker(
        {
            "phase": "ingest",
            "done": 0,
            "total": 237,
            "status": "started",
            "prior_indexed": 40,
            "queue_new": 200,
            "queue_changed": 37,
            "queue_unchanged": 0,
            "files_in_flight": 30,
            "file_workers": 30,
        }
    )
    out = capsys.readouterr().out
    assert "code 0/237" in out
    assert "new=200" in out
    assert "changed=37" in out
    assert "prior file symbols" not in out
    assert "lang_backfill=" not in out
    assert "need-work files finished yet" not in out
    assert "half-credit for 30 in-flight" in out
    assert "done=0 finished" in out
    tracker.finish()


def test_progress_percent_half_credits_in_flight(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr("astloom_cli.ui._use_color", lambda: False)
    progress_file = tmp_path / "sync-progress.json"
    tracker = SyncProgressTracker(
        scope="t/w/p",
        path=str(tmp_path),
        interval_sec=0.0,
        progress_file=progress_file,
    )
    tracker(
        {
            "phase": "ingest",
            "done": 0,
            "total": 10,
            "status": "started",
            "files_in_flight": 10,
            "file_workers": 10,
            "queue_new": 10,
        }
    )
    data = json.loads(progress_file.read_text(encoding="utf-8"))
    # 0 finished + 0.5 * 10 in-flight → 50%
    assert data["done"] == 0
    assert data["percent"] == 50.0
    out = capsys.readouterr().out
    assert "50.0%" in out
    tracker.finish()


def test_progress_shows_docs_phase_label(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr("astloom_cli.ui._use_color", lambda: False)
    tracker = SyncProgressTracker(
        scope="t/w/p",
        path=str(tmp_path),
        interval_sec=30.0,
        progress_file=tmp_path / "sync-progress.json",
    )
    tracker(
        {
            "phase": "docs",
            "done": 2,
            "total": 10,
            "status": "ok",
            "prior_indexed": 5,
            "queue_new": 8,
            "queue_changed": 2,
            "queue_unchanged": 5,
            "docs_indexed": 2,
            "links_created": 1,
            "anchors_registered": 1,
            "file": "docs/a.md",
        }
    )
    out = capsys.readouterr().out
    assert "docs 2/10" in out
    assert "prior docs" not in out
    assert "link_refresh=5" in out
    assert "unchanged_recheck=" not in out
    assert "links 1" in out
    tracker.finish()


def test_progress_code_phase_uses_lang_backfill_label(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr("astloom_cli.ui._use_color", lambda: False)
    tracker = SyncProgressTracker(
        scope="t/w/p",
        path=str(tmp_path),
        interval_sec=30.0,
        progress_file=tmp_path / "sync-progress.json",
    )
    tracker(
        {
            "phase": "ingest",
            "done": 1,
            "total": 3,
            "status": "ok",
            "prior_indexed": 10,
            "queue_new": 1,
            "queue_changed": 1,
            "queue_unchanged": 1,
        }
    )
    out = capsys.readouterr().out
    assert "lang_backfill=1" in out
    assert "new=1" in out
    assert "changed=1" in out
    assert "prior file symbols" not in out
    assert "unchanged_recheck=" not in out
    tracker.finish()


def test_progress_hides_zero_queue_fields(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr("astloom_cli.ui._use_color", lambda: False)
    tracker = SyncProgressTracker(
        scope="t/w/p",
        path=str(tmp_path),
        interval_sec=30.0,
        progress_file=tmp_path / "sync-progress.json",
    )
    tracker(
        {
            "phase": "ingest",
            "done": 2,
            "total": 4,
            "status": "ok",
            "prior_indexed": 358,
            "queue_new": 0,
            "queue_changed": 4,
            "queue_unchanged": 0,
        }
    )
    out = capsys.readouterr().out
    assert "changed=4" in out
    assert "new=" not in out
    assert "lang_backfill=" not in out
    assert "prior" not in out
    tracker.finish()


def test_begin_phase_resets_rate_samples(tmp_path: Path, monkeypatch):
    clock = {"t": 0.0}
    monkeypatch.setattr("astloom_cli.sync_progress.tracker.time.monotonic", lambda: clock["t"])
    tracker = SyncProgressTracker(
        scope="t/w/p",
        path=str(tmp_path),
        interval_sec=30.0,
        progress_file=tmp_path / "sync-progress.json",
    )
    tracker({"phase": "ingest", "done": 5, "total": 10, "status": "ok"})
    clock["t"] = 10.0
    tracker({"phase": "ingest", "done": 10, "total": 10, "status": "finished"})
    tracker.begin_phase()
    clock["t"] = 10.0
    tracker({"phase": "docs", "done": 0, "total": 4, "status": "started"})
    data = json.loads((tmp_path / "sync-progress.json").read_text(encoding="utf-8"))
    assert data["phase"] == "docs"
    assert data["done"] == 0
    assert data["total"] == 4
    assert data["files_per_sec"] is None
    tracker.finish()


def test_tracker_writes_progress_and_adapts(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr("astloom_cli.ui._use_color", lambda: False)
    progress_file = tmp_path / "sync-progress.json"
    tracker = SyncProgressTracker(
        scope="mir/dev/app",
        path=str(tmp_path),
        interval_sec=0.01,
        progress_file=progress_file,
    )
    total = 10
    for i in range(total + 1):
        tracker(
            {
                "phase": "ingest",
                "done": i,
                "total": total,
                "file": f"f{i}.py",
                "status": "started" if i == 0 else ("finished" if i == total else "ok"),
                "symbols_indexed": i * 2,
                "edges_written": i,
                "chars_read": i * 40,
                "approx_tokens": i * 10,
            }
        )
        time.sleep(0.02)
        if i == 5:
            assert progress_file.is_file()
            data = json.loads(progress_file.read_text(encoding="utf-8"))
            assert data["done"] == 5
            assert data["total"] == 10
            # Optional concurrency/RPM fields round-trip when present
            tracker(
                {
                    "phase": "ingest",
                    "done": 5,
                    "total": total,
                    "file": "f5.py",
                    "status": "ok",
                    "files_in_flight": 2,
                    "files_in_flight_paths": ["a.py", "b.py"],
                    "file_workers": 4,
                    "rpm": 30,
                    "rpm_inflight_cap": 30,
                    "rpm_inflight": 3,
                    "rpm_starts_in_window": 5,
                    "symbols_indexed": 10,
                    "edges_written": 5,
                    "chars_read": 200,
                    "approx_tokens": 50,
                }
            )
            data2 = json.loads(progress_file.read_text(encoding="utf-8"))
            assert data2["files_in_flight"] == 2
            assert data2["rpm_inflight"] == 3
            assert data2["file_workers"] == 4
    tracker.finish()
    assert not progress_file.is_file()
    out = capsys.readouterr().out
    assert "%" in out
    assert "code" in out


def test_read_live_progress_fresh(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("astloom_cli.sync_progress.store.repo_root", lambda: tmp_path)
    path = tmp_path / ".astloom" / "sync-progress.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "active": True,
                "percent": 40,
                "done": 4,
                "total": 10,
                "elapsed_sec": 20,
                "eta_sec": 30,
                "pid": __import__("os").getpid(),
                "updated_at": time.time(),
            }
        ),
        encoding="utf-8",
    )
    data = read_live_progress(root=tmp_path)
    assert data is not None
    assert data["percent"] == 40


def test_tracker_publishes_full_session_snapshot(tmp_path: Path):
    progress_file = tmp_path / "sync-progress.json"
    tracker = SyncProgressTracker(
        scope="t/w/p",
        path=str(tmp_path),
        interval_sec=10.0,
        progress_file=progress_file,
    )
    tracker({"phase": "ingest", "done": 0, "total": 2, "status": "started"})
    sessions = {
        "rpm": 4,
        "inflight_cap": 4,
        "starts_in_window": 2,
        "inflight_count": 2,
        "inflight": [{"session_id": "a"}, {"session_id": "b"}],
        "history": [],
    }

    tracker.update_sessions(sessions)
    tracker({"phase": "ingest", "done": 1, "total": 2, "status": "ok"})

    data = json.loads(progress_file.read_text(encoding="utf-8"))
    assert data["llm_sessions"] == sessions
    assert data["rpm_inflight"] == 2
    tracker.finish()


def test_tracker_skips_unchanged_session_snapshot(tmp_path: Path, monkeypatch):
    tracker = SyncProgressTracker(
        scope="t/w/p",
        path=str(tmp_path),
        interval_sec=10.0,
        progress_file=tmp_path / "sync-progress.json",
    )
    tracker({"phase": "ingest", "done": 0, "total": 1, "status": "started"})
    sessions = {
        "rpm": 4,
        "inflight_cap": 4,
        "starts_in_window": 1,
        "inflight_count": 1,
        "inflight": [{"session_id": "a"}],
        "history": [],
    }
    writes = 0
    original_write = tracker._write

    def counted_write(snapshot):
        nonlocal writes
        writes += 1
        original_write(snapshot)

    monkeypatch.setattr(tracker, "_write", counted_write)

    tracker.update_sessions(sessions)
    tracker.update_sessions(dict(sessions))

    assert writes == 1
    tracker.finish()


def test_early_provisional_rate_within_ten_seconds(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr("astloom_cli.ui._use_color", lambda: False)
    clock = {"t": 0.0}
    monkeypatch.setattr("astloom_cli.sync_progress.tracker.time.monotonic", lambda: clock["t"])

    tracker = SyncProgressTracker(
        scope="t/w/p",
        path=str(tmp_path),
        interval_sec=10.0,
        progress_file=tmp_path / "sync-progress.json",
    )
    # t=0: started, done=0 — no rate yet
    tracker(
        {
            "phase": "ingest",
            "done": 0,
            "total": 10,
            "status": "started",
            "files_in_flight": 2,
        }
    )
    data0 = json.loads((tmp_path / "sync-progress.json").read_text(encoding="utf-8"))
    assert data0["files_per_sec"] is None
    assert data0["eta_sec"] is None

    # t=6 (>= EARLY_RATE_AFTER_SEC): provisional rate from in-flight / elapsed
    clock["t"] = 6.0
    tracker(
        {
            "phase": "ingest",
            "done": 0,
            "total": 10,
            "status": "active",
            "files_in_flight": 2,
            "file": "slow.py",
        }
    )
    data = json.loads((tmp_path / "sync-progress.json").read_text(encoding="utf-8"))
    assert data["files_per_sec"] is not None
    assert data["files_per_sec"] > 0
    assert data["eta_sec"] is not None
    assert data["eta_sec"] > 0
    # 2 in-flight / 6s elapsed ⇒ ~0.333/s; ETA for 10 remaining ≈ 30s
    assert abs(data["files_per_sec"] - (2 / 6)) < 0.05
    assert data.get("rate_basis") == "provisional"
    out = capsys.readouterr().out
    progress_lines = [ln for ln in out.splitlines() if "ETA" in ln and "code" in ln]
    assert progress_lines
    assert "rate …" not in progress_lines[-1]
    assert "provisional" in progress_lines[-1]
    tracker.finish()


def test_eta_blend_uses_lifetime_and_recent(tmp_path: Path, monkeypatch):
    """Lifetime avg dominates; a short stall does not collapse ETA to near-zero rate."""
    clock = {"t": 0.0}
    monkeypatch.setattr("astloom_cli.sync_progress.tracker.time.monotonic", lambda: clock["t"])
    tracker = SyncProgressTracker(
        scope="t/w/p",
        path=str(tmp_path),
        interval_sec=30.0,
        progress_file=tmp_path / "sync-progress.json",
    )
    tracker({"phase": "ingest", "done": 0, "total": 100, "status": "started"})

    # Steady completions: 30 files in 30s → 1.0/s lifetime
    for i in range(1, 31):
        clock["t"] = float(i)
        tracker({"phase": "ingest", "done": i, "total": 100, "status": "ok"})

    data_fast = json.loads((tmp_path / "sync-progress.json").read_text(encoding="utf-8"))
    assert data_fast["rate_basis"] in {"avg", "avg+recent"}
    rate_fast = float(data_fast["files_per_sec"])
    assert 0.7 < rate_fast < 1.2

    # 30s stall with only +1 file → recent dips, but lifetime (~31/60) keeps ETA sane
    clock["t"] = 60.0
    tracker({"phase": "ingest", "done": 31, "total": 100, "status": "ok"})
    data = json.loads((tmp_path / "sync-progress.json").read_text(encoding="utf-8"))
    assert data["rate_basis"] == "avg+recent"
    rate = float(data["files_per_sec"])
    # Pure recent over ~30s of stall would be ~0.03/s; blended must stay far above that.
    assert rate > 0.25
    assert data["eta_sec"] is not None
    assert float(data["eta_sec"]) < 69 / 0.25  # remaining 69 at >0.25/s
    tracker.finish()


def test_finished_status_not_reprinted_on_interval(tmp_path: Path, monkeypatch, capsys):
    """Regression: after code 100%, session monitor kept reprinting the same block
    while embedding_refresh still ran — looked hung for tens of minutes."""
    clock = {"t": 0.0}

    def mono():
        return clock["t"]

    monkeypatch.setattr("astloom_cli.sync_progress.tracker.time.monotonic", mono)
    monkeypatch.setattr("astloom_cli.ui._use_color", lambda: False)
    tracker = SyncProgressTracker(
        scope="t/w/p",
        path=str(tmp_path),
        interval_sec=10.0,
        progress_file=tmp_path / "sync-progress.json",
    )
    tracker(
        {
            "phase": "ingest",
            "done": 17,
            "total": 17,
            "status": "finished",
            "queue_new": 14,
            "queue_changed": 3,
            "file_workers": 17,
        }
    )
    first = capsys.readouterr().out
    assert "100.0%" in first
    clock["t"] = 30.0
    tracker.update_sessions(
        {
            "rpm": 30,
            "inflight_cap": 30,
            "starts_in_window": 0,
            "inflight_count": 0,
            "inflight": [],
            "history": [],
        }
    )
    second = capsys.readouterr().out
    assert second == ""
    tracker.finish()


def test_embeddings_phase_resets_percent_and_label(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr("astloom_cli.ui._use_color", lambda: False)
    tracker = SyncProgressTracker(
        scope="t/w/p",
        path=str(tmp_path),
        interval_sec=30.0,
        progress_file=tmp_path / "sync-progress.json",
    )
    tracker(
        {
            "phase": "ingest",
            "done": 17,
            "total": 17,
            "status": "finalizing",
        }
    )
    capsys.readouterr()
    tracker(
        {
            "phase": "embeddings",
            "done": 128,
            "total": 1000,
            "status": "running",
            "embeddings_refreshed": 128,
            "file": "BAAI/bge-large-en-v1.5",
            "file_workers": 4,
            "files_in_flight": 4,
        }
    )
    out = capsys.readouterr().out
    assert "embeddings" in out
    assert "128/1000" in out
    assert "embedding_refresh" in out
    tracker.finish()


def test_session_heartbeat_refreshes_eta_when_unchanged(tmp_path: Path, monkeypatch):
    clock = {"t": 0.0}

    def mono():
        return clock["t"]

    monkeypatch.setattr("astloom_cli.sync_progress.tracker.time.monotonic", mono)
    tracker = SyncProgressTracker(
        scope="t/w/p",
        path=str(tmp_path),
        interval_sec=10.0,
        progress_file=tmp_path / "sync-progress.json",
    )
    sessions = {
        "rpm": 4,
        "inflight_cap": 4,
        "starts_in_window": 1,
        "inflight_count": 1,
        "inflight": [{"session_id": "a"}],
        "history": [],
    }
    tracker(
        {
            "phase": "ingest",
            "done": 0,
            "total": 10,
            "status": "started",
            "files_in_flight": 1,
            "llm_sessions": sessions,
        }
    )
    clock["t"] = 5.0
    tracker.update_sessions(dict(sessions))  # early rate kick
    data = json.loads((tmp_path / "sync-progress.json").read_text(encoding="utf-8"))
    assert data["eta_sec"] is not None
    eta1 = data["eta_sec"]

    clock["t"] = 15.0
    tracker.update_sessions(dict(sessions))  # interval heartbeat
    data2 = json.loads((tmp_path / "sync-progress.json").read_text(encoding="utf-8"))
    assert data2["elapsed_sec"] >= 15.0
    # Longer wait with no completions ⇒ slower implied rate ⇒ ETA grows
    assert data2["eta_sec"] >= eta1
    tracker.finish()


def test_tracker_snapshot_is_private_before_json_is_written(tmp_path: Path, monkeypatch):
    progress_file = tmp_path / "sync-progress.json"
    temp_file = progress_file.with_suffix(".tmp")
    temp_file.write_text("stale", encoding="utf-8")
    temp_file.chmod(0o644)
    modes_when_opened: list[int] = []
    real_fdopen = os.fdopen

    def checked_fdopen(fd, *args, **kwargs):
        modes_when_opened.append(stat.S_IMODE(os.fstat(fd).st_mode))
        return real_fdopen(fd, *args, **kwargs)

    monkeypatch.setattr("astloom_cli.sync_progress.store.os.fdopen", checked_fdopen)
    tracker = SyncProgressTracker(
        scope="t/w/p",
        path=str(tmp_path),
        interval_sec=10.0,
        progress_file=progress_file,
    )

    tracker({"phase": "ingest", "done": 0, "total": 1, "status": "started"})

    assert modes_when_opened == [0o600]
    assert stat.S_IMODE(progress_file.stat().st_mode) == 0o600
    assert temp_file.read_text(encoding="utf-8") == "stale"
    tracker.finish()


def test_ingest_calls_on_progress(tmp_path: Path):
    from code_graph_service.core import CodeGraphService, Scope
    from code_graph_service.testing import InMemoryStore

    root = tmp_path / "src"
    root.mkdir()
    (root / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (root / "b.py").write_text("def b():\n    return 2\n", encoding="utf-8")
    events: list[dict] = []
    svc = CodeGraphService(InMemoryStore())
    scope = Scope("t", "w", "p")
    svc.ingest_repo(
        scope,
        "cli",
        "c1",
        "k1",
        {
            "root_path": str(root),
            "max_files": 10,
            "include_outcomes": False,
            "on_progress": events.append,
        },
    )
    assert events
    assert events[0]["status"] == "discovering"
    assert any(e.get("status") == "started" for e in events)
    assert events[-1]["status"] == "finished"
    # Terminal event is embedding_refresh (may be 0/0 when no embedding index).
    assert events[-1].get("phase") in {"embeddings", "ingest"}
    assert any(e.get("total", 0) >= 2 for e in events)


def test_session_updates_do_not_reprint_while_status_started(
    tmp_path: Path, monkeypatch, capsys
):
    """Regression: status=started must not force-print on every RPM poll."""
    monkeypatch.setattr("astloom_cli.ui._use_color", lambda: False)
    tracker = SyncProgressTracker(
        scope="t/w/p",
        path=str(tmp_path),
        interval_sec=30.0,
        progress_file=tmp_path / "sync-progress.json",
    )
    tracker(
        {
            "phase": "ingest",
            "done": 0,
            "total": 10,
            "status": "started",
            "files_in_flight": 1,
            "file_workers": 1,
        }
    )
    capsys.readouterr()
    sessions_a = {
        "rpm": 30,
        "inflight_cap": 30,
        "starts_in_window": 0,
        "inflight_count": 0,
        "inflight": [],
        "history": [],
    }
    sessions_b = {**sessions_a, "starts_in_window": 1}
    tracker.update_sessions(sessions_a)
    tracker.update_sessions(sessions_b)
    tracker.update_sessions({**sessions_b, "inflight_count": 1})
    out = capsys.readouterr().out
    assert "code 0/10" not in out
    tracker({"phase": "ingest", "done": 10, "total": 10, "status": "finished"})
    out_fin = capsys.readouterr().out
    assert "code 10/10" in out_fin
    tracker.finish()


def test_empty_queue_skips_console_progress_theater(
    tmp_path: Path, monkeypatch, capsys
):
    """Noop / 0 files to visit: write snapshot, do not spam 0/0 progress blocks."""
    monkeypatch.setattr("astloom_cli.ui._use_color", lambda: False)
    progress_file = tmp_path / "sync-progress.json"
    tracker = SyncProgressTracker(
        scope="t/w/p",
        path=str(tmp_path),
        interval_sec=1.0,
        progress_file=progress_file,
    )
    tracker({"phase": "ingest", "done": 0, "total": 0, "status": "started"})
    tracker.update_sessions(
        {
            "rpm": 30,
            "inflight_cap": 30,
            "starts_in_window": 0,
            "inflight_count": 0,
            "inflight": [],
            "history": [],
        }
    )
    tracker({"phase": "ingest", "done": 0, "total": 0, "status": "finished"})
    out = capsys.readouterr().out
    assert "0/0" not in out
    assert "0.0%" not in out
    data = json.loads(progress_file.read_text(encoding="utf-8"))
    assert data["total"] == 0
    assert data["status"] == "finished"
    tracker.finish()

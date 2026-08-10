"""Tests for sync usage folder reports + FIFO."""

from __future__ import annotations

from pathlib import Path

from astloom_cli.sync_usage_log import (
    append_sync_usage_record,
    build_sync_usage_record,
    execution_at_filename,
    task_entry,
    usage_log_dir,
    usage_log_dir_max_bytes,
)


def test_execution_at_filename():
    assert execution_at_filename("2026-07-21 18:57:03") == "2026-07-21_18-57-03.json"


def test_usage_log_dir_and_max_from_env(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("astloom_cli.sync_usage_log.repo_root", lambda: tmp_path)
    env = {
        "ASTLOOM_SYNC_USAGE_LOG_DIR": "logs/sync-usage",
        "ASTLOOM_SYNC_USAGE_LOG_DIR_MAX_BYTES": str(5 * 1024 * 1024),
    }
    assert usage_log_dir(env) == (tmp_path / "logs" / "sync-usage").resolve()
    assert usage_log_dir_max_bytes(env) == 5 * 1024 * 1024


def test_append_writes_named_file_and_fifo_folder(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("astloom_cli.sync_usage_log.repo_root", lambda: tmp_path)
    folder = tmp_path / "sync-usage"
    monkeypatch.setattr(
        "astloom_cli.sync_usage_log.usage_log_dir",
        lambda _env=None: folder,
    )
    monkeypatch.setattr(
        "astloom_cli.sync_usage_log.usage_log_dir_max_bytes",
        lambda _env=None: 2500,
    )
    for i in range(12):
        # Distinct seconds via synthetic execution_at
        execution_at = f"2026-07-21 18:00:{i:02d}"
        record = build_sync_usage_record(
            scope="acme/eng/p",
            report={"ok": True, "n": i, "pad": "x" * 200},
            tasks=[task_entry(name=f"t{i}", duration_sec=0.1, tokens_in=10, tokens_out=2)],
            duration_sec=0.1,
            tokens_in=10,
            tokens_out=2,
            execution_at=execution_at,
        )
        path = append_sync_usage_record(record)
        assert path.name.startswith("2026-07-21_18-00-")
        assert '"execution_at"' in path.read_text(encoding="utf-8")
    total = sum(p.stat().st_size for p in folder.glob("*.json"))
    assert total <= 2500
    names = sorted(p.name for p in folder.glob("*.json"))
    assert names
    # Oldest seconds should be gone
    assert "2026-07-21_18-00-00.json" not in names
    assert any(n.startswith("2026-07-21_18-00-") for n in names)

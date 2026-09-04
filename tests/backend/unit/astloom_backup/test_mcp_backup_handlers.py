"""Unit tests for MCP backup status/dry-run handlers."""

from __future__ import annotations

import json
from pathlib import Path

from astloom_backup.bundle import pack_directory
from astloom_backup.manifest import build_manifest, write_checksums
from astloom_backup.scope import Scope
from mcp_gateway_service.backends import backup as backup_backend
from astloom_backup.job_state import write_job


def test_backup_status_and_dry_run(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTLOOM_ROOT", str(tmp_path))
    staging = tmp_path / "stg"
    staging.mkdir()
    manifest = build_manifest(
        scope=Scope("t", "w", "p"),
        contract_version="1",
        product_version="0.1.2",
        store_counts={"memory": 0},
        created_at="2026-08-01T00:00:00Z",
    )
    (staging / "manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    write_checksums(staging)
    asbak = tmp_path / "x.asbak"
    pack_directory(staging, asbak)

    base = {"maps_to": "backup.status"}
    status = backup_backend.backup_status(base=base)
    assert status["ok"] is True

    report = backup_backend.backup_dry_run(
        {"bundle_path": str(asbak), "replace": False},
        base={"maps_to": "backup.dry_run"},
    )
    assert report["ok"] is True
    assert report["action"] == "dry_run"
    assert report["would_fail_conflict"] is False


def test_backup_status_omits_foreign_scope_job(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTLOOM_ROOT", str(tmp_path))
    write_job(
        tmp_path,
        {
            "ok": True,
            "action": "export",
            "scope": {"tenant_id": "t", "workspace_id": "w", "project_id": "p"},
        },
    )
    status = backup_backend.backup_status(
        base={"maps_to": "backup.status"},
        scope={"tenant_id": "mir", "workspace_id": "dev", "project_id": "ThinkingSOC"},
    )
    assert status["ok"] is True
    assert status["job"] is None
    assert "different MCP project" in status["job_omitted"]

    matched = backup_backend.backup_status(
        base={"maps_to": "backup.status"},
        scope={"tenant_id": "t", "workspace_id": "w", "project_id": "p"},
    )
    assert matched["job"]["scope"]["project_id"] == "p"

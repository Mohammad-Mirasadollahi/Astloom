"""CLI wiring for astloom backup."""

from __future__ import annotations

import json
import os
from pathlib import Path

from astloom_cli.main import main
from astloom_backup.bundle import pack_directory
from astloom_backup.manifest import build_manifest, write_checksums
from astloom_backup.scope import Scope


def test_backup_export_loads_compose_database_url(tmp_path: Path, monkeypatch, capsys):
    """Regression: clean shell after reboot has no ASTLOOM_DATABASE_URL in process env."""
    monkeypatch.setenv("ASTLOOM_DATABASE_URL", "")
    monkeypatch.setenv("ASTLOOM_ROOT", str(tmp_path))
    monkeypatch.setattr("astloom_cli.util.repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        "astloom_cli.commands.backup_cmd.repo_root", lambda: tmp_path
    )

    def fake_apply(environ: dict, root: Path) -> None:  # noqa: ARG001
        environ["ASTLOOM_DATABASE_URL"] = (
            "postgresql://u:secret@127.0.0.1:32232/astloom"
        )

    monkeypatch.setattr(
        "astloom_cli.remote_client.apply_compose_env_to_os", fake_apply
    )

    captured: dict[str, str] = {}

    def fake_export(scope, output, repo_root=None):  # noqa: ARG001
        captured["url"] = os.environ.get("ASTLOOM_DATABASE_URL", "")
        return {"ok": True, "output": str(output)}

    monkeypatch.setattr(
        "astloom_cli.commands.backup_cmd.export_bundle", fake_export
    )
    assert main(["backup", "export", "--output", str(tmp_path / "out.asbak")]) == 0
    assert captured["url"] == "postgresql://u:secret@127.0.0.1:32232/astloom"
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True


def test_backup_validate_and_status(tmp_path: Path, monkeypatch, capsys):
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
    (staging / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    write_checksums(staging)
    asbak = tmp_path / "demo.asbak"
    pack_directory(staging, asbak)

    assert main(["backup", "validate", "--input", str(asbak)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["scope"]["project_id"] == "p"

    assert main(["backup", "status"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["ok"] is True


def test_backup_help():
    from astloom_cli.parser import build_parser

    parser = build_parser()
    args = parser.parse_args(["backup", "export", "--output", "x.asbak"])
    assert args.command == "backup"
    assert args.backup_command == "export"

"""Unit tests for legacy Docker volume → data-root migration."""

from __future__ import annotations

from pathlib import Path

from astloom_cli.data_root_migrate import migrate_named_volumes_to_data_root


def test_migrate_skips_when_dest_not_empty(tmp_path: Path, monkeypatch):
    data = tmp_path / "Astloom-data"
    for name in ("postgres", "neo4j"):
        d = data / name
        d.mkdir(parents=True)
        (d / "marker").write_text("keep\n", encoding="utf-8")

    calls: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        calls.append(list(cmd))

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        return R()

    monkeypatch.setattr("astloom_cli.data_root_migrate.subprocess.run", fake_run)
    assert migrate_named_volumes_to_data_root(data) == []
    assert not any(c[:2] == ["docker", "run"] for c in calls)


def test_migrate_copies_when_empty_and_volume_exists(tmp_path: Path, monkeypatch):
    data = tmp_path / "Astloom-data"
    runs: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        runs.append(list(cmd))

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        return R()

    monkeypatch.setattr("astloom_cli.data_root_migrate.subprocess.run", fake_run)
    migrated = migrate_named_volumes_to_data_root(data)
    assert set(migrated) == {"postgres", "neo4j"}
    assert any("astloom_astloom-postgres-data" in " ".join(c) and c[0:2] == ["docker", "run"] for c in runs)

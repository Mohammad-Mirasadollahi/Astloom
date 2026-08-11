"""Tests for Astloom sibling data-root resolution."""

from __future__ import annotations

from pathlib import Path

from astloom_cli.data_root import (
    DATA_SUBDIRS,
    default_data_root,
    ensure_data_root,
    read_data_root_marker,
    resolve_data_root,
    stamp_data_root,
)


def test_default_data_root_sibling_of_install():
    assert default_data_root(Path("/opt/Astloom")) == Path("/opt/Astloom-data")
    assert default_data_root(Path("/home/x/Astloom")) == Path("/home/x/Astloom-data")


def test_resolve_data_root_env_override(tmp_path: Path, monkeypatch):
    override = tmp_path / "custom-data"
    monkeypatch.setenv("ASTLOOM_DATA_ROOT", str(override))
    assert resolve_data_root(install_root=tmp_path / "Astloom") == override.resolve()


def test_resolve_data_root_default_sibling(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_DATA_ROOT", raising=False)
    install = tmp_path / "Astloom"
    install.mkdir()
    assert resolve_data_root(install_root=install) == (tmp_path / "Astloom-data").resolve()
    assert "sources" not in DATA_SUBDIRS


def test_ensure_data_root_creates_layout(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_DATA_ROOT", raising=False)
    install = tmp_path / "Astloom"
    install.mkdir()
    root = ensure_data_root(install_root=install)
    assert root == (tmp_path / "Astloom-data").resolve()
    for name in DATA_SUBDIRS:
        assert (root / name).is_dir()


def test_ensure_stamps_marker_and_migrates_legacy(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_DATA_ROOT", raising=False)
    install = tmp_path / "Astloom"
    (install / ".astloom" / "mcp-usage").mkdir(parents=True)
    (install / ".astloom" / "mcp-usage" / "events.jsonl").write_text("x\n", encoding="utf-8")
    root = ensure_data_root(install_root=install)
    marker = install / ".astloom" / "data-root"
    assert marker.is_file()
    assert marker.read_text(encoding="utf-8").strip() == str(root)
    assert (root / "mcp-usage" / "events.jsonl").is_file()
    assert read_data_root_marker(install) == root


def test_ensure_data_root_env_override_does_not_stamp_marker(tmp_path: Path, monkeypatch):
    install = tmp_path / "Astloom"
    install.mkdir()
    override = tmp_path / "ephemeral-data"
    monkeypatch.setenv("ASTLOOM_DATA_ROOT", str(override))
    root = ensure_data_root(install_root=install)
    assert root == override.resolve()
    assert not (install / ".astloom" / "data-root").exists()


def test_resolve_prefers_marker_over_sibling(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_DATA_ROOT", raising=False)
    install = tmp_path / "Astloom"
    install.mkdir()
    custom = tmp_path / "elsewhere"
    custom.mkdir()
    stamp_data_root(install, custom)
    assert resolve_data_root(install_root=install) == custom.resolve()

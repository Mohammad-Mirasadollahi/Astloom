"""Unit tests for install-root markers and connect discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from astloom_cli.install_root_marker import (
    looks_like_astloom_root,
    read_marker_file,
    stamp_install_root,
)


def _fake_root(tmp_path: Path) -> Path:
    root = tmp_path / "Astloom"
    (root / ".venv" / "bin").mkdir(parents=True)
    (root / ".venv" / "bin" / "astloom").write_text("#!/bin/sh\n", encoding="utf-8")
    (root / "backend" / "packages" / "astloom_cli").mkdir(parents=True)
    return root


def test_stamp_and_read_tree_and_home_markers(tmp_path: Path):
    root = _fake_root(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    written = stamp_install_root(root, home=home)
    assert any(p.name == "install-root" and ".astloom" in p.parts for p in written)
    tree_marker = root / ".astloom" / "install-root"
    home_marker = home / ".astloom" / "install-root"
    assert tree_marker.is_file()
    assert home_marker.is_file()
    assert read_marker_file(tree_marker) == root.resolve()
    assert read_marker_file(home_marker) == root.resolve()
    # Prefer world-readable; umask may leave group write.
    assert tree_marker.stat().st_mode & 0o444 == 0o444


def test_looks_like_astloom_root_rejects_random_dir(tmp_path: Path):
    junk = tmp_path / "junk"
    junk.mkdir()
    assert looks_like_astloom_root(junk) is False


def test_stamp_rejects_non_astloom(tmp_path: Path):
    with pytest.raises(ValueError, match="not an Astloom root"):
        stamp_install_root(tmp_path / "nope")

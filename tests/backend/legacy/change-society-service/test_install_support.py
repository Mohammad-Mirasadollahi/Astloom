"""Installer helper unit checks (no full install run)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
INSTALL_SCRIPTS = ROOT / "archives" / "hackathon" / "scripts"
sys.path.insert(0, str(INSTALL_SCRIPTS))

from install_support.systemd_runtime import render_systemd_unit
from install_support.banner import BANNER


def test_banner_non_empty() -> None:
    assert "Society" in BANNER
    assert len(BANNER.strip()) > 80


def test_render_systemd_substitutes_paths() -> None:
    repo = Path("/opt/Astloom")
    tpl = "[Service]\nWorkingDirectory=@REPO_ROOT@\nExecStart=@PYTHON@\n"
    out = render_systemd_unit(tpl, repo_root=repo, npm_path="/usr/bin/npm")
    assert "/opt/Astloom" in out
    assert str(repo / ".venv" / "bin" / "python") in out

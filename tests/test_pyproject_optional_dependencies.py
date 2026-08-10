"""Regression: PEP 621 optional extras must live under optional-dependencies."""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_project_optional_dependencies_declares_ci_extras():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = data["project"]
    # Mistakenly nesting extras under [project] breaks `pip install -e ".[dev,turbovec]"`.
    for key in ("dev", "turbovec", "sdk", "embeddings", "graph-analytics"):
        assert key not in project, f"{key!r} must not be a bare [project] key"
    optional = project["optional-dependencies"]
    assert "pytest==9.1.1" in optional["dev"]
    assert any(dep.startswith("turbovec") for dep in optional["turbovec"])

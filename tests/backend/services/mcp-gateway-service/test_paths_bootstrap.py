"""Regression: MCP gateway service path bootstrap must resolve repo root."""

from __future__ import annotations

from pathlib import Path

from mcp_gateway_service.backends import _paths


def test_ensure_service_paths_root_is_repo() -> None:
    root = _paths.ROOT
    assert (root / "pyproject.toml").is_file()
    assert (root / "backend" / "services" / "mcp-gateway-service").is_dir()
    assert _paths.SERVICES == root / "backend" / "services"
    assert _paths.PACKAGES == root / "backend" / "packages"
    # Depth sanity: this file lives six levels under repo root.
    here = Path(_paths.__file__).resolve()
    assert here.parents[6] == root

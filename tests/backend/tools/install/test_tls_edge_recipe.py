"""Presence checks for TLS edge install recipe (no live Caddy)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TLS_EDGE = ROOT / "scripts" / "install" / "tls_edge"


def test_tls_edge_recipe_files_exist_and_nonempty() -> None:
    for name in ("Caddyfile.example", "ensure_certs.sh", "README.md"):
        path = TLS_EDGE / name
        assert path.is_file(), f"missing {path}"
        assert path.stat().st_size > 0, f"empty {path}"

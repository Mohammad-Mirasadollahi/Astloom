"""Ensure in-process service packages are importable for the MCP gateway."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
SERVICES = ROOT / "backend" / "services"
PACKAGES = ROOT / "backend" / "packages"


def ensure_service_paths() -> None:
    for path in (
        PACKAGES,
        PACKAGES / "code-metadata",
        PACKAGES / "common-context",
        SERVICES / "core-data-service" / "src",
        SERVICES / "memory-service" / "src",
        SERVICES / "code-graph-service" / "src",
        SERVICES / "docs-sync-service" / "src",
        SERVICES / "common-context-service" / "src",
    ):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


ensure_service_paths()

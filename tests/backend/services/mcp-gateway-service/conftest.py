"""Ensure mcp_gateway_service imports for this test package."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[4]
for rel in (
    "backend/services/mcp-gateway-service/src",
    "backend/packages",
    "backend/services/code-graph-service/src",
    "backend/services/core-data-service/src",
    "backend/services/memory-service/src",
    "backend/services/docs-sync-service/src",
    "backend/services/common-context-service/src",
):
    path = _ROOT / rel
    if path.is_dir() and str(path) not in sys.path:
        sys.path.insert(0, str(path))

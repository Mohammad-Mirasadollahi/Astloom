"""Shared fixtures for code-graph-service tests.

Ensures `code_graph_service` is importable without exporting PYTHONPATH
(Test Explorer / bare `pytest`), and that sibling helpers like live_helpers
are importable from this directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

_TEST_DIR = Path(__file__).resolve().parent
_ROOT = Path(__file__).resolve().parents[4]
_SRC = _ROOT / "backend" / "services" / "code-graph-service" / "src"
_PACKAGES = (
    _ROOT / "backend" / "packages",
    _ROOT / "backend" / "packages" / "code-metadata",
    _ROOT / "backend" / "packages" / "common-context",
)
for _p in (_TEST_DIR, _SRC, *_PACKAGES):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

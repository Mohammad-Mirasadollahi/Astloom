"""Shared fixtures for docs-sync-service tests.

Ensures ``docs_sync_service`` is importable without exporting PYTHONPATH
(Test Explorer / bare ``pytest``).
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[4]
_SRC = _ROOT / "backend" / "services" / "docs-sync-service" / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

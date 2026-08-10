"""Import paths for common-context-service tests (shared package + service src)."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[4]
_PATHS = (
    _ROOT / "backend" / "services" / "common-context-service" / "src",
    _ROOT / "backend" / "packages",
    _ROOT / "backend" / "packages" / "common-context",
)
for _p in _PATHS:
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

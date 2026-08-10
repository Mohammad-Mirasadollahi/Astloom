from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PACKAGES = ROOT / "backend" / "packages"

# Importable package roots (hyphen dirs nest underscore packages).
_PATHS = (
    PACKAGES,
    PACKAGES / "shared-kernel",
    PACKAGES / "code-metadata",
    PACKAGES / "common-context",
)
for path in _PATHS:
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

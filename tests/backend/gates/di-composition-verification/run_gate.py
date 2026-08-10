#!/usr/bin/env python3
"""Run DI composition Phase A gate and exit non-zero on failure."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SUPPORT = ROOT / "tests" / "support"
if str(SUPPORT) not in sys.path:
    sys.path.insert(0, str(SUPPORT))

from di_composition_gate.gate import check_phase_gate  # noqa: E402


def main() -> int:
    decision = check_phase_gate()
    print(json.dumps(decision.public(), indent=2))
    return 0 if decision.status in {"pass", "waived"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

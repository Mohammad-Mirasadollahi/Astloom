#!/usr/bin/env python3
"""CLI entry for governance-catalog CheckPhaseGate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SUPPORT = ROOT / "tests" / "support"
PACKAGES = ROOT / "backend" / "packages"
sys.path.insert(0, str(SUPPORT))
sys.path.insert(0, str(PACKAGES))

from governance_catalog_gate.checks import run_all_checks  # noqa: E402
from governance_catalog_gate.gate import check_phase_gate  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Astloom governance-catalog verification gate")
    parser.add_argument("--waiver-ref", default=None, help="Optional waiver issue/decision ref")
    parser.add_argument("--json", action="store_true", help="Print machine-readable report")
    args = parser.parse_args()

    decision = check_phase_gate(waiver_ref=args.waiver_ref)
    checks = run_all_checks()
    report = {
        "gate": decision.public(),
        "checks": [item.public() for item in checks],
    }
    failed_checks = [item for item in checks if item.status != "passed"]
    gate = decision.public()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Governance-catalog gate: {gate['status']} ({gate['passed_count']} passed, {gate['failed_count']} failed)")
        print(f"Verification checks: {sum(1 for item in checks if item.status == 'passed')}/{len(checks)} passed")
        for item in decision.checks:
            if item.status == "failed":
                print(f"  FAIL {item.check_id}: {item.message}")
        for item in failed_checks:
            print(f"  FAIL {item.check_id}: {item.message}")

    if decision.status == "fail" or failed_checks:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

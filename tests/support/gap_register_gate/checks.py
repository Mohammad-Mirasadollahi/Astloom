from __future__ import annotations

import sys
from typing import Any

from .catalog import GAP_REGISTER, ROOT
from .gate import CheckResult


def _ensure_packages_path() -> None:
    packages = str(ROOT / "backend" / "packages")
    if packages not in sys.path:
        sys.path.insert(0, packages)


def verify_critical_gaps_have_owners() -> list[CheckResult]:
    _ensure_packages_path()
    from governance_catalog import load_gap_register

    catalog = load_gap_register(GAP_REGISTER)
    critical = [g for g in catalog.get("gaps", []) if g.get("severity") == "Critical"]
    missing = [g["gap_id"] for g in critical if not str(g.get("owner") or "").strip()]
    return [
        CheckResult(
            "critical-gaps-have-owners",
            "ownership",
            "critical",
            "passed" if critical and not missing else "failed",
            (
                f"critical={len(critical)} owners_ok"
                if critical and not missing
                else f"missing_owners={missing or 'no critical gaps'}"
            ),
            [g["gap_id"] for g in critical],
            "docs/10-gap-analysis/05-gap-triage-and-resolution-process.md",
        )
    ]


def verify_high_gaps_linked_to_gates() -> list[CheckResult]:
    _ensure_packages_path()
    from governance_catalog import load_gap_register

    catalog = load_gap_register(GAP_REGISTER)
    high = [g for g in catalog.get("gaps", []) if g.get("severity") in {"Critical", "High"}]
    unlinked = [
        g["gap_id"]
        for g in high
        if not isinstance(g.get("linked_phase_gates"), list) or not g.get("linked_phase_gates")
    ]
    return [
        CheckResult(
            "high-gaps-linked-to-phase-gates",
            "triage",
            "high-severity",
            "passed" if high and not unlinked else "failed",
            (
                f"high_or_critical={len(high)} linked"
                if high and not unlinked
                else f"unlinked={unlinked or 'none'}"
            ),
            [g["gap_id"] for g in high],
            "docs/10-gap-analysis/05-gap-triage-and-resolution-process.md",
        )
    ]


def verify_open_decisions_have_artifacts() -> list[CheckResult]:
    _ensure_packages_path()
    from governance_catalog import load_gap_register

    open_statuses = {"OPEN", "UNDER_REVIEW", "DECISION_NEEDED", "PLANNED"}
    catalog = load_gap_register(GAP_REGISTER)
    open_gaps = [g for g in catalog.get("gaps", []) if g.get("status") in open_statuses]
    missing = [
        g["gap_id"]
        for g in open_gaps
        if not str(g.get("proposed_resolution_artifact") or "").strip()
    ]
    if missing:
        status = "failed"
        detail = f"missing_artifacts={missing}"
    elif not open_gaps:
        status = "passed"
        detail = "open=0 artifacts_ok"
    else:
        status = "passed"
        detail = f"open={len(open_gaps)} artifacts_ok"
    return [
        CheckResult(
            "open-decisions-have-artifacts",
            "triage",
            "open-decisions",
            status,
            detail,
            [g["gap_id"] for g in open_gaps],
            "docs/10-gap-analysis/05-gap-triage-and-resolution-process.md",
        )
    ]


def verify_accepted_risks_have_approvers() -> list[CheckResult]:
    _ensure_packages_path()
    from governance_catalog import load_gap_register

    catalog = load_gap_register(GAP_REGISTER)
    accepted = [g for g in catalog.get("gaps", []) if g.get("status") == "ACCEPTED_RISK"]
    incomplete = [
        g["gap_id"]
        for g in accepted
        if not str(g.get("approver") or "").strip() or not str(g.get("review_date") or "").strip()
    ]
    # Vacuous pass when no accepted risks remain (closing the last one must not fail Phase 10).
    if incomplete:
        status = "failed"
        detail = f"incomplete={incomplete}"
    elif not accepted:
        status = "passed"
        detail = "accepted=0 review_ok"
    else:
        status = "passed"
        detail = f"accepted={len(accepted)} review_ok"
    return [
        CheckResult(
            "accepted-risks-have-approvers",
            "ownership",
            "accepted-risk",
            status,
            detail,
            [g["gap_id"] for g in accepted],
            "docs/10-gap-analysis/05-gap-triage-and-resolution-process.md",
        )
    ]


def verify_register_md_statuses_match_catalog() -> list[CheckResult]:
    """Keep machine catalog status aligned with the prose master register."""
    import re

    _ensure_packages_path()
    from governance_catalog import load_gap_register

    register_md = ROOT / "docs" / "10-gap-analysis" / "01-gap-register.md"
    register_parts = [
        register_md,
        *sorted(register_md.parent.glob("01-gap-register-continued*.md")),
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in register_parts)
    md_statuses = {
        match.group(1): match.group(2)
        for match in re.finditer(
            r"^## (GAP-(?:A\d+|T\d+|\d+))\b[\s\S]*?^Status:\s*(\S+)",
            text,
            re.MULTILINE,
        )
    }
    catalog = load_gap_register(GAP_REGISTER)
    mismatches: list[str] = []
    for item in catalog.get("gaps", []):
        gap_id = str(item.get("gap_id") or "")
        json_status = str(item.get("status") or "").strip()
        md_status = md_statuses.get(gap_id)
        if md_status is None:
            mismatches.append(f"{gap_id}:missing_in_md")
        elif md_status != json_status:
            mismatches.append(f"{gap_id}:md={md_status}/json={json_status}")
    for gap_id in sorted(set(md_statuses) - {str(g.get("gap_id") or "") for g in catalog.get("gaps", [])}):
        mismatches.append(f"{gap_id}:missing_in_json")
    return [
        CheckResult(
            "register-md-status-matches-catalog",
            "governance_catalog",
            "gap-register-parity",
            "passed" if not mismatches else "failed",
            "ok" if not mismatches else "; ".join(mismatches),
            sorted(md_statuses),
            "docs/10-gap-analysis/01-gap-register.md",
        )
    ]


def verify_closed_gaps_documented() -> list[CheckResult]:
    _ensure_packages_path()
    from governance_catalog import load_gap_register

    catalog = load_gap_register(GAP_REGISTER)
    closed = [g for g in catalog.get("gaps", []) if g.get("status") == "CLOSED"]
    missing = [g["gap_id"] for g in closed if not str(g.get("documentation_ref") or "").strip()]
    return [
        CheckResult(
            "closed-gaps-documented",
            "documentation",
            "closed",
            "passed" if closed and not missing else "failed",
            (
                f"closed={len(closed)} documented"
                if closed and not missing
                else f"missing_docs={missing or 'no closed gaps'}"
            ),
            [g["gap_id"] for g in closed],
            "docs/10-gap-analysis/05-gap-triage-and-resolution-process.md",
        )
    ]


def verify_gap_register_schema() -> list[CheckResult]:
    _ensure_packages_path()
    from governance_catalog import load_gap_register, validate_gap_register

    catalog = load_gap_register(GAP_REGISTER)
    errors = validate_gap_register(catalog)
    return [
        CheckResult(
            "gap-register-validate",
            "governance_catalog",
            "gap-register",
            "passed" if not errors else "failed",
            "ok" if not errors else "; ".join(errors),
            [str(GAP_REGISTER.relative_to(ROOT))],
            "docs/10-gap-analysis/01-gap-register.md",
        )
    ]


def run_all_checks() -> list[CheckResult]:
    results: list[CheckResult] = []
    results.extend(verify_gap_register_schema())
    results.extend(verify_register_md_statuses_match_catalog())
    results.extend(verify_critical_gaps_have_owners())
    results.extend(verify_high_gaps_linked_to_gates())
    results.extend(verify_open_decisions_have_artifacts())
    results.extend(verify_accepted_risks_have_approvers())
    results.extend(verify_closed_gaps_documented())
    return results


def public_results(results: list[CheckResult]) -> list[dict[str, Any]]:
    return [item.public() for item in results]

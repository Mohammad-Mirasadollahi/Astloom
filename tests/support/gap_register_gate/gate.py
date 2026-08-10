from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import sys
from typing import Any

from .catalog import (
    DOC_TOPIC_MARKERS,
    DOCS,
    GAP_REGISTER,
    GOVERNANCE_PACKAGE,
    REQUIRED_DOCS,
    ROOT,
)


@dataclass
class CheckResult:
    check_id: str
    check_type: str
    subject_ref: str
    status: str
    message: str
    evidence_refs: list[str] = field(default_factory=list)
    documentation_ref: str = ""

    def public(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "check_type": self.check_type,
            "subject_ref": self.subject_ref,
            "status": self.status,
            "message": self.message,
            "evidence_refs": self.evidence_refs,
            "documentation_ref": self.documentation_ref,
        }


@dataclass
class PhaseGateDecision:
    phase_number: int
    status: str
    owner: str
    waiver_ref: str | None
    checks: list[CheckResult]

    def public(self) -> dict[str, Any]:
        return {
            "phase_number": self.phase_number,
            "status": self.status,
            "owner": self.owner,
            "waiver_ref": self.waiver_ref,
            "blocked": self.status == "fail",
            "checks": [item.public() for item in self.checks],
            "passed_count": sum(1 for item in self.checks if item.status == "passed"),
            "failed_count": sum(1 for item in self.checks if item.status == "failed"),
        }


def explain_failed_check(decision: PhaseGateDecision, check_id: str) -> dict[str, Any]:
    for check in decision.checks:
        if check.check_id == check_id:
            return {
                "check": check.public(),
                "rationale": check.message,
                "documentation_ref": check.documentation_ref,
                "evidence_refs": check.evidence_refs,
            }
    raise KeyError(f"check not found: {check_id}")


def _path_check(check_id: str, check_type: str, subject: str, path: Path, doc_ref: str) -> CheckResult:
    ok = path.exists()
    return CheckResult(
        check_id,
        check_type,
        subject,
        "passed" if ok else "failed",
        f"{path.relative_to(ROOT)} {'present' if ok else 'missing'}",
        [str(path.relative_to(ROOT))],
        doc_ref,
    )


def _ensure_packages_path() -> None:
    packages = str(ROOT / "backend" / "packages")
    if packages not in sys.path:
        sys.path.insert(0, packages)


def check_phase_gate(
    *,
    owner: str = "gap-analysis",
    waiver_ref: str | None = None,
) -> PhaseGateDecision:
    """Evaluate the gap-register exit gate."""
    _ = os.environ
    checks: list[CheckResult] = []

    for index, path in enumerate(REQUIRED_DOCS, start=1):
        checks.append(
            _path_check(
                f"gap-register-doc-{index}",
                "documentation",
                "gap-register",
                path,
                "docs/10-gap-analysis",
            )
        )

    checks.append(
        _path_check(
            "gap-register-file",
            "governance_catalog",
            "gap-register",
            GAP_REGISTER,
            "docs/10-gap-analysis/01-gap-register.md",
        )
    )
    checks.append(
        _path_check(
            "gap-register-governance-package",
            "governance_catalog",
            "governance_catalog",
            GOVERNANCE_PACKAGE / "loader.py",
            "docs/10-gap-analysis/06-phase10-verification-and-acceptance.md",
        )
    )

    _ensure_packages_path()
    try:
        from governance_catalog import load_gap_register, validate_gap_register

        errors = validate_gap_register(load_gap_register(GAP_REGISTER))
        checks.append(
            CheckResult(
                "gap-register-valid",
                "governance_catalog",
                "gap-register",
                "passed" if not errors else "failed",
                "gap register valid" if not errors else "; ".join(errors),
                [str(GAP_REGISTER.relative_to(ROOT))],
                "docs/10-gap-analysis/01-gap-register.md",
            )
        )
    except Exception as exc:  # pragma: no cover
        checks.append(
            CheckResult(
                "gap-register-valid",
                "governance_catalog",
                "gap-register",
                "failed",
                f"catalog load failed: {exc}",
                [],
                "docs/10-gap-analysis/06-phase10-verification-and-acceptance.md",
            )
        )

    for index, (filename, marker) in enumerate(DOC_TOPIC_MARKERS, start=1):
        path = DOCS / filename
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        ok = path.is_file() and marker.lower() in text.lower()
        checks.append(
            CheckResult(
                f"gap-register-topic-{index}-{filename}",
                "documentation",
                filename,
                "passed" if ok else "failed",
                f"marker {marker!r} {'present' if ok else 'missing'}",
                [str(path.relative_to(ROOT))],
                str(path.relative_to(ROOT)),
            )
        )

    failed = [item for item in checks if item.status == "failed"]
    if failed and waiver_ref:
        status = "waived"
    elif failed:
        status = "fail"
    else:
        status = "pass"
    return PhaseGateDecision(10, status, owner, waiver_ref, checks)

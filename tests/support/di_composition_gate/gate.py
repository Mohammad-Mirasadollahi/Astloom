"""Phase gate decision model for DI composition verification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CheckResult:
    check_id: str
    check_type: str
    subject: str
    status: str
    detail: str
    evidence: list[str] = field(default_factory=list)
    doc_ref: str = ""

    def public(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "check_type": self.check_type,
            "subject": self.subject,
            "status": self.status,
            "detail": self.detail,
            "evidence": list(self.evidence),
            "doc_ref": self.doc_ref,
        }


@dataclass
class PhaseGateDecision:
    phase: int
    status: str
    owner: str
    waiver_ref: str | None
    checks: list[CheckResult]

    def public(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "status": self.status,
            "owner": self.owner,
            "waiver_ref": self.waiver_ref,
            "blocked": self.status == "fail",
            "passed_count": sum(1 for item in self.checks if item.status == "passed"),
            "failed_count": sum(1 for item in self.checks if item.status == "failed"),
            "checks": [item.public() for item in self.checks],
        }


def check_phase_gate(
    *,
    owner: str = "platform-architecture",
    waiver_ref: str | None = None,
) -> PhaseGateDecision:
    from .checks import run_all_checks

    checks = run_all_checks()
    failed = [item for item in checks if item.status == "failed"]
    if failed and waiver_ref:
        status = "waived"
    elif failed:
        status = "fail"
    else:
        status = "pass"
    return PhaseGateDecision(8, status, owner, waiver_ref, checks)


def explain_failed_check(decision: PhaseGateDecision, check_id: str) -> dict[str, Any]:
    for item in decision.checks:
        if item.check_id == check_id:
            return {"check": item.public()}
    return {"check": None}

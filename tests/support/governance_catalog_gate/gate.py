from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import sys
from typing import Any

from .catalog import (
    DOC_TOPIC_MARKERS,
    DOCS,
    GOVERNANCE_PACKAGE,
    IMPACT_KPIS,
    REQUIRED_DOCS,
    RISK_CATALOG,
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
    owner: str = "platform-governance",
    waiver_ref: str | None = None,
) -> PhaseGateDecision:
    """Evaluate the governance-catalog exit gate."""
    _ = os.environ  # reserved for future suite toggles
    checks: list[CheckResult] = []

    for index, path in enumerate(REQUIRED_DOCS, start=1):
        checks.append(
            _path_check(
                f"governance-catalog-doc-{index}",
                "documentation",
                "governance-catalog",
                path,
                "docs/09-platform-governance-operations",
            )
        )

    checks.append(
        _path_check(
            "governance-catalog-risk-catalog",
            "governance_catalog",
            "risk-open-decisions",
            RISK_CATALOG,
            "docs/09-platform-governance-operations/07-risk-register-and-open-decisions.md",
        )
    )
    checks.append(
        _path_check(
            "governance-catalog-impact-kpis",
            "governance_catalog",
            "impact-kpis",
            IMPACT_KPIS,
            "docs/09-platform-governance-operations/10-impact-reporting-and-benefit-measurement.md",
        )
    )
    checks.append(
        _path_check(
            "governance-catalog-package",
            "governance_catalog",
            "governance_catalog",
            GOVERNANCE_PACKAGE / "loader.py",
            "docs/09-platform-governance-operations/11-phase9-verification-and-acceptance.md",
        )
    )

    _ensure_packages_path()
    try:
        from governance_catalog import (
            load_impact_kpis,
            load_risk_catalog,
            validate_impact_kpis,
            validate_risk_catalog,
        )

        risk_errors = validate_risk_catalog(load_risk_catalog(RISK_CATALOG))
        checks.append(
            CheckResult(
                "governance-catalog-risk-catalog-valid",
                "governance_catalog",
                "risk-open-decisions",
                "passed" if not risk_errors else "failed",
                "risk catalog valid" if not risk_errors else "; ".join(risk_errors),
                [str(RISK_CATALOG.relative_to(ROOT))],
                "docs/09-platform-governance-operations/07-risk-register-and-open-decisions.md",
            )
        )
        kpi_errors = validate_impact_kpis(load_impact_kpis(IMPACT_KPIS))
        checks.append(
            CheckResult(
                "governance-catalog-impact-kpis-valid",
                "governance_catalog",
                "impact-kpis",
                "passed" if not kpi_errors else "failed",
                "impact KPI catalog valid" if not kpi_errors else "; ".join(kpi_errors),
                [str(IMPACT_KPIS.relative_to(ROOT))],
                "docs/09-platform-governance-operations/10-impact-reporting-and-benefit-measurement.md",
            )
        )
    except Exception as exc:  # pragma: no cover
        checks.append(
            CheckResult(
                "governance-catalogs-valid",
                "governance_catalog",
                "governance",
                "failed",
                f"catalog load failed: {exc}",
                [],
                "docs/09-platform-governance-operations/11-phase9-verification-and-acceptance.md",
            )
        )

    for index, (filename, marker) in enumerate(DOC_TOPIC_MARKERS, start=1):
        path = DOCS / filename
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        ok = path.is_file() and marker.lower() in text.lower()
        checks.append(
            CheckResult(
                f"governance-catalog-topic-{index}-{filename}",
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
    return PhaseGateDecision(9, status, owner, waiver_ref, checks)

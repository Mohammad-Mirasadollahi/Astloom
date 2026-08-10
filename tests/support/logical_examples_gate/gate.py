from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import sys
from typing import Any

from .catalog import (
    DOC_TOPIC_MARKERS,
    DOCS,
    EXAMPLES_CATALOG,
    LOGICAL_EXAMPLES_PACKAGE,
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
    owner: str = "logical-examples",
    waiver_ref: str | None = None,
) -> PhaseGateDecision:
    """Evaluate the logical-examples catalog exit gate."""
    _ = os.environ
    checks: list[CheckResult] = []

    for index, path in enumerate(REQUIRED_DOCS, start=1):
        checks.append(
            _path_check(
                f"logical-examples-doc-{index}",
                "documentation",
                "logical-examples",
                path,
                "docs/11-logical-implementation-examples",
            )
        )

    checks.append(
        _path_check(
            "logical-examples-catalog",
            "examples_catalog",
            "examples-catalog",
            EXAMPLES_CATALOG,
            "docs/11-logical-implementation-examples/00-index.md",
        )
    )
    checks.append(
        _path_check(
            "logical-examples-package",
            "examples_catalog",
            "logical_examples",
            LOGICAL_EXAMPLES_PACKAGE / "loader.py",
            "docs/11-logical-implementation-examples/07-phase11-verification-and-acceptance.md",
        )
    )

    _ensure_packages_path()
    try:
        from logical_examples import load_examples_catalog, validate_examples_catalog

        errors = validate_examples_catalog(load_examples_catalog(EXAMPLES_CATALOG))
        checks.append(
            CheckResult(
                "logical-examples-catalog-valid",
                "examples_catalog",
                "examples-catalog",
                "passed" if not errors else "failed",
                "examples catalog valid" if not errors else "; ".join(errors),
                [str(EXAMPLES_CATALOG.relative_to(ROOT))],
                "docs/11-logical-implementation-examples/07-phase11-verification-and-acceptance.md",
            )
        )
    except Exception as exc:  # pragma: no cover
        checks.append(
            CheckResult(
                "logical-examples-catalog-valid",
                "examples_catalog",
                "examples-catalog",
                "failed",
                f"catalog load failed: {exc}",
                [],
                "docs/11-logical-implementation-examples/07-phase11-verification-and-acceptance.md",
            )
        )

    for index, (filename, marker) in enumerate(DOC_TOPIC_MARKERS, start=1):
        path = DOCS / filename
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        ok = path.is_file() and marker.lower() in text.lower()
        checks.append(
            CheckResult(
                f"logical-examples-topic-{index}-{filename}",
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
    return PhaseGateDecision(11, status, owner, waiver_ref, checks)

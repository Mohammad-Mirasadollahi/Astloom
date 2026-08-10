from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from .catalog import TECHNICAL_LOGIC_DOCS, PHASE_SLICES, ROOT, get_slice


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


def check_phase_gate(
    *,
    run_suites: bool | None = None,
    owner: str = "platform-verification",
    waiver_ref: str | None = None,
) -> PhaseGateDecision:
    """Evaluate the technical-logic gate for owned vertical-slice services."""
    if run_suites is None:
        run_suites = os.environ.get("ASTLOOM_TECHNICAL_LOGIC_RUN_SUITES", "").strip() in {"1", "true", "yes"} or os.environ.get(
            "ASTLOOM_PHASE6_RUN_SUITES", ""
        ).strip() in {"1", "true", "yes"}
    checks: list[CheckResult] = []

    for index, path in enumerate(TECHNICAL_LOGIC_DOCS, start=1):
        checks.append(_path_check(f"technical-logic-doc-{index}", "documentation", "technical-logic", path, "docs/06-technical-logic"))

    for item in PHASE_SLICES:
        checks.append(_path_check(f"src-{item.service}", "canonical_path", item.service, item.src_path, str(item.logic_doc.relative_to(ROOT))))
        checks.append(_path_check(f"tests-{item.service}", "canonical_path", item.service, item.test_path, str(item.logic_doc.relative_to(ROOT))))
        checks.append(_path_check(f"logic-{item.service}", "documentation", item.service, item.logic_doc, str(item.logic_doc.relative_to(ROOT))))
        checks.append(_readme_mentions_command(item))
        if run_suites:
            checks.append(_run_pytest_suite(item))

    failed = [item for item in checks if item.status == "failed"]
    if waiver_ref and failed:
        status = "waived"
    elif failed:
        status = "fail"
    else:
        status = "pass"
    return PhaseGateDecision(6, status, owner, waiver_ref, checks)


def _path_check(check_id: str, check_type: str, subject: str, path: Path, doc_ref: str) -> CheckResult:
    if path.exists():
        return CheckResult(check_id, check_type, subject, "passed", f"path exists: {path.relative_to(ROOT)}", [str(path.relative_to(ROOT))], doc_ref)
    return CheckResult(check_id, check_type, subject, "failed", f"missing path: {path}", [str(path)], doc_ref)


def _readme_mentions_command(item) -> CheckResult:
    readme = ROOT / "backend/services" / item.service / "README.md"
    doc_ref = str(item.logic_doc.relative_to(ROOT))
    if not readme.exists():
        return CheckResult(f"readme-{item.service}", "canonical_command", item.service, "failed", "service README missing", [str(readme)], doc_ref)
    text = readme.read_text(encoding="utf-8")
    needle = f"tests/backend/services/{item.service}"
    if needle in text:
        return CheckResult(f"readme-{item.service}", "canonical_command", item.service, "passed", f"README references {needle}", [str(readme.relative_to(ROOT))], doc_ref)
    return CheckResult(f"readme-{item.service}", "canonical_command", item.service, "failed", f"README missing canonical test path {needle}", [str(readme.relative_to(ROOT))], doc_ref)


def _run_pytest_suite(item) -> CheckResult:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(item.src_path)
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", str(item.test_path), "-q"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    evidence = [str(item.test_path.relative_to(ROOT))]
    if completed.returncode == 0:
        return CheckResult(
            f"pytest-{item.service}",
            "suite",
            item.service,
            "passed",
            "pytest suite passed",
            evidence,
            str(item.logic_doc.relative_to(ROOT)),
        )
    return CheckResult(
        f"pytest-{item.service}",
        "suite",
        item.service,
        "failed",
        (completed.stdout + completed.stderr)[-500:] or "pytest suite failed",
        evidence,
        str(item.logic_doc.relative_to(ROOT)),
    )


def list_required_checks(phase: int) -> list[dict[str, str]]:
    from .catalog import required_checks_for_phase

    return required_checks_for_phase(phase)


def get_canonical_test_command(phase: int) -> str:
    return get_slice(phase).pytest_command

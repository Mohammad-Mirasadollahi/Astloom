from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from .catalog import (
    DOC_TOPIC_MARKERS,
    DOCS,
    OWNED_SERVICES,
    PORT_PACKAGE,
    PORT_PROFILE,
    REQUIRED_DOCS,
    ROOT,
    SHARED_PACKAGE_LOADERS,
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
    run_suites: bool | None = None,
    owner: str = "platform-engineering",
    waiver_ref: str | None = None,
) -> PhaseGateDecision:
    """Evaluate the port-profile and service-ownership exit gate."""
    if run_suites is None:
        run_suites = os.environ.get("ASTLOOM_PHASE8_RUN_SUITES", "").strip() in {"1", "true", "yes"}
    checks: list[CheckResult] = []

    for index, path in enumerate(REQUIRED_DOCS, start=1):
        checks.append(
            _path_check(
                f"port-profile-doc-{index}",
                "documentation",
                "port-profile",
                path,
                "docs/08-software-engineering-architecture",
            )
        )

    checks.append(
        _path_check(
            "port-profile-file",
            "port_profile",
            "port-profiles",
            PORT_PROFILE,
            "docs/08-software-engineering-architecture/04-development-port-management.md",
        )
    )
    checks.append(
        _path_check(
            "port-profile-package",
            "port_profile",
            "port_profile",
            PORT_PACKAGE / "loader.py",
            "docs/08-software-engineering-architecture/04-development-port-management.md",
        )
    )
    for name, loader_path in SHARED_PACKAGE_LOADERS:
        checks.append(
            _path_check(
                f"port-profile-shared-pkg-{name}",
                "shared_package",
                name,
                loader_path,
                "docs/08-software-engineering-architecture/05-modular-project-structure.md",
            )
        )

    _ensure_packages_path()
    try:
        from port_profile import load_profile, validate_profile

        profile = load_profile(PORT_PROFILE)
        errors = validate_profile(profile)
        checks.append(
            CheckResult(
                "port-profile-valid",
                "port_profile",
                "astloom-dev",
                "passed" if not errors else "failed",
                "profile valid" if not errors else "; ".join(errors),
                [str(PORT_PROFILE.relative_to(ROOT))],
                "docs/08-software-engineering-architecture/04-development-port-management.md",
            )
        )
        owners = profile.get("service_owners") or {}
        for service in OWNED_SERVICES:
            ok = owners.get(service.name) == service.port_key
            checks.append(
                CheckResult(
                    f"port-profile-owner-{service.name}",
                    "ownership",
                    service.name,
                    "passed" if ok else "failed",
                    f"port key {service.port_key} {'mapped' if ok else 'missing/mismatch'}",
                    [service.port_key],
                    "docs/08-software-engineering-architecture/02-service-boundaries-and-modules.md",
                )
            )
    except Exception as exc:  # pragma: no cover - surfaced as gate failure
        checks.append(
            CheckResult(
                "port-profile-valid",
                "port_profile",
                "astloom-dev",
                "failed",
                f"profile load failed: {exc}",
                [str(PORT_PROFILE.relative_to(ROOT))],
                "docs/08-software-engineering-architecture/04-development-port-management.md",
            )
        )

    for service in OWNED_SERVICES:
        checks.append(
            _path_check(
                f"port-profile-service-src-{service.name}",
                "ownership",
                service.name,
                service.src_path,
                "docs/08-software-engineering-architecture/02-service-boundaries-and-modules.md",
            )
        )
        checks.append(
            _path_check(
                f"port-profile-service-tests-{service.name}",
                "testing",
                service.name,
                service.test_path,
                "docs/08-software-engineering-architecture/25-live-and-unit-test-strategy.md",
            )
        )
        contracts = list((ROOT / "backend" / "services" / service.name).glob(service.contract_glob))
        checks.append(
            CheckResult(
                f"port-profile-contract-{service.name}",
                "contract",
                service.name,
                "passed" if contracts else "failed",
                f"contract {'found' if contracts else 'missing'}: {service.contract_glob}",
                [str(path.relative_to(ROOT)) for path in contracts],
                "docs/08-software-engineering-architecture/08-interface-and-contract-engineering.md",
            )
        )

    for filename, marker in DOC_TOPIC_MARKERS:
        path = DOCS / filename
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        ok = path.is_file() and marker.lower() in text.lower()
        checks.append(
            CheckResult(
                f"port-profile-topic-{filename}",
                "documentation",
                filename,
                "passed" if ok else "failed",
                f"marker {marker!r} {'present' if ok else 'missing'}",
                [str(path.relative_to(ROOT))],
                str(path.relative_to(ROOT)),
            )
        )

    if run_suites:
        for service in OWNED_SERVICES:
            command = [
                str(ROOT / ".venv" / "bin" / "python"),
                "-m",
                "pytest",
                str(service.test_path),
                "-q",
            ]
            env = os.environ.copy()
            env["PYTHONPATH"] = str(service.src_path)
            completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, check=False)
            ok = completed.returncode == 0
            checks.append(
                CheckResult(
                    f"port-profile-suite-{service.name}",
                    "test_suite",
                    service.name,
                    "passed" if ok else "failed",
                    "pytest passed" if ok else (completed.stdout + completed.stderr)[-500:],
                    [str(service.test_path.relative_to(ROOT))],
                    "docs/08-software-engineering-architecture/25-live-and-unit-test-strategy.md",
                )
            )

    failed = [item for item in checks if item.status == "failed"]
    if failed and waiver_ref:
        status = "waived"
    elif failed:
        status = "fail"
    else:
        status = "pass"
    return PhaseGateDecision(8, status, owner, waiver_ref, checks)

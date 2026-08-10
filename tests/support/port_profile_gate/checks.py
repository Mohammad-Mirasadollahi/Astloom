from __future__ import annotations

import sys
from typing import Any

from .catalog import OWNED_SERVICES, PORT_PROFILE, ROOT
from .gate import CheckResult


def _ensure_packages_path() -> None:
    packages = str(ROOT / "backend" / "packages")
    if packages not in sys.path:
        sys.path.insert(0, packages)


def verify_port_profile_rules() -> list[CheckResult]:
    _ensure_packages_path()
    from port_profile import FORBIDDEN_COMMON_PORTS, load_profile, resolve_ports, validate_profile

    profile = load_profile(PORT_PROFILE)
    errors = validate_profile(profile)
    results = [
        CheckResult(
            "ports-validate",
            "port_profile",
            "astloom-dev",
            "passed" if not errors else "failed",
            "ok" if not errors else "; ".join(errors),
            [str(PORT_PROFILE.relative_to(ROOT))],
            "docs/08-software-engineering-architecture/04-development-port-management.md",
        )
    ]
    resolved = resolve_ports(profile, environ={})
    colliding = [f"{key}={value}" for key, value in resolved.items() if value in FORBIDDEN_COMMON_PORTS]
    results.append(
        CheckResult(
            "ports-no-common-defaults",
            "port_profile",
            "astloom-dev",
            "passed" if not colliding else "failed",
            "no common defaults" if not colliding else f"collisions: {', '.join(colliding)}",
            list(resolved),
            "docs/08-software-engineering-architecture/04-development-port-management.md",
        )
    )
    override = resolve_ports(profile, environ={"ASTLOOM_API_PORT": "32199"})
    results.append(
        CheckResult(
            "ports-env-override",
            "port_profile",
            "ASTLOOM_API_PORT",
            "passed" if override["ASTLOOM_API_PORT"] == 32199 else "failed",
            f"resolved={override['ASTLOOM_API_PORT']}",
            ["ASTLOOM_API_PORT"],
            "docs/08-software-engineering-architecture/04-development-port-management.md",
        )
    )
    return results


def verify_service_boundaries() -> list[CheckResult]:
    results: list[CheckResult] = []
    for service in OWNED_SERVICES:
        readme = ROOT / "backend" / "services" / service.name / "README.md"
        ok = service.src_path.is_dir() and readme.is_file()
        results.append(
            CheckResult(
                f"boundary-{service.name}",
                "ownership",
                service.name,
                "passed" if ok else "failed",
                "service boundary present" if ok else "missing src or README",
                [str(service.src_path.relative_to(ROOT)), str(readme.relative_to(ROOT))],
                "docs/08-software-engineering-architecture/02-service-boundaries-and-modules.md",
            )
        )
    return results


def verify_contract_ownership() -> list[CheckResult]:
    results: list[CheckResult] = []
    for service in OWNED_SERVICES:
        contracts = list((ROOT / "backend" / "services" / service.name).glob(service.contract_glob))
        text = contracts[0].read_text(encoding="utf-8") if contracts else ""
        has_api = "/api/v1/" in text
        has_scope = "Idempotency-Key" in text or "X-Tenant-Id" in text
        has_heading = any(token in text for token in ("Purpose", "Resources", "Commands", "Version"))
        ok = bool(contracts) and has_api and has_scope and has_heading
        results.append(
            CheckResult(
                f"contract-quality-{service.name}",
                "contract",
                service.name,
                "passed" if ok else "failed",
                "contract has api/scope/heading markers" if ok else "contract incomplete",
                [str(path.relative_to(ROOT)) for path in contracts],
                "docs/08-software-engineering-architecture/08-interface-and-contract-engineering.md",
            )
        )
    return results


def run_all_checks() -> list[CheckResult]:
    results: list[CheckResult] = []
    results.extend(verify_port_profile_rules())
    results.extend(verify_service_boundaries())
    results.extend(verify_contract_ownership())
    return results


def public_results(results: list[CheckResult]) -> list[dict[str, Any]]:
    return [item.public() for item in results]

from __future__ import annotations

import sys
from typing import Any

from .catalog import IMPACT_KPIS, RISK_CATALOG, ROOT
from .gate import CheckResult


def _ensure_packages_path() -> None:
    packages = str(ROOT / "backend" / "packages")
    if packages not in sys.path:
        sys.path.insert(0, packages)


def verify_risk_and_decision_ownership() -> list[CheckResult]:
    _ensure_packages_path()
    from governance_catalog import load_risk_catalog, validate_risk_catalog

    catalog = load_risk_catalog(RISK_CATALOG)
    errors = validate_risk_catalog(catalog)
    results = [
        CheckResult(
            "risks-validate",
            "governance_catalog",
            "risk-open-decisions",
            "passed" if not errors else "failed",
            "ok" if not errors else "; ".join(errors),
            [str(RISK_CATALOG.relative_to(ROOT))],
            "docs/09-platform-governance-operations/07-risk-register-and-open-decisions.md",
        )
    ]
    owners = {item["owner"] for item in catalog.get("risks", [])}
    results.append(
        CheckResult(
            "risks-have-owners",
            "ownership",
            "risks",
            "passed" if owners else "failed",
            f"owners={sorted(owners)}",
            sorted(owners),
            "docs/09-platform-governance-operations/07-risk-register-and-open-decisions.md",
        )
    )
    return results


def verify_impact_kpi_completeness() -> list[CheckResult]:
    _ensure_packages_path()
    from governance_catalog import load_impact_kpis, validate_impact_kpis

    catalog = load_impact_kpis(IMPACT_KPIS)
    errors = validate_impact_kpis(catalog)
    return [
        CheckResult(
            "impact-kpis-validate",
            "governance_catalog",
            "impact-kpis",
            "passed" if not errors else "failed",
            "ok" if not errors else "; ".join(errors),
            [str(IMPACT_KPIS.relative_to(ROOT))],
            "docs/09-platform-governance-operations/10-impact-reporting-and-benefit-measurement.md",
        ),
        CheckResult(
            "impact-comparison-method",
            "reporting",
            "comparison_method",
            "passed" if catalog.get("comparison_method") == "with-or-without-astloom" else "failed",
            f"method={catalog.get('comparison_method')}",
            ["with-or-without-astloom"],
            "docs/09-platform-governance-operations/10-impact-reporting-and-benefit-measurement.md",
        ),
    ]


def run_all_checks() -> list[CheckResult]:
    results: list[CheckResult] = []
    results.extend(verify_risk_and_decision_ownership())
    results.extend(verify_impact_kpi_completeness())
    return results


def public_results(results: list[CheckResult]) -> list[dict[str, Any]]:
    return [item.public() for item in results]

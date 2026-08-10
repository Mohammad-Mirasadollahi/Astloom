from __future__ import annotations

import json
from pathlib import Path
from typing import Any


GOVERNANCE_DIR = Path(__file__).resolve().parents[2] / "configs" / "governance"
RISK_CATALOG_PATH = GOVERNANCE_DIR / "risk-open-decisions.json"
IMPACT_KPI_PATH = GOVERNANCE_DIR / "impact-kpis.json"
GAP_REGISTER_PATH = GOVERNANCE_DIR / "gap-register.json"
BOUNDED_CONTEXT_MAP_PATH = GOVERNANCE_DIR / "bounded-context-map.json"
SYNC_ASYNC_PATH = GOVERNANCE_DIR / "sync-async-boundaries.json"
READ_MODEL_PATH = GOVERNANCE_DIR / "read-model-catalog.json"
TENANCY_MODES_PATH = GOVERNANCE_DIR / "tenancy-deployment-modes.json"
AGENT_TRUST_PATH = GOVERNANCE_DIR / "agent-trust-policy.json"
IDE_BOUNDARY_PATH = GOVERNANCE_DIR / "ide-product-boundary.json"
ADMIN_MATRIX_PATH = GOVERNANCE_DIR / "admin-permission-matrix.json"

ALLOWED_GAP_STATUSES = {
    "OPEN",
    "UNDER_REVIEW",
    "DECISION_NEEDED",
    "PLANNED",
    "PARTIALLY_RESOLVED",
    "CLOSED",
    "ACCEPTED_RISK",
}
ALLOWED_GAP_SEVERITIES = {"Critical", "High", "Medium", "Low"}
HIGH_SEVERITIES = {"Critical", "High"}
DECISION_STATUSES = {"OPEN", "UNDER_REVIEW", "DECISION_NEEDED", "PLANNED"}

REQUIRED_KPI_FIELDS = (
    "definition",
    "instrumentation",
    "baseline",
    "scope",
    "time_range",
    "sample_size",
    "caveats",
    "evidence_drilldown",
)

REQUIRED_KPI_NAMES = {
    "initial_code_generation_speed",
    "bug_reduction",
    "architecture_quality",
    "rework_reduction",
    "token_consumption",
}


class GovernanceCatalogError(ValueError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GovernanceCatalogError(f"catalog missing: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise GovernanceCatalogError(f"catalog must be an object: {path}")
    return data


def load_risk_catalog(path: Path | None = None) -> dict[str, Any]:
    return _load_json(path or RISK_CATALOG_PATH)


def load_impact_kpis(path: Path | None = None) -> dict[str, Any]:
    return _load_json(path or IMPACT_KPI_PATH)


def load_gap_register(path: Path | None = None) -> dict[str, Any]:
    return _load_json(path or GAP_REGISTER_PATH)


def load_bounded_context_map(path: Path | None = None) -> dict[str, Any]:
    return _load_json(path or BOUNDED_CONTEXT_MAP_PATH)


def load_sync_async_boundaries(path: Path | None = None) -> dict[str, Any]:
    return _load_json(path or SYNC_ASYNC_PATH)


def load_read_model_catalog(path: Path | None = None) -> dict[str, Any]:
    return _load_json(path or READ_MODEL_PATH)


def load_tenancy_deployment_modes(path: Path | None = None) -> dict[str, Any]:
    return _load_json(path or TENANCY_MODES_PATH)


def load_agent_trust_policy(path: Path | None = None) -> dict[str, Any]:
    return _load_json(path or AGENT_TRUST_PATH)


def load_ide_product_boundary(path: Path | None = None) -> dict[str, Any]:
    return _load_json(path or IDE_BOUNDARY_PATH)


def load_admin_permission_matrix(path: Path | None = None) -> dict[str, Any]:
    return _load_json(path or ADMIN_MATRIX_PATH)


def validate_risk_catalog(catalog: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    risks = catalog.get("risks")
    decisions = catalog.get("open_decisions")
    if not isinstance(risks, list) or not risks:
        errors.append("risks list is required")
    else:
        for item in risks:
            for field in ("risk_id", "title", "severity", "owner", "mitigation", "review_date"):
                if not str(item.get(field) or "").strip():
                    errors.append(f"risk missing {field}: {item.get('risk_id')}")
    if not isinstance(decisions, list) or not decisions:
        errors.append("open_decisions list is required")
    else:
        for item in decisions:
            for field in ("decision_id", "title", "owner", "proposed_resolution", "status", "review_date"):
                if not str(item.get(field) or "").strip():
                    errors.append(f"decision missing {field}: {item.get('decision_id')}")
    return errors


def validate_impact_kpis(catalog: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_fields = catalog.get("required_report_fields") or []
    for field in REQUIRED_KPI_FIELDS:
        if field not in required_fields:
            errors.append(f"required_report_fields missing {field}")
    kpis = catalog.get("kpis")
    if not isinstance(kpis, list) or not kpis:
        errors.append("kpis list is required")
        return errors
    names = {str(item.get("name") or "") for item in kpis}
    missing_names = sorted(REQUIRED_KPI_NAMES - names)
    if missing_names:
        errors.append(f"missing KPI names: {', '.join(missing_names)}")
    for item in kpis:
        for field in REQUIRED_KPI_FIELDS:
            if not str(item.get(field) or "").strip():
                errors.append(f"KPI {item.get('kpi_id')} missing {field}")
    if str(catalog.get("comparison_method") or "") != "with-or-without-astloom":
        errors.append("comparison_method must be with-or-without-astloom")
    return errors


def validate_gap_register(catalog: dict[str, Any]) -> list[str]:
    """Validate Phase 10 gap register exit criteria."""
    errors: list[str] = []
    gaps = catalog.get("gaps")
    if not isinstance(gaps, list) or not gaps:
        errors.append("gaps list is required")
        return errors

    seen_ids: set[str] = set()
    for item in gaps:
        if not isinstance(item, dict):
            errors.append("gap entry must be an object")
            continue
        gap_id = str(item.get("gap_id") or "").strip()
        if not gap_id:
            errors.append("gap missing gap_id")
            continue
        if gap_id in seen_ids:
            errors.append(f"duplicate gap_id: {gap_id}")
        seen_ids.add(gap_id)

        for field in ("title", "category", "severity", "owner", "status", "documentation_ref"):
            if not str(item.get(field) or "").strip():
                errors.append(f"{gap_id} missing {field}")

        severity = str(item.get("severity") or "").strip()
        status = str(item.get("status") or "").strip()
        if severity and severity not in ALLOWED_GAP_SEVERITIES:
            errors.append(f"{gap_id} invalid severity: {severity}")
        if status and status not in ALLOWED_GAP_STATUSES:
            errors.append(f"{gap_id} invalid status: {status}")

        owner = str(item.get("owner") or "").strip()
        if severity == "Critical" and not owner:
            errors.append(f"{gap_id} critical gap requires owner")

        if severity in HIGH_SEVERITIES:
            gates = item.get("linked_phase_gates")
            if not isinstance(gates, list) or not gates:
                errors.append(f"{gap_id} high/critical gap requires linked_phase_gates")
            elif not all(isinstance(g, int) and g >= 1 for g in gates):
                errors.append(f"{gap_id} linked_phase_gates must be positive integers")

        if status in DECISION_STATUSES:
            artifact = str(item.get("proposed_resolution_artifact") or "").strip()
            if not artifact:
                errors.append(f"{gap_id} open decision requires proposed_resolution_artifact")

        if status == "ACCEPTED_RISK":
            if not str(item.get("approver") or "").strip():
                errors.append(f"{gap_id} accepted risk requires approver")
            if not str(item.get("review_date") or "").strip():
                errors.append(f"{gap_id} accepted risk requires review_date")

        if status == "CLOSED":
            doc_ref = str(item.get("documentation_ref") or "").strip()
            if not doc_ref:
                errors.append(f"{gap_id} closed gap requires documentation_ref")

    return errors

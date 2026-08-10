"""Architecture governance catalogs (GAP-A01–A07).

Role: load machine-readable architecture closures and apply lightweight enforcement helpers.
SoT: backend/configs/governance/* JSON catalogs.
Allowed: fail-closed validation of mode/env; soft policy helpers for trust/admin.
Forbidden: UI concerns; inventing entities not owned by a service context.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

GOVERNANCE_DIR = Path(__file__).resolve().parents[2] / "configs" / "governance"

CATALOG_FILES = {
    "bounded_context_map": "bounded-context-map.json",
    "sync_async_boundaries": "sync-async-boundaries.json",
    "read_model_catalog": "read-model-catalog.json",
    "tenancy_deployment_modes": "tenancy-deployment-modes.json",
    "agent_trust_policy": "agent-trust-policy.json",
    "ide_product_boundary": "ide-product-boundary.json",
    "admin_permission_matrix": "admin-permission-matrix.json",
}


class ArchitectureGovernanceError(ValueError):
    pass


def _load(name: str) -> dict[str, Any]:
    path = GOVERNANCE_DIR / CATALOG_FILES[name]
    if not path.is_file():
        raise ArchitectureGovernanceError(f"missing catalog: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ArchitectureGovernanceError(f"catalog must be object: {path}")
    return data


def load_bounded_context_map() -> dict[str, Any]:
    return _load("bounded_context_map")


def load_sync_async_boundaries() -> dict[str, Any]:
    return _load("sync_async_boundaries")


def load_read_model_catalog() -> dict[str, Any]:
    return _load("read_model_catalog")


def load_tenancy_modes() -> dict[str, Any]:
    return _load("tenancy_deployment_modes")


def load_agent_trust_policy() -> dict[str, Any]:
    return _load("agent_trust_policy")


def load_ide_product_boundary() -> dict[str, Any]:
    return _load("ide_product_boundary")


def load_admin_permission_matrix() -> dict[str, Any]:
    return _load("admin_permission_matrix")


def resolve_tenancy_mode(environ: dict[str, str] | None = None) -> str:
    env = environ if environ is not None else os.environ
    catalog = load_tenancy_modes()
    mode = str(env.get("ASTLOOM_TENANCY_MODE") or catalog.get("default_mode") or "shared_scoped").strip()
    modes = {m["mode_id"]: m for m in catalog.get("modes", [])}
    if mode not in modes:
        raise ArchitectureGovernanceError(f"unknown ASTLOOM_TENANCY_MODE={mode!r}")
    missing = [k for k in modes[mode].get("requires_env", []) if not str(env.get(k) or "").strip()]
    if missing:
        raise ArchitectureGovernanceError(
            f"tenancy mode {mode} missing required env: {', '.join(missing)}"
        )
    return mode


def _operation_row(operation_id: str) -> dict[str, Any]:
    catalog = load_sync_async_boundaries()
    for op in catalog.get("operations", []):
        if op.get("operation_id") == operation_id:
            return dict(op)
    raise ArchitectureGovernanceError(f"unknown operation: {operation_id}")


def operation_mode(operation_id: str) -> str:
    return str(_operation_row(operation_id).get("mode") or "sync")


def retry_policy(operation_id: str | None = None) -> dict[str, Any]:
    """Return retry defaults from sync-async catalog (per-op override optional later)."""
    catalog = load_sync_async_boundaries()
    base = dict(catalog.get("default_retry") or {"max_attempts": 3, "backoff_seconds": [1, 5, 30]})
    if operation_id:
        row = _operation_row(operation_id)
        if isinstance(row.get("retry"), dict):
            base.update(row["retry"])
    return base


def timeout_seconds(operation_id: str) -> int:
    catalog = load_sync_async_boundaries()
    row = _operation_row(operation_id)
    if row.get("timeout_seconds") is not None:
        return int(row["timeout_seconds"])
    defaults = catalog.get("default_timeout_seconds") or {}
    mode = str(row.get("mode") or "sync")
    return int(defaults.get(mode) or (30 if mode == "sync" else 600))


def read_model(read_model_id: str) -> dict[str, Any]:
    catalog = load_read_model_catalog()
    for item in catalog.get("read_models", []):
        if item.get("read_model_id") == read_model_id:
            return dict(item)
    raise ArchitectureGovernanceError(f"unknown read model: {read_model_id}")


def trust_rank(level: str) -> int:
    policy = load_agent_trust_policy()
    levels = list(policy.get("levels") or [])
    if level not in levels:
        raise ArchitectureGovernanceError(f"unknown trust level: {level}")
    return levels.index(level)


def provider_rank(provider_or_level: str) -> int:
    """Rank providers / trust labels from agent-trust-policy provider_rank map."""
    policy = load_agent_trust_policy()
    ranks = dict(policy.get("provider_rank") or {})
    key = str(provider_or_level or "").strip().lower()
    if key not in ranks:
        raise ArchitectureGovernanceError(f"unknown provider_rank key: {provider_or_level}")
    return int(ranks[key])


def apply_trust_transition(
    current: str,
    *,
    successes: int = 0,
    failures: int = 0,
    revoke: bool = False,
) -> str:
    policy = load_agent_trust_policy()
    if revoke:
        return "untrusted"
    level = current if current in policy.get("levels", []) else policy.get("default_level", "standard")
    earn = policy.get("earn") or {}
    demote = policy.get("demote") or {}
    if failures >= int(demote.get("failed_tasks") or 3):
        return str(demote.get("demote_to") or "untrusted")
    if successes >= int(earn.get("successful_tasks") or 5):
        return str(earn.get("promote_to") or "elevated")
    return str(level)


def trust_allows_high_risk(level: str) -> bool:
    policy = load_agent_trust_policy()
    return trust_rank(level) >= trust_rank(str(policy.get("high_risk_min_level") or "elevated"))


def admin_action_allowed(
    action_id: str,
    *,
    roles: list[str],
    permissions: list[str],
) -> bool:
    matrix = load_admin_permission_matrix()
    role_set = {str(r) for r in roles}
    perm_set = {str(p) for p in permissions}
    if "admin" in role_set:
        return True
    for row in matrix.get("actions", []):
        if row.get("action_id") != action_id:
            continue
        if role_set & set(row.get("roles_any") or []):
            return True
        if perm_set & set(row.get("permissions_any") or []):
            return True
        return False
    raise ArchitectureGovernanceError(f"unknown admin action: {action_id}")


def guidance_resolve_required(environ: dict[str, str] | None = None) -> bool:
    env = environ if environ is not None else os.environ
    raw = str(env.get("ASTLOOM_GUIDANCE_RESOLVE_REQUIRED", "")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def surface_for_action(action_id: str) -> list[str]:
    catalog = load_ide_product_boundary()
    for row in catalog.get("actions", []):
        if row.get("action_id") == action_id:
            return list(row.get("surfaces") or [])
    raise ArchitectureGovernanceError(f"unknown boundary action: {action_id}")


def forbidden_persistence_violations(service_dir: Path, from_service: str) -> list[str]:
    """Scan service sources for banned cross-service postgres_store imports."""
    catalog = load_bounded_context_map()
    banned = [
        rule["must_not_import"]
        for rule in catalog.get("forbidden_persistence_imports", [])
        if rule.get("from_service") == from_service
    ]
    if not banned or not service_dir.is_dir():
        return []
    hits: list[str] = []
    for path in service_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for needle in banned:
            if needle in text:
                hits.append(f"{path}: {needle}")
    return hits

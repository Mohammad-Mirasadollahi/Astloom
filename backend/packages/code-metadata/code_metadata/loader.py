from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_PROFILE_PATH = (
    Path(__file__).resolve().parents[3] / "configs" / "code-metadata-profiles" / "default.json"
)

REQUIRED_RANKING_WEIGHTS = (
    "symbol_relevance",
    "graph_proximity",
    "documentation_freshness",
    "ownership",
    "call_frequency",
    "test_coverage",
    "risk",
)


class CodeMetadataError(ValueError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CodeMetadataError(f"profile missing: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CodeMetadataError(f"profile must be an object: {path}")
    return data


def load_profile(path: Path | None = None) -> dict[str, Any]:
    return _load_json(path or DEFAULT_PROFILE_PATH)


def validate_profile(profile: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("profile_id", "version"):
        if not str(profile.get(field) or "").strip():
            errors.append(f"missing {field}")

    thresholds = profile.get("freshness_thresholds")
    if not isinstance(thresholds, dict):
        errors.append("freshness_thresholds object is required")
    elif not isinstance(thresholds.get("default_max_age_hours"), (int, float)):
        errors.append("freshness_thresholds.default_max_age_hours must be a number")

    weights = profile.get("ranking_weights")
    if not isinstance(weights, dict) or not weights:
        errors.append("ranking_weights map is required")
    else:
        for key in REQUIRED_RANKING_WEIGHTS:
            value = weights.get(key)
            if not isinstance(value, (int, float)):
                errors.append(f"ranking_weights.{key} must be a number")
        total = sum(float(weights.get(k, 0) or 0) for k in REQUIRED_RANKING_WEIGHTS)
        if abs(total - 1.0) > 0.001:
            errors.append(f"ranking_weights must sum to 1.0, got {total}")

    escalation = profile.get("source_read_escalation")
    if not isinstance(escalation, dict):
        errors.append("source_read_escalation object is required")
    else:
        if not isinstance(escalation.get("min_confidence"), (int, float)):
            errors.append("source_read_escalation.min_confidence must be a number")
        for flag in ("escalate_on_stale", "escalate_on_high_risk"):
            if flag in escalation and not isinstance(escalation.get(flag), bool):
                errors.append(f"source_read_escalation.{flag} must be a boolean")

    budget = profile.get("token_budget")
    if not isinstance(budget, dict) or not isinstance(budget.get("context_pack_max"), int):
        errors.append("token_budget.context_pack_max must be an integer")
    elif budget["context_pack_max"] < 1:
        errors.append("token_budget.context_pack_max must be >= 1")

    return errors


def should_escalate_to_source(
    *,
    freshness_status: str,
    confidence_score: float,
    risk_tags: list[str] | None,
    profile: dict[str, Any],
) -> bool:
    """Return True when the profile says agents should read source instead of metadata only."""
    escalation = profile.get("source_read_escalation") or {}
    min_confidence = float(escalation.get("min_confidence") or 0.0)
    if confidence_score < min_confidence:
        return True
    if escalation.get("escalate_on_stale") and str(freshness_status).upper() != "CURRENT":
        return True
    high_risk = {
        "security",
        "authz",
        "authn",
        "persistence",
        "migration",
        "billing",
        "deployment",
        "secrets",
        "concurrency",
        "destructive",
    }
    tags = {str(tag).lower() for tag in (risk_tags or [])}
    if escalation.get("escalate_on_high_risk") and tags & high_risk:
        return True
    return False

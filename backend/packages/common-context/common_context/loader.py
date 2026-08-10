from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_PROFILE_PATH = (
    Path(__file__).resolve().parents[3] / "configs" / "common-context-profiles" / "default.json"
)

REQUIRED_WEIGHTS = (
    "frequency",
    "recency",
    "confidence",
    "user_pinning",
    "task_similarity",
    "project_relevance",
    "effectiveness",
)


class CommonContextError(ValueError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CommonContextError(f"profile missing: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CommonContextError(f"profile must be an object: {path}")
    return data


def load_profile(path: Path | None = None) -> dict[str, Any]:
    return _load_json(path or DEFAULT_PROFILE_PATH)


def validate_profile(profile: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("profile_id", "version"):
        if not str(profile.get(field) or "").strip():
            errors.append(f"missing {field}")

    weights = profile.get("weights")
    if not isinstance(weights, dict) or not weights:
        errors.append("weights map is required")
    else:
        for key in REQUIRED_WEIGHTS:
            value = weights.get(key)
            if not isinstance(value, (int, float)):
                errors.append(f"weights.{key} must be a number")
        total = sum(float(weights.get(k, 0) or 0) for k in REQUIRED_WEIGHTS)
        if abs(total - 1.0) > 0.001:
            errors.append(f"weights must sum to 1.0, got {total}")

    budget = profile.get("default_token_budget")
    if not isinstance(budget, int) or budget < 1:
        errors.append("default_token_budget must be a positive integer")

    if "approval_required" in profile and not isinstance(profile.get("approval_required"), bool):
        errors.append("approval_required must be a boolean")

    return errors

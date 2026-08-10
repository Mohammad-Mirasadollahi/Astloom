"""WeightProfile governance: catalog load, validate, activate, rollback."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


_CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs" / "weight-profiles"
_REQUIRED_WEIGHTS = (
    "semantic_weight",
    "episodic_weight",
    "working_weight",
    "evidence_weight",
    "recency_weight",
)
_REQUIRED_THRESHOLDS = ("min_relevance_score", "context_token_budget")


class WeightProfileError(ValueError):
    """Invalid weight profile or governance transition."""


def _catalog_dir() -> Path:
    override = os.environ.get("ASTLOOM_WEIGHT_PROFILES_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return _CONFIG_DIR


def _governance_path(state_root: Path) -> Path:
    return state_root / "weight-profile-governance.json"


def list_profiles(directory: Path | None = None) -> list[str]:
    root = directory or _catalog_dir()
    if not root.is_dir():
        return []
    return sorted(
        path.stem
        for path in root.glob("*.json")
        if not path.name.endswith(".schema.json") and path.name != "weight-profile.schema.json"
    )


def load_profile(profile_id: str, directory: Path | None = None) -> dict[str, Any]:
    root = directory or _catalog_dir()
    path = root / f"{profile_id}.json"
    if not path.is_file():
        raise WeightProfileError(f"weight profile not found: {profile_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise WeightProfileError(f"invalid weight profile: {path}")
    validate_profile(data)
    return data


def validate_profile(data: dict[str, Any]) -> list[str]:
    """Return empty list when valid; raise WeightProfileError on hard failures."""
    errors: list[str] = []
    for field in ("profile_id", "version", "owner", "status", "feature_weights", "thresholds"):
        if field not in data:
            errors.append(f"missing {field}")
    weights = data.get("feature_weights")
    if not isinstance(weights, dict):
        errors.append("feature_weights must be an object")
    else:
        for key in _REQUIRED_WEIGHTS:
            if key not in weights:
                errors.append(f"missing feature_weights.{key}")
            elif not isinstance(weights[key], (int, float)) or float(weights[key]) < 0:
                errors.append(f"feature_weights.{key} must be >= 0")
    thresholds = data.get("thresholds")
    if not isinstance(thresholds, dict):
        errors.append("thresholds must be an object")
    else:
        for key in _REQUIRED_THRESHOLDS:
            if key not in thresholds:
                errors.append(f"missing thresholds.{key}")
    status = str(data.get("status") or "")
    if status and status not in {"draft", "active", "retired"}:
        errors.append(f"invalid status: {status}")
    if errors:
        raise WeightProfileError("; ".join(errors))
    return []


def _load_governance(state_root: Path) -> dict[str, Any]:
    path = _governance_path(state_root)
    if not path.is_file():
        return {"active_profile_id": "default-memory-profile", "history": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise WeightProfileError(f"invalid governance state: {path}")
    data.setdefault("active_profile_id", "default-memory-profile")
    data.setdefault("history", [])
    return data


def _save_governance(state_root: Path, data: dict[str, Any]) -> Path:
    path = _governance_path(state_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def get_active_profile_id(
    state_root: Path | None = None,
    *,
    project_state: dict[str, Any] | None = None,
    env: dict[str, str] | None = None,
) -> str:
    environ = env if env is not None else os.environ
    env_id = str(environ.get("ASTLOOM_WEIGHT_PROFILE", "")).strip()
    if env_id:
        return env_id
    if project_state and project_state.get("weight_profile"):
        return str(project_state["weight_profile"]).strip()
    if state_root is not None:
        return str(_load_governance(state_root).get("active_profile_id") or "default-memory-profile")
    return "default-memory-profile"


def activate_profile(
    state_root: Path,
    profile_id: str,
    *,
    actor: str,
    reason: str,
    now_iso: str,
    require_approval: bool = True,
    directory: Path | None = None,
    roles: list[str] | None = None,
    permissions: list[str] | None = None,
) -> dict[str, Any]:
    role_list = list(roles or [])
    perm_list = list(permissions or [])
    enforce = str(os.environ.get("ASTLOOM_ENFORCE_ADMIN_MATRIX", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if enforce or role_list or perm_list:
        try:
            from architecture_governance import admin_action_allowed

            if not admin_action_allowed(
                "weight_profile.change",
                roles=role_list,
                permissions=perm_list,
            ):
                raise WeightProfileError("weight_profile.change denied by admin permission matrix")
        except ImportError as exc:
            raise WeightProfileError(
                "weight_profile.change requires architecture_governance when "
                "ASTLOOM_ENFORCE_ADMIN_MATRIX is enabled or actor roles/permissions "
                "are supplied"
            ) from exc
    profile = load_profile(profile_id, directory=directory)
    if profile.get("status") == "retired":
        raise WeightProfileError(f"cannot activate retired profile: {profile_id}")
    if require_approval and not str(profile.get("approved_by") or "").strip():
        raise WeightProfileError(f"profile {profile_id} missing approved_by")
    gov = _load_governance(state_root)
    previous = str(gov.get("active_profile_id") or "default-memory-profile")
    if previous == profile_id:
        # Idempotent: do not append no-op history that would break rollback.
        return {
            "active_profile_id": profile_id,
            "previous_profile_id": previous,
            "entry": None,
            "profile": profile,
            "unchanged": True,
        }
    entry = {
        "at": now_iso,
        "actor": actor,
        "reason": reason,
        "from_profile_id": previous,
        "to_profile_id": profile_id,
        "to_version": int(profile.get("version") or 1),
    }
    history = list(gov.get("history") or [])
    history.append(entry)
    gov["active_profile_id"] = profile_id
    gov["history"] = history
    gov["updated_at"] = now_iso
    gov["updated_by"] = actor
    _save_governance(state_root, gov)
    return {"active_profile_id": profile_id, "previous_profile_id": previous, "entry": entry, "profile": profile}


def rollback_profile(
    state_root: Path,
    *,
    actor: str,
    reason: str,
    now_iso: str,
    steps: int = 1,
    directory: Path | None = None,
) -> dict[str, Any]:
    if steps < 1:
        raise WeightProfileError("steps must be >= 1")
    gov = _load_governance(state_root)
    history = list(gov.get("history") or [])
    # Drop accidental no-op entries (same from/to) so rollback always moves.
    while history and str(history[-1].get("from_profile_id") or "") == str(
        history[-1].get("to_profile_id") or ""
    ):
        history.pop()
    if not history:
        raise WeightProfileError("no activation history to roll back")
    if steps > len(history):
        raise WeightProfileError(f"steps={steps} exceeds history length={len(history)}")
    target_entry = history[-steps]
    target_id = str(target_entry.get("from_profile_id") or "default-memory-profile")
    gov["history"] = history[:-steps]
    profile = load_profile(target_id, directory=directory)
    previous = str(gov.get("active_profile_id") or "")
    gov["active_profile_id"] = target_id
    gov["updated_at"] = now_iso
    gov["updated_by"] = actor
    rollback_entry = {
        "at": now_iso,
        "actor": actor,
        "reason": reason or "rollback",
        "from_profile_id": previous,
        "to_profile_id": target_id,
        "to_version": int(profile.get("version") or 1),
        "rollback": True,
    }
    gov.setdefault("rollback_log", []).append(rollback_entry)
    _save_governance(state_root, gov)
    return {
        "active_profile_id": target_id,
        "previous_profile_id": previous,
        "entry": rollback_entry,
        "profile": profile,
    }

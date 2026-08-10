from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONFIGS = Path(__file__).resolve().parents[3] / "configs"
TECHNOLOGY_PROFILE_PATH = CONFIGS / "technology-profiles" / "default.json"
ENVIRONMENTS_DIR = CONFIGS / "environments"

REQUIRED_STORE_ROLES = {
    "postgresql": "operational",
    "pgvector": "rag",
    "neo4j": "code_graph",
    "redis": "ephemeral_cache",
}

REQUIRED_RUNTIME_FIELDS = (
    "venv_path",
    "compose_profiles",
    "port_profile",
    "install_python_dependencies",
    "start_infrastructure_with_docker",
)

REQUIRED_ENV_FIELDS = (
    "environment",
    "version",
    "technology_profile",
    "port_profile",
    "feature_profile",
)


class ConfigError(ValueError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"config missing: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ConfigError(f"config must be an object: {path}")
    return data


def load_technology_profile(path: Path | None = None) -> dict[str, Any]:
    return _load_json(path or TECHNOLOGY_PROFILE_PATH)


def load_environment_profile(name: str, *, root: Path | None = None) -> dict[str, Any]:
    base = root or ENVIRONMENTS_DIR
    return _load_json(base / name / "profile.json")


def validate_technology_profile(profile: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("profile_id", "version"):
        if not str(profile.get(field) or "").strip():
            errors.append(f"missing {field}")
    runtime = profile.get("runtime")
    if not isinstance(runtime, dict):
        errors.append("runtime object is required")
    else:
        for field in REQUIRED_RUNTIME_FIELDS:
            if field not in runtime:
                errors.append(f"runtime missing {field}")
        profiles = runtime.get("compose_profiles")
        if "compose_profiles" in runtime and (
            not isinstance(profiles, list) or not profiles
        ):
            errors.append("runtime.compose_profiles must be a non-empty list")
    stores = profile.get("stores")
    if not isinstance(stores, dict) or not stores:
        errors.append("stores map is required")
    else:
        for name, expected_role in REQUIRED_STORE_ROLES.items():
            entry = stores.get(name)
            if not isinstance(entry, dict):
                errors.append(f"stores.{name} object is required")
                continue
            if entry.get("enabled") is not True:
                errors.append(f"stores.{name}.enabled must be true in default profile")
            if str(entry.get("role") or "") != expected_role:
                errors.append(f"stores.{name}.role must be {expected_role}")
    return errors


def validate_environment_profile(profile: dict[str, Any], *, expected_name: str | None = None) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_ENV_FIELDS:
        if not str(profile.get(field) or "").strip():
            errors.append(f"missing {field}")
    if expected_name is not None and str(profile.get("environment") or "") != expected_name:
        errors.append(f"environment must be {expected_name}")
    if "debug" in profile and not isinstance(profile.get("debug"), bool):
        errors.append("debug must be a boolean")
    return errors

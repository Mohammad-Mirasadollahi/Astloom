"""ModelRoutingProfile resolution for LiteLLM task/risk → model aliases."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RouteDecision:
    """Resolved LiteLLM route for one task class."""

    profile_id: str
    task_class: str
    risk_level: str
    primary_model: str
    fallback_models: tuple[str, ...]
    max_tokens: int | None
    json_mode: bool
    allow_stub: bool

    def models_in_order(self) -> tuple[str, ...]:
        models: list[str] = []
        if self.primary_model.strip():
            models.append(self.primary_model.strip())
        for item in self.fallback_models:
            alias = item.strip()
            if alias and alias not in models:
                models.append(alias)
        return tuple(models)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "task_class": self.task_class,
            "risk_level": self.risk_level,
            "primary_model": self.primary_model,
            "fallback_models": list(self.fallback_models),
            "max_tokens": self.max_tokens,
            "json_mode": self.json_mode,
            "allow_stub": self.allow_stub,
        }


_TASK_ENV = {
    "docs.generate": "ASTLOOM_LITELLM_MODEL_DOCS",
    "rules.judge": "ASTLOOM_LITELLM_MODEL_JUDGE",
    "codegen.synthesize": "ASTLOOM_LITELLM_MODEL_CODEGEN",
    "embed.symbol": "ASTLOOM_LITELLM_MODEL_EMBED",
}

_MODEL_ROUTING_DIR = Path(__file__).resolve().parents[2] / "configs" / "model-routing"
_PROFILE_CACHE: dict[str, dict[str, Any]] = {}


def _parse_fallbacks(raw: str) -> tuple[str, ...]:
    parts = [p.strip() for p in raw.replace(";", ",").split(",")]
    return tuple(p for p in parts if p)


def _profile_path() -> Path:
    override = os.environ.get("ASTLOOM_LITELLM_ROUTING_PROFILE", "").strip()
    if override:
        path = Path(override).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        return path
    env_name = os.environ.get("ASTLOOM_LITELLM_ROUTING_ENV", "local").strip().lower() or "local"
    if env_name == "cloud":
        return _MODEL_ROUTING_DIR / "cloud.json"
    return _MODEL_ROUTING_DIR / "default.json"


def load_routing_profile(path: Path | None = None) -> dict[str, Any]:
    """Load a ModelRoutingProfile JSON document (cached by resolved path)."""
    resolved = (path or _profile_path()).resolve()
    key = str(resolved)
    cached = _PROFILE_CACHE.get(key)
    if cached is not None:
        return cached
    if not resolved.is_file():
        empty: dict[str, Any] = {
            "profile_id": "missing-profile",
            "version": "0.0.0",
            "title": "Missing",
            "environment": "local",
            "routes": [],
        }
        _PROFILE_CACHE[key] = empty
        return empty
    data = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"ModelRoutingProfile must be an object: {resolved}")
    _PROFILE_CACHE[key] = data
    return data


def clear_routing_profile_cache() -> None:
    """Test helper: drop cached profile documents."""
    _PROFILE_CACHE.clear()


def _route_from_profile(
    profile: dict[str, Any],
    *,
    task_class: str,
    risk_level: str,
) -> dict[str, Any] | None:
    routes = profile.get("routes") or []
    if not isinstance(routes, list):
        return None
    exact: dict[str, Any] | None = None
    low_fallback: dict[str, Any] | None = None
    for item in routes:
        if not isinstance(item, dict):
            continue
        if item.get("task_class") != task_class:
            continue
        if item.get("risk_level") == risk_level:
            exact = item
            break
        if item.get("risk_level") == "low":
            low_fallback = item
    return exact or low_fallback


def resolve_route(
    task_class: str,
    *,
    risk_level: str | None = None,
    default_model: str = "",
    profile_id: str | None = None,
) -> RouteDecision:
    """Resolve LiteLLM model aliases for a task class from env + profile defaults."""
    risk = (risk_level or os.environ.get("ASTLOOM_LITELLM_RISK_LEVEL", "low")).strip().lower() or "low"
    if risk not in {"low", "medium", "high"}:
        risk = "low"

    profile = load_routing_profile()
    route = _route_from_profile(profile, task_class=task_class, risk_level=risk) or {}

    env_key = _TASK_ENV.get(task_class, "")
    primary = (os.environ.get(env_key, "").strip() if env_key else "") or ""
    if not primary:
        primary = default_model.strip()
    if not primary:
        primary = str(route.get("primary_model") or "").strip()

    fallback_env = os.environ.get("ASTLOOM_LITELLM_FALLBACK_MODELS", "").strip()
    if fallback_env:
        fallbacks = _parse_fallbacks(fallback_env)
    else:
        raw_fallbacks = route.get("fallback_models") or []
        fallbacks = tuple(
            str(item).strip() for item in raw_fallbacks if str(item).strip()
        )

    allow_stub = bool(route.get("allow_stub", True))
    json_mode = bool(route.get("json_mode", task_class == "rules.judge"))
    max_tokens = route.get("max_tokens", 512 if task_class != "embed.symbol" else None)
    if max_tokens is not None:
        max_tokens = int(max_tokens)

    # Force stub-friendly behavior when no model is configured.
    if not primary:
        allow_stub = True

    return RouteDecision(
        profile_id=(
            profile_id
            or os.environ.get("ASTLOOM_LITELLM_PROFILE_ID", "").strip()
            or str(profile.get("profile_id") or "env-default")
        ),
        task_class=task_class,
        risk_level=risk,
        primary_model=primary,
        fallback_models=fallbacks,
        max_tokens=max_tokens,
        json_mode=json_mode,
        allow_stub=allow_stub,
    )


def docs_generation_enabled() -> bool:
    raw = os.environ.get("ASTLOOM_LITELLM_DOCS_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def embeddings_generation_enabled() -> bool:
    raw = os.environ.get("ASTLOOM_LITELLM_EMBEDDINGS_ENABLED", "false").strip().lower()
    return raw not in {"0", "false", "no", "off"}

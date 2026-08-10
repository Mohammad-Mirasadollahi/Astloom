"""Environment-driven LiteLLM gateway settings."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any


# Non-default host port (LiteLLM upstream often uses 4000 — forbidden in Astloom).
DEFAULT_LITELLM_PORT = 32400
DEFAULT_TIMEOUT_SECONDS = 180.0
DEFAULT_NUM_RETRIES = 3
DEFAULT_RPM = 30


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw not in {"0", "false", "no", "off"}


def _load_port_from_profile(default: int = DEFAULT_LITELLM_PORT) -> int:
    """Read ASTLOOM_LITELLM_PORT from the active port profile when present."""
    try:
        from port_profile.loader import load_profile

        profile = load_profile()
        ports = profile.get("ports") or {}
        value = ports.get("ASTLOOM_LITELLM_PORT")
        if isinstance(value, int) and 1024 < value < 65535:
            return value
    except Exception:
        pass
    # Fallback: optional JSON beside this package is not required.
    root = Path(__file__).resolve().parents[2] / "configs" / "port-profiles" / "astloom-dev.json"
    if root.is_file():
        try:
            import json

            data = json.loads(root.read_text(encoding="utf-8"))
            value = (data.get("ports") or {}).get("ASTLOOM_LITELLM_PORT")
            if isinstance(value, int) and 1024 < value < 65535:
                return value
        except Exception:
            pass
    return default


def resolve_api_base(
    *,
    override: str | None,
    host: str,
    port: int,
) -> str:
    """Return override when set; otherwise auto Base URL from host:port."""
    cleaned = (override or "").strip().rstrip("/")
    if cleaned:
        return cleaned
    return f"http://{host}:{port}"


def build_reasoning_payload(
    *,
    enabled: bool,
    effort: str = "",
) -> dict[str, Any] | None:
    """OpenRouter-style ``reasoning`` object, or None when disabled.

    Sent via LiteLLM ``extra_body`` so it is not stripped by ``drop_params``.
    Example: ``{"enabled": True}`` or ``{"enabled": True, "effort": "high"}``.
    """
    if not enabled:
        return None
    payload: dict[str, Any] = {"enabled": True}
    cleaned = (effort or "").strip()
    if cleaned:
        payload["effort"] = cleaned
    return payload


@dataclass(frozen=True)
class LlmGatewaySettings:
    """LiteLLM settings loaded from environment (all ASTLOOM_LITELLM_* / related)."""

    enabled: bool
    api_base: str
    api_base_override: str
    api_base_is_auto: bool
    api_key: str
    default_model: str
    timeout_seconds: float
    num_retries: int
    rpm: int
    host: str
    port: int
    drop_params: bool
    debug: bool
    reasoning_enabled: bool
    reasoning_effort: str

    def public_dict(self) -> dict[str, Any]:
        """Safe config view (no secrets)."""
        return {
            "enabled": self.enabled,
            "api_base": self.api_base,
            "api_base_is_auto": self.api_base_is_auto,
            "api_base_override_set": bool(self.api_base_override.strip()),
            "default_model": self.default_model,
            "timeout_seconds": self.timeout_seconds,
            "num_retries": self.num_retries,
            "rpm": self.rpm,
            "host": self.host,
            "port": self.port,
            "api_key_configured": bool(self.api_key.strip()),
            "drop_params": self.drop_params,
            "debug": self.debug,
            "reasoning_enabled": self.reasoning_enabled,
            "reasoning_effort": self.reasoning_effort,
        }

    def reasoning_payload(
        self,
        *,
        enabled_override: bool | None = None,
        effort_override: str | None = None,
    ) -> dict[str, Any] | None:
        """Resolve reasoning body for one completion (request override wins)."""
        enabled = self.reasoning_enabled if enabled_override is None else enabled_override
        effort = self.reasoning_effort if effort_override is None else (effort_override or "")
        return build_reasoning_payload(enabled=enabled, effort=effort)

    @classmethod
    def from_environment(cls) -> "LlmGatewaySettings":
        enabled = _env_bool("ASTLOOM_LITELLM_ENABLED", True)

        host = os.environ.get("ASTLOOM_LITELLM_HOST", "127.0.0.1").strip() or "127.0.0.1"
        port_raw = os.environ.get("ASTLOOM_LITELLM_PORT", "").strip()
        if port_raw:
            port = int(port_raw)
        else:
            port = _load_port_from_profile()

        override = os.environ.get("ASTLOOM_LITELLM_API_BASE", "").strip()
        # Also accept common LiteLLM/OpenAI-compatible alias.
        if not override:
            override = os.environ.get("LITELLM_API_BASE", "").strip()
        api_base = resolve_api_base(override=override, host=host, port=port)

        timeout_raw = os.environ.get("ASTLOOM_LITELLM_TIMEOUT_SECONDS", "").strip()
        timeout = float(timeout_raw) if timeout_raw else DEFAULT_TIMEOUT_SECONDS

        retries_raw = os.environ.get("ASTLOOM_LITELLM_NUM_RETRIES", "").strip()
        num_retries = int(retries_raw) if retries_raw else DEFAULT_NUM_RETRIES

        rpm_raw = os.environ.get("ASTLOOM_LITELLM_RPM", "").strip()
        rpm = int(rpm_raw) if rpm_raw else DEFAULT_RPM

        api_key = (
            os.environ.get("ASTLOOM_LITELLM_API_KEY", "").strip()
            or os.environ.get("LITELLM_API_KEY", "").strip()
            or os.environ.get("OPENROUTER_API_KEY", "").strip()
            or os.environ.get("OPENAI_API_KEY", "").strip()
        )
        default_model = os.environ.get("ASTLOOM_LITELLM_DEFAULT_MODEL", "").strip()
        drop_params = _env_bool("ASTLOOM_LITELLM_DROP_PARAMS", True)
        debug = _env_bool("ASTLOOM_LITELLM_DEBUG", False)
        reasoning_enabled = _env_bool("ASTLOOM_LITELLM_REASONING_ENABLED", False)
        reasoning_effort = os.environ.get("ASTLOOM_LITELLM_REASONING_EFFORT", "").strip()

        if timeout <= 0:
            raise RuntimeError("ASTLOOM_LITELLM_TIMEOUT_SECONDS must be > 0")
        if num_retries < 0:
            raise RuntimeError("ASTLOOM_LITELLM_NUM_RETRIES must be >= 0")
        if rpm < 1:
            raise RuntimeError("ASTLOOM_LITELLM_RPM must be >= 1")
        if not (1024 < port < 65535):
            raise RuntimeError("ASTLOOM_LITELLM_PORT must be in (1024, 65535)")

        return cls(
            enabled=enabled,
            api_base=api_base,
            api_base_override=override,
            api_base_is_auto=not bool(override),
            api_key=api_key,
            default_model=default_model,
            timeout_seconds=timeout,
            num_retries=num_retries,
            rpm=rpm,
            host=host,
            port=port,
            drop_params=drop_params,
            debug=debug,
            reasoning_enabled=reasoning_enabled,
            reasoning_effort=reasoning_effort,
        )

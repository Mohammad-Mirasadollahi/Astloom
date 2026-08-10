"""ApprovalModeProfile catalog + route decision (GAP-004)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MODES = frozenset({"manual", "auto_approve", "system_routed"})
_RISK_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}

_CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs" / "approval-modes"
_DEFAULT_HARD_BLOCKS = frozenset(
    {
        "secret.exposure",
        "authz.change",
        "tenant.boundary",
        "destructive.delete",
        "production.deploy",
        "compliance.gated",
    }
)


class ApprovalModesError(ValueError):
    """Invalid approval-mode profile or route input."""


@dataclass(frozen=True)
class RouteDecision:
    route: str  # auto | human
    mode_effective: str
    reason: str
    decision_source: str
    hard_block: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route,
            "mode_effective": self.mode_effective,
            "reason": self.reason,
            "decision_source": self.decision_source,
            "hard_block": self.hard_block,
        }


def _profile_dir() -> Path:
    override = os.environ.get("ASTLOOM_APPROVAL_MODES_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return _CONFIG_DIR


def list_mode_profiles(directory: Path | None = None) -> list[str]:
    root = directory or _profile_dir()
    if not root.is_dir():
        return []
    return sorted(
        path.stem
        for path in root.glob("*.json")
        if path.name != "approval-mode-profile.schema.json" and not path.name.endswith(".schema.json")
    )


def load_mode_profile(profile_id: str = "default", directory: Path | None = None) -> dict[str, Any]:
    root = directory or _profile_dir()
    path = root / f"{profile_id}.json"
    if not path.is_file() and profile_id == "default":
        path = root / "default.json"
    if not path.is_file():
        raise ApprovalModesError(f"approval mode profile not found: {profile_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ApprovalModesError(f"invalid approval mode profile: {path}")
    mode = str(data.get("mode") or "manual").strip()
    if mode not in MODES:
        raise ApprovalModesError(f"invalid mode {mode!r} in {path}")
    return data


def resolve_effective_mode(
    *,
    project_state: dict[str, Any] | None = None,
    env: dict[str, str] | None = None,
    directory: Path | None = None,
) -> dict[str, Any]:
    """Resolve effective ApprovalModeProfile (env → project → catalog default)."""
    environ = env if env is not None else os.environ
    env_mode = str(environ.get("ASTLOOM_APPROVAL_MODE", "")).strip()
    profile = load_mode_profile("default", directory=directory)
    if project_state and isinstance(project_state.get("approval_mode_profile"), dict):
        overlay = project_state["approval_mode_profile"]
        profile = {**profile, **overlay}
    elif project_state and project_state.get("approval_mode"):
        profile = {**profile, "mode": str(project_state["approval_mode"]).strip()}
    if env_mode:
        if env_mode not in MODES:
            raise ApprovalModesError(f"invalid ASTLOOM_APPROVAL_MODE={env_mode!r}")
        profile = {**profile, "mode": env_mode, "updated_by": "env"}
    mode = str(profile.get("mode") or "manual").strip()
    if mode not in MODES:
        mode = "manual"
        profile = {**profile, "mode": mode}
    return profile


def save_mode_override(project_state: dict[str, Any], mode: str, *, actor: str) -> dict[str, Any]:
    if mode not in MODES:
        raise ApprovalModesError(f"invalid mode: {mode}")
    from datetime import UTC, datetime

    stamp = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    project_state["approval_mode"] = mode
    project_state["approval_mode_profile"] = {
        "mode": mode,
        "updated_by": actor,
        "updated_at": stamp,
        "version": int((project_state.get("approval_mode_profile") or {}).get("version") or 0) + 1,
    }
    return project_state


def is_hard_block(subject_class: str, profile: dict[str, Any] | None = None) -> bool:
    classes = set(_DEFAULT_HARD_BLOCKS)
    if profile:
        for item in profile.get("hard_block_classes") or []:
            text = str(item).strip()
            if text:
                classes.add(text)
    return str(subject_class or "").strip() in classes


def decide_route(
    *,
    mode: str | None = None,
    subject_class: str = "",
    risk_level: str = "medium",
    profile: dict[str, Any] | None = None,
) -> RouteDecision:
    """Apply GAP-004 decision policy for one Accept gate."""
    effective_profile = profile or resolve_effective_mode()
    effective_mode = (mode or str(effective_profile.get("mode") or "manual")).strip()
    if effective_mode not in MODES:
        effective_mode = "manual"

    cls = str(subject_class or "").strip()
    if is_hard_block(cls, effective_profile):
        return RouteDecision(
            route="human",
            mode_effective=effective_mode,
            reason=f"hard-block class {cls}",
            decision_source="hard_block",
            hard_block=True,
        )

    if effective_mode == "manual":
        return RouteDecision(
            route="human",
            mode_effective=effective_mode,
            reason="mode=manual",
            decision_source="deterministic_policy",
        )

    if effective_mode == "auto_approve":
        denied = {str(x).strip() for x in (effective_profile.get("denied_auto_classes") or []) if str(x).strip()}
        if cls and cls in denied:
            return RouteDecision(
                route="human",
                mode_effective=effective_mode,
                reason=f"denied_auto_class {cls}",
                decision_source="deterministic_policy",
            )
        return RouteDecision(
            route="auto",
            mode_effective=effective_mode,
            reason="mode=auto_approve",
            decision_source="deterministic_policy",
        )

    # system_routed
    allowed = {str(x).strip() for x in (effective_profile.get("allowed_auto_classes") or []) if str(x).strip()}
    max_risk = str(effective_profile.get("max_auto_risk") or "medium").strip().lower() or "medium"
    risk = str(risk_level or "medium").strip().lower() or "medium"
    if cls and allowed and cls not in allowed:
        return RouteDecision(
            route="human",
            mode_effective=effective_mode,
            reason=f"class {cls} not in allowed_auto_classes",
            decision_source="deterministic_policy",
        )
    if _RISK_RANK.get(risk, 99) > _RISK_RANK.get(max_risk, 1):
        return RouteDecision(
            route="human",
            mode_effective=effective_mode,
            reason=f"risk {risk} exceeds max_auto_risk {max_risk}",
            decision_source="deterministic_policy",
        )
    return RouteDecision(
        route="auto",
        mode_effective=effective_mode,
        reason="system_routed eligible",
        decision_source="deterministic_policy",
    )

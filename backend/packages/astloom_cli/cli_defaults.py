"""Operator CLI defaults: env / connect.yaml / dogfood fallbacks."""

from __future__ import annotations

import os
from pathlib import Path

# Dogfood defaults when nothing else is configured (Astloom developing Astloom).
DEFAULT_TENANT = "astloom"
DEFAULT_WORKSPACE = "dev"


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            out[key] = value
    return out


def load_dotenv_files(*, root: Path | None = None) -> list[Path]:
    """Merge known env files into ``os.environ`` without overwriting existing keys.

    Source of truth: repository-root ``.env`` (template: ``.env.example``).

    Order (later files only fill missing keys — first wins after process env):
    process env already set > repo ``.env`` > repo ``.env.local`` > compose
    ``.env.local``.
    """
    from astloom_cli.util import repo_root

    base = root or repo_root()
    loaded: list[Path] = []
    candidates = [
        base / ".env",
        base / ".env.local",
        base / "backend" / "deployments" / "compose" / ".env.local",
    ]
    for path in candidates:
        values = _parse_env_file(path)
        if not values:
            continue
        loaded.append(path)
        for key, value in values.items():
            if key not in os.environ or not str(os.environ.get(key) or "").strip():
                os.environ[key] = value
    return loaded


def peek_connect_scope() -> dict[str, str]:
    """Read scope from checkout ``.astloom/connect.yaml`` if present (soft; never raises)."""
    try:
        from astloom_cli.connect_config import default_config_paths, _read_config_file
    except Exception:
        return {}
    for path in default_config_paths():
        if not path.is_file():
            continue
        try:
            doc = _read_config_file(path)
        except Exception:
            continue
        scope = doc.get("scope") if isinstance(doc, dict) else None
        if not isinstance(scope, dict):
            return {}
        return {
            "tenant": str(scope.get("tenant") or "").strip(),
            "workspace": str(scope.get("workspace") or "").strip(),
            "project": str(scope.get("project") or "").strip(),
        }
    return {}


def peek_identity_scope() -> dict[str, str]:
    try:
        from astloom_cli.identity import peek_identity
    except Exception:
        return {}
    data = peek_identity()
    return {
        "tenant": data.get("tenant", ""),
        "workspace": data.get("workspace", ""),
        "project": data.get("project", ""),
    }


def resolve_operator_scope(
    *,
    tenant: str = "",
    workspace: str = "",
    project: str = "",
    cwd: Path | None = None,
) -> tuple[str, str, str]:
    """Resolve tenant/workspace/project for everyday commands (sync/purge/status).

    Priority: CLI flag > env > identity.yaml > connect.yaml > dogfood defaults.
    """
    load_dotenv_files()
    work = cwd or Path.cwd()
    identity = peek_identity_scope()
    connect = peek_connect_scope()

    resolved_tenant = (
        (tenant or "").strip()
        or os.environ.get("ASTLOOM_TENANT_ID", "").strip()
        or os.environ.get("ASTLOOM_CONNECT_TENANT", "").strip()
        or identity.get("tenant", "")
        or connect.get("tenant", "")
        or DEFAULT_TENANT
    )
    resolved_workspace = (
        (workspace or "").strip()
        or os.environ.get("ASTLOOM_WORKSPACE_ID", "").strip()
        or os.environ.get("ASTLOOM_CONNECT_WORKSPACE", "").strip()
        or identity.get("workspace", "")
        or connect.get("workspace", "")
        or DEFAULT_WORKSPACE
    )
    resolved_project = (
        (project or "").strip()
        or os.environ.get("ASTLOOM_PROJECT_ID", "").strip()
        or os.environ.get("ASTLOOM_CONNECT_PROJECT", "").strip()
        or identity.get("project", "")
        or connect.get("project", "")
        or work.name
        or "project"
    )
    return resolved_tenant, resolved_workspace, resolved_project

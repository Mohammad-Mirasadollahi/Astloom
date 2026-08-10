"""Active operator identity (tenant / workspace / project) under checkout ``.astloom/``."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from astloom_cli.connect_security import harden_connect_config_permissions
from astloom_cli.util import now_iso

IDENTITY_FILENAME = "identity.yaml"


def identity_path() -> Path:
    """Prefer ``<repo>/.astloom/identity.yaml``; legacy ``~/.astloom/`` if present."""
    from astloom_cli.util import repo_root

    preferred = repo_root() / ".astloom" / IDENTITY_FILENAME
    if preferred.is_file():
        return preferred
    legacy = Path.home() / ".astloom" / IDENTITY_FILENAME
    if legacy.is_file():
        return legacy
    return preferred


def slugify(raw: str, *, fallback: str = "user") -> str:
    text = (raw or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if not text:
        return fallback
    return text[:48]


def peek_identity() -> dict[str, str]:
    path = identity_path()
    if not path.is_file():
        return {}
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    if not isinstance(doc, dict):
        return {}
    scope = doc.get("scope") if isinstance(doc.get("scope"), dict) else doc
    return {
        "tenant": str(scope.get("tenant") or scope.get("tenant_id") or "").strip(),
        "workspace": str(scope.get("workspace") or scope.get("workspace_id") or "").strip(),
        "project": str(scope.get("project") or scope.get("project_id") or "").strip(),
        "display_name": str(doc.get("display_name") or "").strip(),
    }


def write_identity(
    *,
    tenant: str,
    workspace: str,
    project: str,
    display_name: str = "",
    paths: list[str] | None = None,
) -> Path:
    path = identity_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    doc: dict[str, Any] = {
        "display_name": display_name or tenant,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "scope": {
            "tenant": tenant,
            "workspace": workspace,
            "project": project,
        },
    }
    if paths is not None:
        doc["paths"] = list(paths)
    # Preserve created_at / paths if rewriting without new paths
    if path.is_file():
        try:
            old = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(old, dict):
                if old.get("created_at"):
                    doc["created_at"] = old["created_at"]
                if paths is None and isinstance(old.get("paths"), list):
                    doc["paths"] = old["paths"]
        except Exception:
            pass
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    harden_connect_config_permissions(path)
    return path


def merge_identity_into_connect_yaml(*, tenant: str, workspace: str, project: str) -> Path | None:
    """Update scope in checkout ``.astloom/connect.yaml`` when the file already exists."""
    from astloom_cli.connect_config import default_config_paths

    for path in default_config_paths():
        if not path.is_file():
            continue
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if not isinstance(doc, dict):
            continue
        scope = doc.get("scope") if isinstance(doc.get("scope"), dict) else {}
        scope = dict(scope)
        scope["tenant"] = tenant
        scope["workspace"] = workspace
        scope["project"] = project
        doc["scope"] = scope
        path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        harden_connect_config_permissions(path)
        return path
    return None


def write_repo_env_scope(
    root: Path,
    *,
    tenant: str,
    workspace: str,
    project: str,
    software_paths: list[str] | None = None,
) -> Path:
    """Upsert ASTLOOM_* scope keys into repo ``.env`` (create if missing)."""
    path = root / ".env"
    lines: list[str] = []
    if path.is_file():
        lines = path.read_text(encoding="utf-8").splitlines()
    keys = {
        "ASTLOOM_TENANT_ID": tenant,
        "ASTLOOM_WORKSPACE_ID": workspace,
        "ASTLOOM_PROJECT_ID": project,
    }
    if software_paths is not None:
        from astloom_cli.software_paths import ENV_KEY, format_paths_env

        keys[ENV_KEY] = format_paths_env(software_paths)
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            out.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in keys:
            out.append(f"{key}={keys[key]}")
            seen.add(key)
        else:
            out.append(line)
    for key, value in keys.items():
        if key not in seen:
            out.append(f"{key}={value}")
    if out and out[-1] != "":
        out.append("")
    path.write_text("\n".join(out), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def clear_identity_if_matches(*, tenant: str, workspace: str, project: str) -> bool:
    """Delete identity.yaml when it pins exactly this scope. Returns True if removed."""
    current = peek_identity()
    if not current:
        return False
    if (
        current.get("tenant") != tenant
        or current.get("workspace") != workspace
        or current.get("project") != project
    ):
        return False
    path = identity_path()
    if path.is_file():
        path.unlink()
        return True
    return False


def clear_connect_scope_if_matches(*, tenant: str, workspace: str, project: str) -> Path | None:
    """Clear connect.yaml scope when it matches; returns path if updated."""
    from astloom_cli.connect_config import default_config_paths

    for path in default_config_paths():
        if not path.is_file():
            continue
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if not isinstance(doc, dict):
            continue
        scope = doc.get("scope") if isinstance(doc.get("scope"), dict) else {}
        if not isinstance(scope, dict):
            continue
        if (
            str(scope.get("tenant") or "").strip() != tenant
            or str(scope.get("workspace") or "").strip() != workspace
            or str(scope.get("project") or "").strip() != project
        ):
            continue
        doc["scope"] = {}
        path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        harden_connect_config_permissions(path)
        return path
    return None


def clear_repo_env_scope_if_matches(
    root: Path,
    *,
    tenant: str,
    workspace: str,
    project: str,
) -> bool:
    """Remove ASTLOOM_* scope lines from `.env` when they match this scope."""
    path = root / ".env"
    if not path.is_file():
        return False
    lines = path.read_text(encoding="utf-8").splitlines()
    current: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        current[key.strip()] = value.strip()
    if (
        current.get("ASTLOOM_TENANT_ID") != tenant
        or current.get("ASTLOOM_WORKSPACE_ID") != workspace
        or current.get("ASTLOOM_PROJECT_ID") != project
    ):
        return False
    drop = {
        "ASTLOOM_TENANT_ID",
        "ASTLOOM_WORKSPACE_ID",
        "ASTLOOM_PROJECT_ID",
        "ASTLOOM_SOFTWARE_PATHS",
    }
    out = []
    changed = False
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in drop:
                changed = True
                continue
        out.append(line)
    if not changed:
        return False
    text = "\n".join(out)
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")
    return True

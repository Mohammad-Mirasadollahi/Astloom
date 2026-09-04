"""Pinned software roots (directories) for sync / ingest."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from astloom_cli import state
from astloom_cli.identity import (
    identity_path,
    peek_identity,
    write_identity,
    write_repo_env_scope,
)
from astloom_cli.util import now_iso, repo_root

ENV_KEY = "ASTLOOM_SOFTWARE_PATHS"
# Absolute paths; ``:`` separates entries (Linux). Do not put ``:`` inside a path.
_PATH_SEP = ":"


def format_paths_env(paths: list[str]) -> str:
    return _PATH_SEP.join(paths)


def normalize_software_paths(
    raws: list[str] | None,
    *,
    must_exist: bool = True,
) -> list[str]:
    """Resolve, validate, and dedupe directory paths (order preserved)."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in raws or []:
        text = str(raw or "").strip()
        if not text:
            continue
        path = Path(text).expanduser().resolve()
        if must_exist and not path.is_dir():
            raise SystemExit(f"error: software path is not a directory: {path}")
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def paths_from_env() -> list[str]:
    raw = os.environ.get(ENV_KEY, "").strip()
    if not raw:
        return []
    return normalize_software_paths(raw.split(_PATH_SEP), must_exist=False)


def peek_software_paths() -> list[str]:
    """Pinned roots: identity.yaml → env → active project JSON."""
    path = identity_path()
    if path.is_file():
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            doc = {}
        if isinstance(doc, dict):
            raw = doc.get("paths")
            if isinstance(raw, list) and raw:
                return normalize_software_paths([str(p) for p in raw], must_exist=False)
            if isinstance(raw, str) and raw.strip():
                return normalize_software_paths([raw], must_exist=False)

    from_env = paths_from_env()
    if from_env:
        return from_env

    identity = peek_identity()
    tenant = identity.get("tenant") or ""
    workspace = identity.get("workspace") or ""
    project = identity.get("project") or ""
    if tenant and workspace and project:
        proj = state.load_project(
            state.default_state_root(repo_root()),
            tenant,
            workspace,
            project,
        )
        if proj and isinstance(proj.get("paths"), list) and proj["paths"]:
            return normalize_software_paths([str(p) for p in proj["paths"]], must_exist=False)
    return []


def software_paths_for_project(
    tenant_id: str,
    workspace_id: str,
    project_id: str,
    *,
    must_exist: bool = False,
) -> list[str]:
    """Pinned roots for an MCP/project scope (project JSON only — not CLI identity)."""
    tenant = str(tenant_id or "").strip()
    workspace = str(workspace_id or "").strip()
    project = str(project_id or "").strip()
    if not tenant or not workspace or not project:
        return []
    proj = state.load_project(
        state.default_state_root(repo_root()),
        tenant,
        workspace,
        project,
    )
    if not proj or not isinstance(proj.get("paths"), list) or not proj["paths"]:
        return []
    return normalize_software_paths([str(p) for p in proj["paths"]], must_exist=must_exist)


def require_software_paths(*, cli_paths: list[str] | None = None) -> list[str]:
    """CLI ``--path`` overrides pins; otherwise require at least one pinned root."""
    if cli_paths:
        return normalize_software_paths(cli_paths, must_exist=True)
    pinned = normalize_software_paths(peek_software_paths(), must_exist=True)
    if pinned:
        return pinned
    raise SystemExit(
        "error: no software path configured\n"
        "  Set roots when you init (required):\n"
        "    astloom init --tenant … --workspace … --path /path/to/app\n"
        "  Or edit later:\n"
        "    astloom paths add /path/to/app\n"
        "    astloom paths list"
    )


def persist_software_paths(
    paths: list[str],
    *,
    tenant: str,
    workspace: str,
    project: str,
    display_name: str = "",
) -> list[str]:
    """Write paths into identity.yaml, project JSON, and repo ``.env``."""
    normalized = normalize_software_paths(paths, must_exist=True)
    if not normalized:
        raise SystemExit("error: at least one software path is required")

    write_identity(
        tenant=tenant,
        workspace=workspace,
        project=project,
        display_name=display_name,
        paths=normalized,
    )

    root = state.default_state_root(repo_root())
    existing = state.load_project(root, tenant, workspace, project) or {
        "tenant_id": tenant,
        "workspace_id": workspace,
        "project_id": project,
        "name": project,
        "created_at": now_iso(),
        "status": "active",
    }
    existing["paths"] = normalized
    existing["updated_at"] = now_iso()
    state.save_project(root, existing)

    write_repo_env_scope(
        repo_root(),
        tenant=tenant,
        workspace=workspace,
        project=project,
        software_paths=normalized,
    )
    os.environ[ENV_KEY] = format_paths_env(normalized)
    return normalized

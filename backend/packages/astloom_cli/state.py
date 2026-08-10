from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def default_state_root(repo_root: Path) -> Path:
    return repo_root / ".astloom" / "projects"


def project_path(root: Path, tenant_id: str, workspace_id: str, project_id: str) -> Path:
    return root / tenant_id / workspace_id / f"{project_id}.json"


def load_project(root: Path, tenant_id: str, workspace_id: str, project_id: str) -> dict[str, Any] | None:
    path = project_path(root, tenant_id, workspace_id, project_id)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"invalid project state: {path}")
    return data


def save_project(root: Path, project: dict[str, Any]) -> Path:
    path = project_path(
        root,
        str(project["tenant_id"]),
        str(project["workspace_id"]),
        str(project["project_id"]),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(project, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def delete_project(root: Path, tenant_id: str, workspace_id: str, project_id: str) -> bool:
    """Remove local project state file. Returns True if a file was deleted."""
    path = project_path(root, tenant_id, workspace_id, project_id)
    if not path.is_file():
        return False
    path.unlink()
    # Prune empty workspace / tenant dirs under the projects root.
    for parent in (path.parent, path.parent.parent):
        if parent == root or not parent.is_relative_to(root):
            break
        try:
            parent.rmdir()
        except OSError:
            break
    return True


def list_projects(root: Path) -> list[dict[str, Any]]:
    """Load all local project state files under ``.astloom/projects/``."""
    if not root.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(root.glob("*/*/*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        tenant = str(data.get("tenant_id") or path.parts[-3]).strip()
        workspace = str(data.get("workspace_id") or path.parts[-2]).strip()
        project_id = str(data.get("project_id") or path.stem).strip()
        items.append(
            {
                "tenant_id": tenant,
                "workspace_id": workspace,
                "project_id": project_id,
                "name": str(data.get("name") or project_id),
                "usage_profile": str(data.get("usage_profile") or ""),
                "domain_pack": str(data.get("domain_pack") or ""),
                "feature_profile": str(data.get("feature_profile") or ""),
                "status": str(data.get("status") or ""),
                "paths": [str(p) for p in (data.get("paths") or []) if str(p).strip()],
                "created_at": str(data.get("created_at") or ""),
                "updated_at": str(data.get("updated_at") or ""),
                "path": str(path),
            }
        )
    return items

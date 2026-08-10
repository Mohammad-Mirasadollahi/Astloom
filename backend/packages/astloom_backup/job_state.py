"""Persist last backup job summary for MCP status."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def job_path(repo_root: Path) -> Path:
    from astloom_cli.data_root import backup_dir

    return backup_dir(install_root=repo_root) / "last-job.json"


def write_job(repo_root: Path, payload: dict[str, Any]) -> Path:
    path = job_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def read_job(repo_root: Path) -> dict[str, Any] | None:
    path = job_path(repo_root)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None

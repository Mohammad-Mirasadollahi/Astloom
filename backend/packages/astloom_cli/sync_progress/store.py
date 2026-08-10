"""Sync progress snapshot file I/O."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from tempfile import mkstemp
from typing import Any

from astloom_cli.sync_progress.constants import PROGRESS_FILENAME
from astloom_cli.util import repo_root


def progress_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / ".astloom" / PROGRESS_FILENAME


def write_snapshot(progress_file: Path, snapshot: dict[str, Any]) -> None:
    fd, tmp_name = mkstemp(
        prefix=f".{progress_file.name}.",
        suffix=".tmp",
        dir=progress_file.parent,
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = -1
            handle.write(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        tmp.replace(progress_file)
    except BaseException:
        if fd >= 0:
            os.close(fd)
        tmp.unlink(missing_ok=True)
        raise


def clear_snapshot(progress_file: Path | None) -> None:
    if progress_file and progress_file.is_file():
        try:
            progress_file.unlink()
        except OSError:
            pass


def read_live_progress(*, max_age_sec: float = 30.0, root: Path | None = None) -> dict[str, Any] | None:
    """Return sync progress snapshot if a sync looks active."""
    path = progress_path(root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict) or not data.get("active"):
        return None
    updated = float(data.get("updated_at") or 0)
    if updated <= 0 or (time.time() - updated) > max_age_sec:
        return None
    pid = int(data.get("pid") or 0)
    if pid > 0:
        try:
            os.kill(pid, 0)
        except OSError:
            return None
    return data

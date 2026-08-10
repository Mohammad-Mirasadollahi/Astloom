"""Live disk snapshots for client content-push jobs (server operator CLI).

Role: best-effort write/read/list of per-job progress JSON under data-root.
SoT: ``{data_root}/run/client-sync-jobs/<job_id>.json`` (active jobs only in list).
Invariants: never store secrets or file bodies; writes must not break ingest;
  after ``clear_job_snapshot``, late progress writes must not recreate the file
  (cancel/disconnect race with stuck workers) unless ``status=registered`` reopens.
Allowed: omit stale/inactive from list; detail may report missing/stale.
Forbidden: failing ingest when snapshot I/O fails; cancelling jobs from this module.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from tempfile import mkstemp
from typing import Any

JOBS_SUBDIR = Path("run") / "client-sync-jobs"
DEFAULT_STALE_SEC = 60.0

# Process-local: after clear/cancel, block resurrect until a new ``registered`` write.
_closed_job_ids: set[str] = set()
_closed_lock = threading.Lock()


def _jobs_dir(*, data_root: Path | None = None, environ: dict[str, str] | None = None) -> Path:
    if data_root is not None:
        return Path(data_root).expanduser().resolve() / JOBS_SUBDIR
    env = environ if environ is not None else dict(os.environ)
    raw = str(env.get("ASTLOOM_DATA_ROOT") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve() / JOBS_SUBDIR
    # Last resort: cwd-relative (tests); production sets ASTLOOM_DATA_ROOT.
    return Path.cwd() / ".astloom" / "run" / "client-sync-jobs"


def job_snapshot_path(
    job_id: str,
    *,
    data_root: Path | None = None,
    environ: dict[str, str] | None = None,
) -> Path:
    jid = str(job_id or "").strip()
    if not jid or len(jid) > 128:
        raise ValueError("job_id is required (1..128 chars)")
    # Path-safe: reject separators
    if "/" in jid or "\\" in jid or jid in {".", ".."}:
        raise ValueError("job_id must not contain path separators")
    return _jobs_dir(data_root=data_root, environ=environ) / f"{jid}.json"


def write_job_snapshot(
    job_id: str,
    patch: dict[str, Any],
    *,
    data_root: Path | None = None,
    environ: dict[str, str] | None = None,
    tenant_id: str = "",
    workspace_id: str = "",
    project_id: str = "",
) -> Path | None:
    """Merge ``patch`` into the job snapshot. Returns path or None on failure."""
    try:
        path = job_snapshot_path(job_id, data_root=data_root, environ=environ)
    except ValueError:
        return None
    jid = str(job_id).strip()
    reopen = str(patch.get("status") or "") == "registered"
    with _closed_lock:
        if jid in _closed_job_ids and not reopen:
            return None
        if reopen:
            _closed_job_ids.discard(jid)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        existing: dict[str, Any] = {}
        if path.is_file():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    existing = loaded
            except (OSError, json.JSONDecodeError):
                existing = {}
        # Closed on disk (active=false) without process memory: do not revive via progress.
        if existing and not bool(existing.get("active", True)) and not reopen:
            return None
        now = time.time()
        snap = {
            **existing,
            **{k: v for k, v in patch.items() if k != "source"},
            "job_id": jid,
            "active": bool(patch.get("active", existing.get("active", True))),
            "updated_at": now,
        }
        if "started_at" not in snap:
            snap["started_at"] = float(existing.get("started_at") or now)
        if tenant_id:
            snap["tenant_id"] = tenant_id
        if workspace_id:
            snap["workspace_id"] = workspace_id
        if project_id:
            snap["project_id"] = project_id
        fd, tmp_name = mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                fd = -1
                handle.write(json.dumps(snap, indent=2, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            tmp.replace(path)
        except BaseException:
            if fd >= 0:
                os.close(fd)
            tmp.unlink(missing_ok=True)
            raise
        return path
    except OSError:
        return None


def clear_job_snapshot(
    job_id: str,
    *,
    data_root: Path | None = None,
    environ: dict[str, str] | None = None,
) -> None:
    try:
        path = job_snapshot_path(job_id, data_root=data_root, environ=environ)
    except ValueError:
        return
    jid = str(job_id).strip()
    with _closed_lock:
        _closed_job_ids.add(jid)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def read_job_snapshot(
    job_id: str,
    *,
    data_root: Path | None = None,
    environ: dict[str, str] | None = None,
    max_age_sec: float = DEFAULT_STALE_SEC,
) -> dict[str, Any] | None:
    try:
        path = job_snapshot_path(job_id, data_root=data_root, environ=environ)
    except ValueError:
        return None
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    updated = float(data.get("updated_at") or 0)
    if max_age_sec > 0 and (time.time() - updated) > max_age_sec:
        data = {**data, "stale": True}
    return data


def list_live_job_snapshots(
    *,
    data_root: Path | None = None,
    environ: dict[str, str] | None = None,
    max_age_sec: float = DEFAULT_STALE_SEC,
) -> list[dict[str, Any]]:
    root = _jobs_dir(data_root=data_root, environ=environ)
    if not root.is_dir():
        return []
    out: list[dict[str, Any]] = []
    now = time.time()
    try:
        paths = sorted(root.glob("*.json"))
    except OSError:
        return []
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        if not data.get("active", True):
            continue
        updated = float(data.get("updated_at") or 0)
        if max_age_sec > 0 and (now - updated) > max_age_sec:
            continue
        out.append(data)
    out.sort(key=lambda d: float(d.get("updated_at") or 0), reverse=True)
    return out


__all__ = [
    "DEFAULT_STALE_SEC",
    "JOBS_SUBDIR",
    "clear_job_snapshot",
    "job_snapshot_path",
    "list_live_job_snapshots",
    "read_job_snapshot",
    "write_job_snapshot",
]

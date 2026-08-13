"""Server CLI: list/detail live client content-push sync jobs."""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Any

from astloom_cli import ui
from astloom_cli.data_root import default_data_root, resolve_data_root
from astloom_cli.service_runtime.paths import install_role
from astloom_cli.sync_progress.formatters import format_duration
from astloom_cli.util import print_json, repo_root


def _data_root_for_jobs() -> Path:
    return resolve_data_root(install_root=repo_root())


def _job_data_roots() -> list[Path]:
    """Install marker, env, and sibling ``<name>-data`` (HTTPS APIs may differ)."""
    root = repo_root()
    seen: set[Path] = set()
    out: list[Path] = []

    def add(raw: Path | str | None) -> None:
        if raw is None:
            return
        text = str(raw).strip()
        if not text:
            return
        try:
            path = Path(text).expanduser().resolve()
        except OSError:
            return
        if path in seen:
            return
        seen.add(path)
        out.append(path)

    add(_data_root_for_jobs())
    add(os.environ.get("ASTLOOM_DATA_ROOT"))
    add(default_data_root(root))
    add(root / ".astloom")
    return out


def _require_server_role() -> None:
    role = install_role(repo_root())
    if role == "client":
        raise SystemExit(
            "error: astloom sync jobs is server-only "
            "(client hosts use astloom-client sync progress instead)"
        )


def _graph_pid(root: Path) -> int | None:
    for name in ("code-graph-https.pid", "graph-https.pid"):
        path = root / ".astloom" / "run" / name
        try:
            raw = path.read_text(encoding="utf-8").strip()
            pid = int(raw.splitlines()[0].strip())
            if pid > 1:
                return pid
        except (OSError, ValueError, IndexError):
            continue
    return None


def _proc_resources(pid: int | None) -> dict[str, Any]:
    if pid is None:
        return {"pid": None, "cpu_percent": None, "rss_bytes": None}
    rss = None
    cpu = None
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        parts = stat.split()
        # utime + stime in clock ticks (fields 14,15 — 1-based → index 13,14)
        utime = int(parts[13])
        stime = int(parts[14])
        start = time.monotonic()
        ticks1 = utime + stime
        time.sleep(0.05)
        stat2 = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()
        ticks2 = int(stat2[13]) + int(stat2[14])
        elapsed = max(time.monotonic() - start, 1e-6)
        hz = os_clock_ticks()
        cpu = max(0.0, (ticks2 - ticks1) / hz / elapsed * 100.0)
    except (OSError, ValueError, IndexError):
        cpu = None
    try:
        status = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
        for line in status.splitlines():
            if line.startswith("VmRSS:"):
                # kB
                kb = int(line.split()[1])
                rss = kb * 1024
                break
    except (OSError, ValueError, IndexError):
        rss = None
    return {"pid": pid, "cpu_percent": None if cpu is None else round(cpu, 1), "rss_bytes": rss}


def os_clock_ticks() -> float:
    try:
        import os

        return float(os.sysconf("SC_CLK_TCK") or 100)
    except (ValueError, OSError, AttributeError):
        return 100.0


def _age_sec(snap: dict[str, Any]) -> float:
    started = float(snap.get("started_at") or snap.get("updated_at") or 0)
    if started <= 0:
        return 0.0
    return max(0.0, time.time() - started)


def _rate_eta(snap: dict[str, Any]) -> tuple[float | None, float | None]:
    done = int(snap.get("done") or 0)
    total = int(snap.get("total") or 0)
    age = _age_sec(snap)
    if age <= 0 or done <= 0:
        return None, None
    rate = done / age
    remaining = max(0, total - done)
    eta = (remaining / rate) if rate > 0 else None
    return rate, eta


def _scope_line(snap: dict[str, Any]) -> str:
    return (
        f"{snap.get('tenant_id') or '?'}/"
        f"{snap.get('workspace_id') or '?'}/"
        f"{snap.get('project_id') or '?'}"
    )


def cmd_sync_jobs(args: argparse.Namespace) -> int:
    _require_server_role()
    from code_graph_service.api.client_sync_job_snapshots import (
        list_live_job_snapshots,
        read_job_snapshot,
    )

    roots = _job_data_roots()
    data_root = roots[0] if roots else _data_root_for_jobs()
    job_id = str(getattr(args, "sync_job_id", None) or "").strip()
    as_json = bool(getattr(args, "json", False))

    if not job_id:
        by_id: dict[str, dict[str, Any]] = {}
        for root in roots:
            for snap in list_live_job_snapshots(data_root=root):
                jid = str(snap.get("job_id") or "").strip()
                if jid and jid not in by_id:
                    by_id[jid] = snap
        jobs = sorted(
            by_id.values(),
            key=lambda d: float(d.get("updated_at") or 0),
            reverse=True,
        )
        if as_json:
            print_json({"jobs": jobs, "data_root": str(data_root)})
            return 0
        if not jobs:
            print("No live client sync jobs.")
            return 0
        ui.blank()
        print(
            f"{'JOB_ID':<38}  {'SCOPE':<28}  {'DONE/TOTAL':<12}  {'%':>6}  AGE"
        )
        for snap in jobs:
            done = int(snap.get("done") or 0)
            total = int(snap.get("total") or 0)
            pct = (100.0 * done / total) if total else 0.0
            print(
                f"{str(snap.get('job_id') or ''):<38}  "
                f"{_scope_line(snap):<28}  "
                f"{f'{done}/{total}':<12}  "
                f"{pct:5.1f}%  "
                f"{format_duration(_age_sec(snap))}"
            )
        ui.blank()
        print(ui.dim("Detail: astloom sync jobs <JOB_ID>"))
        return 0

    snap = None
    found_root = data_root
    for root in roots:
        snap = read_job_snapshot(job_id, data_root=root, max_age_sec=0)
        if snap is not None:
            found_root = root
            break
    if snap is None:
        raise SystemExit(f"error: no snapshot for job_id {job_id!r}")
    # Re-check staleness for messaging
    live = read_job_snapshot(job_id, data_root=found_root)
    stale = live is None or bool((live or {}).get("stale"))
    rate, eta = _rate_eta(snap)
    resources = _proc_resources(_graph_pid(repo_root()))
    payload = {
        **snap,
        "stale": stale,
        "age_sec": round(_age_sec(snap), 1),
        "files_per_sec": None if rate is None else round(rate, 3),
        "eta_sec": None if eta is None else round(eta, 1),
        "resources": resources,
    }
    if as_json:
        print_json(payload)
        return 0

    done = int(snap.get("done") or 0)
    total = int(snap.get("total") or 0)
    pct = (100.0 * done / total) if total else 0.0
    ui.blank()
    ui.heading("Client sync job")
    ui.kv("Job ID", str(snap.get("job_id") or job_id))
    ui.kv("Scope", _scope_line(snap))
    ui.kv("Phase", f"{snap.get('phase') or '?'} / {snap.get('status') or '?'}")
    ui.kv("Progress", f"{done}/{total} ({pct:.1f}%)")
    ui.kv("Age", format_duration(_age_sec(snap)))
    ui.kv("Rate", "…" if rate is None else f"{rate:.2f}/s")
    ui.kv("ETA", "…" if eta is None else format_duration(eta))
    ui.kv("Current file", str(snap.get("file") or "—"))
    workers = int(snap.get("file_workers") or 0)
    in_flight = int(snap.get("files_in_flight") or 0)
    ui.kv("Parallel", f"{in_flight} active / {workers or '?'} workers")
    paths = list(snap.get("files_in_flight_paths") or [])
    if paths:
        ui.kv("In-flight", ", ".join(str(p) for p in paths[:8]))
    ui.kv("Symbols", str(snap.get("symbols_indexed") or 0))
    ui.kv("Edges", str(snap.get("edges_written") or 0))
    rss = resources.get("rss_bytes")
    cpu = resources.get("cpu_percent")
    ui.kv(
        "Graph process",
        (
            f"pid={resources.get('pid') or 'n/a'}  "
            f"cpu={cpu if cpu is not None else 'n/a'}%  "
            f"rss={_fmt_bytes(rss) if rss is not None else 'n/a'}"
        ),
    )
    if stale:
        print(ui.warn("Snapshot looks stale (job may have finished)."))
    ui.blank()
    return 0


def _fmt_bytes(n: int) -> str:
    x = float(n)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if x < 1024 or unit == "GiB":
            return f"{x:.1f}{unit}" if unit != "B" else f"{int(x)}B"
        x /= 1024
    return f"{n}B"


__all__ = ["cmd_sync_jobs"]

"""Combined start/stop/restart/status and sync auto-start."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from astloom_cli.service_runtime.progress import progress


def service_state(compose: dict[str, Any], mcp: dict[str, Any]) -> str:
    """Human-readable overall state — names what is wrong, never vague labels."""
    compose_ok = bool(compose.get("ok"))
    mcp_ok = bool(mcp.get("ok"))
    mcp_running = bool(mcp.get("running"))
    mcp_reachable = bool(mcp.get("reachable"))
    if compose_ok and mcp_ok:
        return "all running"
    if not compose_ok and not mcp_running:
        return "stopped"
    if compose_ok and not mcp_running:
        return "MCP HTTP stopped"
    if compose_ok and mcp_running and not mcp_reachable:
        return "MCP HTTP not reachable"
    if not compose_ok and mcp_ok:
        return "Compose not healthy"
    return "not fully running"


def status_all(root: Path) -> dict[str, Any]:
    from astloom_cli import service_runtime as runtime
    from astloom_cli.cli_defaults import load_dotenv_files
    from astloom_cli.service_runtime.progress import stack_restarted_at, uptime_seconds_since

    load_dotenv_files(root=root)
    compose = runtime.compose_status(root)
    mcp = runtime.mcp_status(root)
    boot = runtime.boot_status(root)
    stamps: list[str | None] = [
        (info or {}).get("started_at")
        for info in (compose.get("services") or {}).values()
        if (info or {}).get("running")
    ]
    if mcp.get("running"):
        stamps.append(mcp.get("started_at"))
    restarted_at = stack_restarted_at(*stamps)
    out: dict[str, Any] = {
        "status": service_state(compose, mcp),
        "repo_root": str(root),
        "compose": compose,
        "mcp": mcp,
        "boot": boot,
    }
    if restarted_at:
        out["restarted_at"] = restarted_at
        uptime = uptime_seconds_since(restarted_at)
        if uptime is not None:
            out["uptime_sec"] = uptime
    return out


def start_all(root: Path, *, as_part_of: str | None = None) -> dict[str, Any]:
    from astloom_cli import service_runtime as runtime

    if as_part_of == "restart":
        progress("Restart: starting services")
    else:
        progress("Starting Astloom (databases, then MCP HTTP)")
    _run_port_preflight(root)
    compose = runtime.start_compose(root)
    mcp = runtime.start_mcp_http(root)
    ok = bool(compose.get("ok") and mcp.get("ok"))
    if ok:
        if as_part_of == "restart":
            progress("Restart: services are up")
        else:
            progress("Astloom is up")
    else:
        if as_part_of == "restart":
            progress("Restart: start finished with errors")
        else:
            progress("Start finished with errors — Astloom is not fully up")
    return {"ok": ok, "compose": compose, "mcp": mcp}


def _run_port_preflight(root: Path) -> None:
    """Block start when profile ports conflict with a foreign process."""
    from astloom_cli import service_runtime as runtime
    from port_profile import load_profile, run_preflight, write_port_map
    from port_profile.loader import DEFAULT_PORT_MAP_REL

    progress("Port preflight: checking profile ports")
    profile = load_profile()
    mcp_pid = runtime.read_mcp_pid(root)
    report = run_preflight(
        profile,
        allow_ours=True,
        allowed_pids={mcp_pid} if mcp_pid is not None else set(),
        repo_root=root,
    )
    map_path = write_port_map(root / DEFAULT_PORT_MAP_REL, report)
    if report["ok"]:
        progress(f"Port preflight: ok (map {map_path})")
        return
    conflicts = report.get("conflicts") or []
    details: list[str] = []
    for key in conflicts:
        info = (report.get("ports") or {}).get(key) or {}
        port = info.get("port")
        owner = info.get("owner") or {}
        suggest = info.get("suggested_port")
        who = f"{owner.get('name', '?')} pid={owner.get('pid', '?')}" if owner else "unknown process"
        line = f"{key}={port} in use by {who}"
        if suggest is not None:
            line += f"; try {key}={suggest}"
        details.append(line)
    raise SystemExit(
        "error: port preflight failed — free the ports or override ASTLOOM_*_PORT:\n  "
        + "\n  ".join(details)
        + f"\n  port map: {map_path}"
    )


def stop_all(root: Path, *, as_part_of: str | None = None) -> dict[str, Any]:
    from astloom_cli import service_runtime as runtime

    if as_part_of == "restart":
        progress("Restart: stopping services")
    else:
        progress("Stopping Astloom (MCP HTTP, then databases)")
    mcp = runtime.stop_mcp_http(root)
    compose = runtime.stop_compose(root)
    ok = bool(mcp.get("ok") and compose.get("ok"))
    if ok:
        if as_part_of == "restart":
            progress("Restart: services are stopped")
        else:
            progress("Astloom is stopped")
    else:
        if as_part_of == "restart":
            progress("Restart: stop finished with errors")
        else:
            progress("Stop finished with errors — Astloom may still be partly up")
    return {"ok": ok, "mcp": mcp, "compose": compose}


def restart_all(root: Path) -> dict[str, Any]:
    from astloom_cli import service_runtime as runtime

    progress("Restarting Astloom")
    stopped = runtime.stop_all(root, as_part_of="restart")
    started = runtime.start_all(root, as_part_of="restart")
    ok = bool(stopped.get("ok") and started.get("ok"))
    if ok:
        progress("Restart complete — Astloom is up")
    else:
        progress("Restart finished with errors — check astloom service status")
    return {"ok": ok, "stop": stopped, "start": started}


def _read_yes_no(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError as exc:
        raise SystemExit(
            "error: confirmation aborted (no input). Software was not started."
        ) from exc


def ensure_running_or_offer_start(
    root: Path,
    *,
    input_fn: Any | None = None,
    stdin_isatty: bool | None = None,
) -> dict[str, Any] | None:
    """If local software is down, ask to start it (TTY) or exit with a hint.

    Returns the ``start_all`` report when start ran; ``None`` when already up.
    Client / CLI-only checkouts (no Compose env) exit with a clear message —
    they cannot start a local stack.
    """
    from astloom_cli import service_runtime as runtime
    from astloom_cli.service_runtime.paths import (
        local_compose_stack_present,
        missing_local_stack_message,
    )

    if not local_compose_stack_present(root):
        raise SystemExit(missing_local_stack_message(root))

    report = runtime.status_all(root)
    if report.get("status") == "all running":
        return None

    state = str(report.get("status") or "not fully running")
    tty = sys.stdin.isatty() if stdin_isatty is None else bool(stdin_isatty)
    if not tty:
        raise SystemExit(
            f"error: software is not running ({state}). "
            "Start it with: astloom service start"
        )

    print()
    print(f"Software is not running ({state}).")
    print("Sync needs Compose (postgres/neo4j) and MCP HTTP.")
    answer = (input_fn or _read_yes_no)("Start software now? [y/N]: ").strip().lower()
    if answer not in {"y", "yes"}:
        raise SystemExit("error: sync cancelled (software not running)")

    progress("Astloom is not fully up — starting it before sync")
    started = runtime.start_all(root)
    after = runtime.status_all(root)
    if after.get("status") != "all running":
        raise SystemExit(
            f"error: software still not fully running after start "
            f"({after.get('status')}). Try: astloom service detail"
        )
    progress("Astloom is up — continuing sync")
    return started

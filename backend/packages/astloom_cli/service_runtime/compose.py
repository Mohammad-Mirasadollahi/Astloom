"""Docker Compose postgres/neo4j control."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from astloom_cli.service_runtime.paths import COMPOSE_SERVICES, compose_dir, compose_env_file, compose_file
from astloom_cli.service_runtime.progress import format_docker_started_at, progress, wall_clock_now

# Graceful stop wait (docker SIGTERM→SIGKILL). Hard ceiling for the CLI itself.
COMPOSE_STOP_TIMEOUT_SEC = 20
COMPOSE_STOP_WAIT_SEC = 45


def compose_base_cmd(root: Path) -> list[str]:
    from astloom_cli.service_runtime.paths import missing_local_stack_message

    env_file = compose_env_file(root)
    file = compose_file(root)
    if not file.is_file():
        raise SystemExit(f"error: missing compose file {file}")
    if not env_file.is_file():
        raise SystemExit(missing_local_stack_message(root))
    return [
        "docker",
        "compose",
        "--env-file",
        str(env_file),
        "-f",
        str(file),
    ]


def run_cmd(
    cmd: list[str],
    *,
    cwd: Path,
    check: bool = True,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        check=check,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def container_started_at(cid: str) -> str:
    inspect = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.StartedAt}}", cid],
        text=True,
        capture_output=True,
        check=False,
    )
    return format_docker_started_at((inspect.stdout or "").strip())


def start_compose(root: Path) -> dict[str, Any]:
    compose_started_at = wall_clock_now()
    services = ", ".join(COMPOSE_SERVICES)
    progress(f"Databases: starting {services}")

    from astloom_cli.data_root import ENV_DATA_ROOT, ensure_data_root
    from astloom_cli.data_root_migrate import migrate_named_volumes_to_data_root

    data_root = ensure_data_root(install_root=root)
    env_file = compose_env_file(root)
    if env_file.is_file():
        text = env_file.read_text(encoding="utf-8")
        line = f"{ENV_DATA_ROOT}={data_root}"
        if f"{ENV_DATA_ROOT}=" in text:
            import re

            text = re.sub(
                rf"^{ENV_DATA_ROOT}=.*$",
                line,
                text,
                count=1,
                flags=re.MULTILINE,
            )
        else:
            text = text.rstrip() + "\n" + line + "\n"
        env_file.write_text(text, encoding="utf-8")
    try:
        migrated = migrate_named_volumes_to_data_root(data_root)
    except RuntimeError as exc:
        raise SystemExit(f"error: {exc}") from exc
    if migrated:
        progress(f"Databases: migrated legacy volumes → {data_root} ({', '.join(migrated)})")

    cmd = compose_base_cmd(root) + ["--profile", "core", "up", "-d", *COMPOSE_SERVICES]
    proc = run_cmd(cmd, cwd=root, check=False)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise SystemExit(f"error: compose up failed: {err[:800]}")
    wait = compose_dir(root) / "wait-healthy.sh"
    names: list[str] = []
    service_started_at: dict[str, str] = {}
    for service in COMPOSE_SERVICES:
        cid = run_cmd(
            compose_base_cmd(root) + ["ps", "-q", service],
            cwd=root,
            check=False,
        )
        container_id = (cid.stdout or "").strip().splitlines()
        if container_id:
            names.append(container_id[0])
            service_started_at[service] = container_started_at(container_id[0])
            progress(f"Databases: {service} is up")
        else:
            service_started_at[service] = compose_started_at
            progress(f"Databases: {service} did not appear after start")
    if wait.is_file() and names:
        progress(
            "Databases: waiting until healthy (up to 5 minutes; "
            "neo4j may download plugins on first start)"
        )
        subprocess.run(
            ["bash", str(wait), "--timeout", "300", *names],
            cwd=str(root),
            check=False,
        )
        health = compose_status(root)
        for name, info in (health.get("services") or {}).items():
            state = str(info.get("health") or "unknown")
            if state == "healthy":
                progress(f"Databases: {name} is healthy")
            else:
                progress(f"Databases: {name} is {state}")
        if health.get("ok"):
            progress("Databases: ready")
        else:
            progress("Databases: started, but not all healthy yet")
    else:
        progress("Databases: start finished")
    return {
        "ok": True,
        "action": "compose_up",
        "started_at": compose_started_at,
        "services": list(COMPOSE_SERVICES),
        "service_started_at": service_started_at,
    }


def stop_mcp_gateway(root: Path) -> dict[str, Any]:
    """Stop Compose mcp-gateway so host MCP HTTP can bind the shared port.

    Host runtime (``astloom service start`` / install stage 06) owns :32500.
    A leftover ``mcp-gateway`` container makes host start look healthy via TCP
    while the new process dies with EADDRINUSE — then sync reports MCP stopped.

    Both ``core`` and ``app`` profiles are required: mcp-gateway depends_on
    postgres/neo4j, which are only defined when ``core`` is enabled.
    """
    progress("MCP HTTP: stopping compose mcp-gateway if present (host owns the port)")
    cmd = compose_base_cmd(root) + [
        "--profile",
        "core",
        "--profile",
        "app",
        "stop",
        "--timeout",
        str(COMPOSE_STOP_TIMEOUT_SEC),
        "mcp-gateway",
    ]
    try:
        proc = run_cmd(cmd, cwd=root, check=False, timeout=COMPOSE_STOP_WAIT_SEC)
    except subprocess.TimeoutExpired:
        progress("MCP HTTP: mcp-gateway stop timed out — forcing kill")
        proc = run_cmd(
            compose_base_cmd(root)
            + ["--profile", "core", "--profile", "app", "kill", "mcp-gateway"],
            cwd=root,
            check=False,
            timeout=30,
        )
    ok = proc.returncode == 0
    if ok:
        progress("MCP HTTP: compose mcp-gateway is stopped (or was already down)")
    else:
        err = (proc.stderr or proc.stdout or "").strip()
        # Missing service / profile is fine on older compose layouts.
        progress(
            "MCP HTTP: mcp-gateway stop skipped"
            + (f" — {err[:160]}" if err else f" (exit {proc.returncode})")
        )
    return {
        "ok": ok,
        "action": "mcp_gateway_stop",
        "returncode": proc.returncode,
    }


def stop_compose(root: Path) -> dict[str, Any]:
    services = ", ".join(COMPOSE_SERVICES)
    progress(f"Databases: stopping {services}")
    cmd = compose_base_cmd(root) + [
        "stop",
        "--timeout",
        str(COMPOSE_STOP_TIMEOUT_SEC),
        *COMPOSE_SERVICES,
    ]
    forced = False
    try:
        proc = run_cmd(cmd, cwd=root, check=False, timeout=COMPOSE_STOP_WAIT_SEC)
    except subprocess.TimeoutExpired:
        forced = True
        progress("Databases: stop timed out — forcing kill")
        proc = run_cmd(
            compose_base_cmd(root) + ["kill", *COMPOSE_SERVICES],
            cwd=root,
            check=False,
            timeout=30,
        )
    if proc.returncode == 0:
        progress("Databases: stopped" + (" (forced)" if forced else ""))
    else:
        err = (proc.stderr or proc.stdout or "").strip()
        progress(
            f"Databases: stop failed (exit {proc.returncode})"
            + (f" — {err[:200]}" if err else "")
        )
    return {
        "ok": proc.returncode == 0,
        "action": "compose_stop",
        "services": list(COMPOSE_SERVICES),
        "returncode": proc.returncode,
        "forced": forced,
    }


def compose_status(root: Path) -> dict[str, Any]:
    """Report Compose health. Missing client stack → all missing (no SystemExit)."""
    out: dict[str, Any] = {"services": {}}
    if not compose_file(root).is_file() or not compose_env_file(root).is_file():
        for service in COMPOSE_SERVICES:
            out["services"][service] = {"running": False, "health": "missing"}
        out["ok"] = False
        out["stack_present"] = False
        return out
    out["stack_present"] = True
    for service in COMPOSE_SERVICES:
        cid_proc = run_cmd(compose_base_cmd(root) + ["ps", "-q", service], cwd=root, check=False)
        cid = (cid_proc.stdout or "").strip().splitlines()
        if not cid:
            out["services"][service] = {"running": False, "health": "missing"}
            continue
        inspect = subprocess.run(
            [
                "docker",
                "inspect",
                "--format",
                "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}"
                "|{{.State.StartedAt}}",
                cid[0],
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        raw = (inspect.stdout or "").strip()
        health_raw, _, started_raw = raw.partition("|")
        health = health_raw or "unknown"
        info: dict[str, Any] = {
            "running": health not in {"missing", ""},
            "health": health,
            "id": cid[0][:12],
        }
        if started_raw:
            info["started_at"] = format_docker_started_at(started_raw)
        out["services"][service] = info
    out["ok"] = all(
        (info.get("health") == "healthy") for info in out["services"].values()
    )
    return out


def compose_logs_tail(root: Path, service: str, *, lines: int = 80) -> dict[str, Any]:
    cmd = compose_base_cmd(root) + ["logs", "--no-color", "--tail", str(max(1, lines)), service]
    proc = run_cmd(cmd, cwd=root, check=False)
    text = (proc.stdout or proc.stderr or "").rstrip()
    return {
        "service": service,
        "ok": proc.returncode == 0,
        "text": text,
        "lines": text.splitlines() if text else [],
    }

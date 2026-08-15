"""Host HTTPS APIs required for client content-push (code-graph ingest-push).

``astloom service start`` must bring these up after Compose databases. MCP HTTP alone
is not enough — clients call ``server.graph_url`` (default port 32140) for
``file-hashes`` / ``ingest-push``.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from astloom_cli.service_runtime.mcp import prepare_mcp_env, tcp_ok
from astloom_cli.service_runtime.paths import (
    CODE_GRAPH_READY_TIMEOUT_SEC,
    DEFAULT_CODE_GRAPH_HOST,
    DEFAULT_CODE_GRAPH_PORT,
    DEFAULT_PROJECT_PROFILE_PORT,
    code_graph_log_path,
    code_graph_pid_path,
    project_profile_log_path,
    project_profile_pid_path,
    run_dir,
)
from astloom_cli.service_runtime.progress import (
    format_process_started_at,
    progress,
    wall_clock_now,
)

_SERVICES: tuple[dict[str, Any], ...] = (
    {
        "key": "code_graph",
        "label": "code-graph HTTPS",
        "module": "code_graph_service.api:app",
        "port_env": "ASTLOOM_CODE_GRAPH_PORT",
        "default_port": DEFAULT_CODE_GRAPH_PORT,
        "pid_path": code_graph_pid_path,
        "log_path": code_graph_log_path,
        "src_dirs": ("code-graph-service",),
        "required": True,
    },
    {
        "key": "project_profile",
        "label": "project-profile HTTPS",
        "module": "project_profile_service.api:app",
        "port_env": "ASTLOOM_PROJECT_PROFILE_PORT",
        "default_port": DEFAULT_PROJECT_PROFILE_PORT,
        "pid_path": project_profile_pid_path,
        "log_path": project_profile_log_path,
        "src_dirs": ("project-profile-service",),
        "required": False,
    },
)


def _pid_alive(pid: int) -> bool:
    from astloom_cli import service_runtime as runtime

    return runtime._pid_alive(pid)


def _read_pid(path: Path) -> int | None:
    if not path.is_file():
        return None
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
    except ValueError:
        return None
    if not _pid_alive(pid):
        path.unlink(missing_ok=True)
        return None
    return pid


def read_code_graph_pid(root: Path) -> int | None:
    return _read_pid(code_graph_pid_path(root))


def read_https_api_pids(root: Path) -> set[int]:
    out: set[int] = set()
    for spec in _SERVICES:
        pid = _read_pid(spec["pid_path"](root))
        if pid is not None:
            out.add(pid)
    return out


def _host() -> str:
    return (os.environ.get("ASTLOOM_CODE_GRAPH_HOST") or DEFAULT_CODE_GRAPH_HOST).strip() or (
        DEFAULT_CODE_GRAPH_HOST
    )


def _port_for(spec: dict[str, Any], env: dict[str, str] | None = None) -> int:
    source = env if env is not None else os.environ
    raw = source.get(spec["port_env"]) or str(spec["default_port"])
    return int(raw)


def _one_status(root: Path, spec: dict[str, Any]) -> dict[str, Any]:
    host = _host()
    port = _port_for(spec)
    pid = _read_pid(spec["pid_path"](root))
    reachable = tcp_ok(host, port)
    out: dict[str, Any] = {
        "running": pid is not None or reachable,
        "managed": pid is not None,
        "pid": pid,
        "host": host,
        "port": port,
        "reachable": reachable,
        "log": str(spec["log_path"](root)),
        "ok": reachable,
        "required": bool(spec["required"]),
        "label": spec["label"],
    }
    if pid is not None:
        started = format_process_started_at(pid)
        if started:
            out["started_at"] = started
    return out


def https_apis_status(root: Path) -> dict[str, Any]:
    """Status for managed HTTPS APIs; ``ok`` requires every *required* listener."""
    services: dict[str, Any] = {}
    required_ok = True
    for spec in _SERVICES:
        st = _one_status(root, spec)
        services[spec["key"]] = st
        if spec["required"] and not st.get("ok"):
            required_ok = False
    code = services.get("code_graph") or {}
    return {
        "ok": required_ok,
        "running": bool(code.get("running")),
        "reachable": bool(code.get("reachable")),
        "pid": code.get("pid"),
        "host": code.get("host"),
        "port": code.get("port"),
        "log": code.get("log"),
        "started_at": code.get("started_at"),
        "services": services,
    }


def _prepare_env(root: Path, spec: dict[str, Any]) -> dict[str, str]:
    env = prepare_mcp_env(root)
    # Prefer checkout TLS material used by the historic start-https-apis helper.
    cert_default = root / ".astloom" / "certs" / "server.pem"
    key_default = root / ".astloom" / "certs" / "server.key"
    if cert_default.is_file() and key_default.is_file():
        env["ASTLOOM_MCP_TLS_CERTFILE"] = str(cert_default)
        env["ASTLOOM_MCP_TLS_KEYFILE"] = str(key_default)
    srcs = [
        str(root / "backend" / "packages"),
        *[str(root / "backend" / "services" / name / "src") for name in spec["src_dirs"]],
        env.get("PYTHONPATH", ""),
    ]
    env["PYTHONPATH"] = os.pathsep.join(p for p in srcs if p).strip(os.pathsep)
    env.setdefault("PYTHONUNBUFFERED", "1")
    # Load optional sidecar env written by older helpers (never commit secrets).
    sidecar = run_dir(root) / "https-apis.env"
    if sidecar.is_file():
        for line in sidecar.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text or text.startswith("#") or "=" not in text:
                continue
            key, value = text.split("=", 1)
            env.setdefault(key.strip(), value.strip())
    return env


def _raise_start_error(spec: dict[str, Any], root: Path, summary: str, **extra: Any) -> None:
    log_path = spec["log_path"](root)
    lines = [f"error: {summary}"]
    if extra.get("host") is not None and extra.get("port") is not None:
        lines.append(f"  listen: {extra['host']}:{extra['port']}")
    if extra.get("pid") is not None:
        lines.append(f"  pid: {extra['pid']}")
    if extra.get("waited_sec") is not None:
        lines.append(
            f"  waited: {extra['waited_sec']:.1f}s / {CODE_GRAPH_READY_TIMEOUT_SEC:.0f}s budget"
        )
    if extra.get("exit_code") is not None:
        lines.append(f"  exit_code: {extra['exit_code']}")
    lines.append(f"  log: {log_path}")
    lines.append("  next: astloom service detail")
    raise SystemExit("\n".join(lines))


def _terminate_pid(pid: int) -> None:
    from astloom_cli import service_runtime as runtime

    try:
        os.killpg(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    for _ in range(20):
        if not runtime._pid_alive(pid):
            return
        time.sleep(0.1)
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _stop_one(root: Path, spec: dict[str, Any]) -> dict[str, Any]:
    label = spec["label"]
    pid_path = spec["pid_path"](root)
    pid = _read_pid(pid_path)
    host = _host()
    port = _port_for(spec)
    if pid is None:
        if tcp_ok(host, port):
            progress(f"{label}: reachable listener is not managed by this checkout")
            return {
                "ok": False,
                "action": "unmanaged_listener",
                "host": host,
                "port": port,
            }
        progress(f"{label}: already stopped")
        return {"ok": True, "action": "already_stopped"}
    progress(f"{label}: stopping (pid {pid})")
    _terminate_pid(pid)
    pid_path.unlink(missing_ok=True)
    progress(f"{label}: is stopped")
    return {"ok": True, "action": "stopped", "pid": pid}


def _start_one(root: Path, spec: dict[str, Any]) -> dict[str, Any]:
    label = spec["label"]
    current = _one_status(root, spec)
    existing = current.get("pid")
    if existing is not None and current.get("reachable"):
        progress(f"{label}: already up (pid {existing} on {current.get('host')}:{current.get('port')})")
        return {"ok": True, "action": "already_running", "pid": existing, **current}

    env = _prepare_env(root, spec)
    host = _host()
    port = _port_for(spec, env)
    python = root / ".venv" / "bin" / "python"
    exe = str(python if python.is_file() else sys.executable)
    log_path = spec["log_path"](root)
    pid_path = spec["pid_path"](root)
    started_at = wall_clock_now()

    if existing is not None:
        _terminate_pid(int(existing))
        pid_path.unlink(missing_ok=True)

    if tcp_ok(host, port, timeout=0.25):
        _raise_start_error(
            spec,
            root,
            f"{label} port {port} is still in use",
            host=host,
            port=port,
        )

    progress(f"{label}: starting on {host}:{port}")
    try:
        log_f = open(log_path, "a", encoding="utf-8")  # noqa: SIM115
    except OSError as exc:
        _raise_start_error(spec, root, f"{label} could not open log file ({exc})", host=host, port=port)

    cmd = [
        exe,
        "-m",
        "uvicorn",
        spec["module"],
        "--factory",
        "--host",
        host,
        "--port",
        str(port),
    ]
    cert = (env.get("ASTLOOM_MCP_TLS_CERTFILE") or "").strip()
    key = (env.get("ASTLOOM_MCP_TLS_KEYFILE") or "").strip()
    if cert and key and Path(cert).is_file() and Path(key).is_file():
        cmd.extend(["--ssl-certfile", cert, "--ssl-keyfile", key])
        progress(f"{label}: TLS enabled ({cert})")
    else:
        progress(f"{label}: TLS certs missing — starting without TLS (clients may refuse)")

    try:
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(root),
                env=env,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError as exc:
            _raise_start_error(spec, root, f"{label} failed to launch ({exc})", host=host, port=port)
    finally:
        log_f.close()

    pid_path.write_text(str(proc.pid) + "\n", encoding="utf-8")
    progress(f"{label}: process launched (pid {proc.pid}); waiting until reachable")

    wait_started = time.monotonic()
    deadline = wait_started + CODE_GRAPH_READY_TIMEOUT_SEC
    while time.monotonic() < deadline:
        code = proc.poll()
        if code is not None:
            pid_path.unlink(missing_ok=True)
            _raise_start_error(
                spec,
                root,
                f"{label} exited before becoming reachable",
                host=host,
                port=port,
                pid=proc.pid,
                waited_sec=time.monotonic() - wait_started,
                exit_code=code,
            )
        if tcp_ok(host, port):
            progress(f"{label}: is up on {host}:{port}")
            return {
                "ok": True,
                "action": "started",
                "started_at": started_at,
                "pid": proc.pid,
                "host": host,
                "port": port,
                "log": str(log_path),
            }
        time.sleep(0.2)

    waited = time.monotonic() - wait_started
    _terminate_pid(proc.pid)
    pid_path.unlink(missing_ok=True)
    _raise_start_error(
        spec,
        root,
        f"{label} not reachable on {host}:{port}",
        host=host,
        port=port,
        pid=proc.pid,
        waited_sec=waited,
    )
    raise AssertionError("unreachable")


def start_https_apis(root: Path) -> dict[str, Any]:
    """Start code-graph (required) and project-profile HTTPS listeners."""
    results: dict[str, Any] = {}
    for spec in _SERVICES:
        results[spec["key"]] = _start_one(root, spec)
    code = results.get("code_graph") or {}
    ok = bool(code.get("ok"))
    return {"ok": ok, "action": code.get("action"), **{k: v for k, v in code.items() if k != "ok"}, "services": results}


def stop_https_apis(root: Path) -> dict[str, Any]:
    results: dict[str, Any] = {}
    # Stop optional first, then required.
    for spec in reversed(_SERVICES):
        results[spec["key"]] = _stop_one(root, spec)
    code = results.get("code_graph") or {}
    ok = all(bool((results[s["key"]] or {}).get("ok")) for s in _SERVICES if s["required"])
    return {"ok": ok, "action": code.get("action"), "pid": code.get("pid"), "services": results}

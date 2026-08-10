"""MCP HTTP daemon process control."""

from __future__ import annotations

import os
import secrets
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from astloom_cli.service_runtime.paths import (
    DEFAULT_MCP_HOST,
    DEFAULT_MCP_PORT,
    MCP_HTTP_READY_TIMEOUT_SEC,
    mcp_log_path,
    mcp_pid_path,
    mcp_secret_path,
)
from astloom_cli.service_runtime.progress import (
    format_process_started_at,
    progress,
    wall_clock_now,
)


def prepare_mcp_env(root: Path) -> dict[str, str]:
    from astloom_cli.cli_defaults import load_dotenv_files

    load_dotenv_files(root=root)
    env = os.environ.copy()
    env["ASTLOOM_ROOT"] = str(root)
    try:
        from astloom_cli.remote_client import apply_compose_env_to_os

        apply_compose_env_to_os(env, root)
    except SystemExit:
        pass

    if not env.get("ASTLOOM_MCP_TOKEN_SECRET") and not env.get("ASTLOOM_MCP_HTTP_TOKEN"):
        secret_file = mcp_secret_path(root)
        if secret_file.is_file():
            token = secret_file.read_text(encoding="utf-8").strip()
        else:
            token = secrets.token_urlsafe(32)
            secret_file.parent.mkdir(parents=True, exist_ok=True)
            secret_file.write_text(token + "\n", encoding="utf-8")
        secret_file.chmod(0o600)
        env["ASTLOOM_MCP_TOKEN_SECRET"] = token
        os.environ["ASTLOOM_MCP_TOKEN_SECRET"] = token

    # Connect bootstrap secret: load from durable file when env unset (install creates it).
    if not (env.get("ASTLOOM_CONNECT_BOOTSTRAP_SECRET") or "").strip():
        from astloom_cli.install_auth import bootstrap_secret_path

        boot_file = bootstrap_secret_path(root)
        if boot_file.is_file():
            boot = boot_file.read_text(encoding="utf-8").strip()
            if boot:
                env["ASTLOOM_CONNECT_BOOTSTRAP_SECRET"] = boot
                os.environ["ASTLOOM_CONNECT_BOOTSTRAP_SECRET"] = boot

    host = env.get("ASTLOOM_MCP_HTTP_HOST") or DEFAULT_MCP_HOST
    port = str(env.get("ASTLOOM_MCP_HTTP_PORT") or DEFAULT_MCP_PORT)
    env["ASTLOOM_MCP_HTTP_HOST"] = host
    env["ASTLOOM_MCP_HTTP_PORT"] = port

    tls_disabled = (env.get("ASTLOOM_MCP_TLS") or "1").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }
    if tls_disabled:
        env.pop("ASTLOOM_MCP_TLS_CERTFILE", None)
        env.pop("ASTLOOM_MCP_TLS_KEYFILE", None)
    else:
        cert = (env.get("ASTLOOM_MCP_TLS_CERTFILE") or "").strip()
        key = (env.get("ASTLOOM_MCP_TLS_KEYFILE") or "").strip()
        if not (cert and key and Path(cert).is_file() and Path(key).is_file()):
            from astloom_cli.data_root import ensure_data_root
            from astloom_cli.tls_certs import ensure_tls_material

            data_root = ensure_data_root(install_root=root, environ=env)
            hostname = (
                (env.get("ASTLOOM_PUBLIC_HOSTNAME") or "").strip()
                or (env.get("ASTLOOM_TLS_HOSTNAME") or "").strip()
                or "localhost"
            )
            material = ensure_tls_material(data_root=data_root, hostname=hostname)
            cert = str(material.cert_path)
            key = str(material.key_path)
        env["ASTLOOM_MCP_TLS_CERTFILE"] = cert
        env["ASTLOOM_MCP_TLS_KEYFILE"] = key
        os.environ["ASTLOOM_MCP_TLS_CERTFILE"] = cert
        os.environ["ASTLOOM_MCP_TLS_KEYFILE"] = key

    public = (env.get("ASTLOOM_MCP_HTTP_PUBLIC_URL") or "").strip().rstrip("/")
    scheme = "http" if tls_disabled else "https"
    pub_host = (env.get("ASTLOOM_PUBLIC_HOSTNAME") or "").strip() or "127.0.0.1"
    if not public:
        public = f"{scheme}://{pub_host}:{port}"
    elif not tls_disabled and public.startswith("http://"):
        public = "https://" + public[len("http://") :]
    env["ASTLOOM_MCP_HTTP_PUBLIC_URL"] = public
    os.environ["ASTLOOM_MCP_HTTP_PUBLIC_URL"] = public

    pythonpath = os.pathsep.join(
        [
            str(root / "backend" / "services" / "mcp-gateway-service" / "src"),
            str(root / "backend" / "packages"),
            str(root / "backend" / "services" / "core-data-service" / "src"),
            str(root / "backend" / "services" / "memory-service" / "src"),
            str(root / "backend" / "services" / "code-graph-service" / "src"),
            str(root / "backend" / "services" / "docs-sync-service" / "src"),
            env.get("PYTHONPATH", ""),
        ]
    ).strip(os.pathsep)
    env["PYTHONPATH"] = pythonpath
    # File-redirected uvicorn logs stay empty on early kill unless unbuffered.
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def read_mcp_pid(root: Path) -> int | None:
    path = mcp_pid_path(root)
    if not path.is_file():
        return None
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
    except ValueError:
        return None
    # Resolve through package so tests can monkeypatch ``service_runtime._pid_alive``.
    from astloom_cli import service_runtime as runtime

    if not runtime._pid_alive(pid):
        path.unlink(missing_ok=True)
        return None
    return pid


def _discover_managed_mcp_pid(root: Path, port: int) -> int | None:
    """Recover a missing pid file only for an MCP process rooted in this checkout."""
    try:
        from port_profile import find_port_owner

        owner = find_port_owner(port)
    except Exception:  # noqa: BLE001 — owner detection is best-effort
        return None
    pid = int((owner or {}).get("pid") or 0)
    if not pid_alive(pid):
        return None
    proc = Path("/proc") / str(pid)
    try:
        command = (proc / "cmdline").read_bytes().replace(b"\0", b" ").decode(
            "utf-8",
            errors="replace",
        )
        cwd = (proc / "cwd").resolve()
    except OSError:
        return None
    if "mcp_gateway_service" not in command or cwd != root.resolve():
        return None
    pid_path = mcp_pid_path(root)
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(f"{pid}\n", encoding="utf-8")
    pid_path.chmod(0o600)
    return pid


def tcp_ok(host: str, port: int, *, timeout: float = 1.0) -> bool:
    probe_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    try:
        with socket.create_connection((probe_host, port), timeout=timeout):
            return True
    except OSError:
        return False


def mcp_status(root: Path) -> dict[str, Any]:
    env_host = os.environ.get("ASTLOOM_MCP_HTTP_HOST") or DEFAULT_MCP_HOST
    env_port = int(os.environ.get("ASTLOOM_MCP_HTTP_PORT") or DEFAULT_MCP_PORT)
    pid = read_mcp_pid(root)
    reachable = tcp_ok(env_host, env_port)
    if pid is None and reachable:
        pid = _discover_managed_mcp_pid(root, env_port)
    managed = pid is not None
    out: dict[str, Any] = {
        "running": managed or reachable,
        "managed": managed,
        "pid": pid,
        "host": env_host,
        "port": env_port,
        "reachable": reachable,
        "log": str(mcp_log_path(root)),
        "ok": reachable,
    }
    if pid is not None:
        started = format_process_started_at(pid)
        if started:
            out["started_at"] = started
    return out


def _wait_port_free(host: str, port: int, *, timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not tcp_ok(host, port, timeout=0.25):
            return True
        time.sleep(0.2)
    return not tcp_ok(host, port, timeout=0.25)


def _clear_mcp_pid(root: Path) -> None:
    mcp_pid_path(root).unlink(missing_ok=True)


def _terminate_mcp_proc(proc: subprocess.Popen[Any]) -> int | None:
    """SIGTERM (then SIGKILL) a session-leader MCP process; return exit code if known."""
    code = proc.poll()
    if code is not None:
        return code
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.terminate()
        except ProcessLookupError:
            return proc.poll()
    for _ in range(25):
        code = proc.poll()
        if code is not None:
            return code
        time.sleep(0.1)
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except ProcessLookupError:
            pass
    return proc.poll()


def _raise_mcp_start_error(
    root: Path,
    summary: str,
    *,
    host: str,
    port: int,
    pid: int | None = None,
    waited_sec: float | None = None,
    exit_code: int | None = None,
    still_running: bool = False,
) -> None:
    """Fail closed with actionable diagnostics (caller may also print log tail)."""
    log_path = mcp_log_path(root)
    lines = [f"error: {summary}"]
    lines.append(f"  listen: {host}:{port}")
    if pid is not None:
        lines.append(f"  pid: {pid}")
    if waited_sec is not None:
        lines.append(
            f"  waited: {waited_sec:.1f}s / {MCP_HTTP_READY_TIMEOUT_SEC:.0f}s budget"
        )
    if exit_code is not None:
        lines.append(f"  exit_code: {exit_code}")
    if still_running:
        lines.append("  process: still running after stop attempt")
    lines.append(f"  log: {log_path}")
    lines.append("  next: astloom service detail")
    raise SystemExit("\n".join(lines))


def start_mcp_http(root: Path) -> dict[str, Any]:
    current = mcp_status(root)
    existing = current.get("pid")
    if existing is not None:
        status = current
        where = f"{status.get('host')}:{status.get('port')}"
        progress(f"MCP HTTP: already up (pid {existing} on {where})")
        return {
            "ok": True,
            "action": "already_running",
            "pid": existing,
            "started_at": wall_clock_now(),
            **status,
        }
    env = prepare_mcp_env(root)
    host = env["ASTLOOM_MCP_HTTP_HOST"]
    port = int(env["ASTLOOM_MCP_HTTP_PORT"])
    python = root / ".venv" / "bin" / "python"
    exe = str(python if python.is_file() else sys.executable)
    log_path = mcp_log_path(root)
    started_at = wall_clock_now()

    # Same contract as install host bring-up: container must not hold :32500.
    from astloom_cli.service_runtime.compose import stop_mcp_gateway

    stop_mcp_gateway(root)
    if not _wait_port_free(host, port):
        _raise_mcp_start_error(
            root,
            f"MCP HTTP port {port} is still in use after stopping compose mcp-gateway",
            host=host,
            port=port,
        )

    progress(f"MCP HTTP: starting on {host}:{port}")
    try:
        log_f = open(log_path, "a", encoding="utf-8")  # noqa: SIM115 — closed after Popen
    except OSError as exc:
        _raise_mcp_start_error(
            root,
            f"MCP HTTP could not open log file ({exc})",
            host=host,
            port=port,
        )
    cmd = [exe, "-m", "mcp_gateway_service", "--http", "--host", host, "--port", str(port)]
    cert = (env.get("ASTLOOM_MCP_TLS_CERTFILE") or "").strip()
    key = (env.get("ASTLOOM_MCP_TLS_KEYFILE") or "").strip()
    if cert and key:
        cmd.extend(["--ssl-certfile", cert, "--ssl-keyfile", key])
        progress(f"MCP HTTP: TLS enabled ({cert})")
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
            _raise_mcp_start_error(
                root,
                f"MCP HTTP failed to launch ({exc})",
                host=host,
                port=port,
            )
    finally:
        log_f.close()
    mcp_pid_path(root).write_text(str(proc.pid) + "\n", encoding="utf-8")
    progress(f"MCP HTTP: process launched (pid {proc.pid}); waiting until reachable")

    wait_started = time.monotonic()
    deadline = wait_started + MCP_HTTP_READY_TIMEOUT_SEC
    reachable = False
    while time.monotonic() < deadline:
        code = proc.poll()
        if code is not None:
            _clear_mcp_pid(root)
            _raise_mcp_start_error(
                root,
                "MCP HTTP exited before becoming reachable",
                host=host,
                port=port,
                pid=proc.pid,
                waited_sec=time.monotonic() - wait_started,
                exit_code=code,
            )
        if tcp_ok(host, port):
            reachable = True
            break
        time.sleep(0.2)
    if not reachable:
        waited = time.monotonic() - wait_started
        exit_code = _terminate_mcp_proc(proc)
        _clear_mcp_pid(root)
        _raise_mcp_start_error(
            root,
            f"MCP HTTP not reachable on {host}:{port}",
            host=host,
            port=port,
            pid=proc.pid,
            waited_sec=waited,
            exit_code=exit_code,
            still_running=exit_code is None,
        )

    # Reject the false-success race: foreign listener answered TCP while our
    # process already failed to bind and exited.
    code = proc.poll()
    if code is not None or not tcp_ok(host, port):
        _clear_mcp_pid(root)
        _raise_mcp_start_error(
            root,
            f"MCP HTTP failed to stay up on {host}:{port}",
            host=host,
            port=port,
            pid=proc.pid,
            exit_code=code,
        )

    progress(f"MCP HTTP: is up on {host}:{port}")
    return {
        "ok": True,
        "action": "started",
        "started_at": started_at,
        "pid": proc.pid,
        "host": host,
        "port": port,
        "log": str(log_path),
    }


def stop_mcp_http(root: Path) -> dict[str, Any]:
    from astloom_cli import service_runtime as runtime

    pid = read_mcp_pid(root)
    if pid is None:
        status = mcp_status(root)
        pid = status.get("pid")
    if pid is None:
        if status.get("reachable"):
            progress("MCP HTTP: reachable listener is not managed by this checkout")
            return {
                "ok": False,
                "action": "unmanaged_listener",
                "host": status.get("host"),
                "port": status.get("port"),
            }
        progress("MCP HTTP: already stopped")
        return {"ok": True, "action": "already_stopped"}
    progress(f"MCP HTTP: stopping (pid {pid})")
    try:
        os.killpg(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            mcp_pid_path(root).unlink(missing_ok=True)
            progress("MCP HTTP: already gone")
            return {"ok": True, "action": "already_stopped"}
    for _ in range(20):
        if not runtime._pid_alive(pid):
            break
        time.sleep(0.1)
    if runtime._pid_alive(pid):
        progress(f"MCP HTTP: still running after gentle stop; forcing stop (pid {pid})")
        try:
            os.killpg(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    mcp_pid_path(root).unlink(missing_ok=True)
    progress("MCP HTTP: is stopped")
    return {"ok": True, "action": "stopped", "pid": pid}

"""Astloom development port profile loader, validators, and preflight.

Role: resolve project-scoped non-default ports and block startup on conflicts.
SoT: backend/configs/port-profiles/*.json + ASTLOOM_*_PORT env overrides.
Invariants: forbidden common defaults rejected; conflicts report owner + alternate.
Allowed failure: best-effort owner detection when ss/lsof missing (still reports bind fail).
Forbidden failure: silent reassignment; starting with unresolved conflicts.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FORBIDDEN_COMMON_PORTS = frozenset(
    {80, 443, 3000, 3001, 5432, 6379, 7474, 7687, 8000, 8080, 8501, 9000, 9200}
)

DEFAULT_PROFILE_PATH = (
    Path(__file__).resolve().parents[2] / "configs" / "port-profiles" / "astloom-dev.json"
)

DEFAULT_PORT_MAP_REL = Path(".astloom") / "run" / "port-map.json"

# Listeners we treat as already-ours when re-entering start/install.
_OWN_PROCESS_HINTS = ("docker-proxy", "astloom", "uvicorn", "mcp-gateway")

_SS_USERS_RE = re.compile(
    r'users:\(\("(?P<name>[^"]+)",pid=(?P<pid>\d+)',
)
_LSOF_RE = re.compile(r"^(?P<name>\S+)\s+(?P<pid>\d+)\s+")


class PortProfileError(ValueError):
    pass


def load_profile(path: Path | None = None) -> dict[str, Any]:
    profile_path = path or DEFAULT_PROFILE_PATH
    if not profile_path.is_file():
        raise PortProfileError(f"port profile missing: {profile_path}")
    data = json.loads(profile_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise PortProfileError("port profile must be a JSON object")
    return data


def validate_profile(profile: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    ports = profile.get("ports")
    if not isinstance(ports, dict) or not ports:
        return ["ports map is required"]
    forbidden = set(profile.get("forbidden_defaults") or []) | set(FORBIDDEN_COMMON_PORTS)
    seen: dict[int, str] = {}
    for key, value in ports.items():
        if not str(key).startswith("ASTLOOM_") or not str(key).endswith("_PORT"):
            errors.append(f"invalid port key naming: {key}")
            continue
        if not isinstance(value, int) or not (1024 < value < 65535):
            errors.append(f"port out of range for {key}: {value}")
            continue
        if value in forbidden:
            errors.append(f"port {value} for {key} is a forbidden common default")
        if value in seen:
            errors.append(f"duplicate port {value} for {key} and {seen[value]}")
        else:
            seen[value] = str(key)
    owners = profile.get("service_owners") or {}
    if not isinstance(owners, dict) or not owners:
        errors.append("service_owners map is required")
    else:
        for service, port_key in owners.items():
            if port_key not in ports:
                errors.append(f"service_owners[{service}] references unknown key {port_key}")
    return errors


def resolve_ports(profile: dict[str, Any], environ: dict[str, str] | None = None) -> dict[str, int]:
    env = environ if environ is not None else os.environ
    ports = profile.get("ports") or {}
    resolved: dict[str, int] = {}
    for key, default in ports.items():
        raw = env.get(str(key), "").strip()
        if raw:
            try:
                resolved[str(key)] = int(raw)
            except ValueError as exc:
                raise PortProfileError(f"{key} must be an integer, got {raw!r}") from exc
        else:
            resolved[str(key)] = int(default)
    errors = validate_profile(
        {
            "ports": resolved,
            "service_owners": profile.get("service_owners"),
            "forbidden_defaults": profile.get("forbidden_defaults"),
        }
    )
    if errors:
        raise PortProfileError("; ".join(errors))
    return resolved


def check_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """Return True when ``host:port`` can be bound for a service restart.

    Uses ``SO_REUSEADDR`` so a listener we just stopped (``TIME_WAIT``) does not
    falsely block ``start_all`` preflight when no foreign process owns the port.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _run_capture(cmd: list[str]) -> str:
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (proc.stdout or "") + (proc.stderr or "")


def find_port_owner(port: int) -> dict[str, Any] | None:
    """Best-effort Linux owning-process detection via ``ss`` then ``lsof``."""
    if shutil.which("ss"):
        out = _run_capture(["ss", "-lptn", f"sport = :{port}"])
        match = _SS_USERS_RE.search(out)
        if match:
            return {
                "pid": int(match.group("pid")),
                "name": match.group("name"),
                "source": "ss",
                "raw": out.strip()[:400],
            }
    if shutil.which("lsof"):
        out = _run_capture(["lsof", f"-iTCP:{port}", "-sTCP:LISTEN", "-n", "-P"])
        for line in out.splitlines():
            if line.startswith("COMMAND"):
                continue
            match = _LSOF_RE.match(line)
            if match:
                return {
                    "pid": int(match.group("pid")),
                    "name": match.group("name"),
                    "source": "lsof",
                    "raw": line.strip()[:400],
                }
    return None


def owner_looks_ours(owner: dict[str, Any] | None) -> bool:
    if not owner:
        return False
    blob = f"{owner.get('name', '')} {owner.get('raw', '')}".lower()
    return any(hint in blob for hint in _OWN_PROCESS_HINTS)


def pid_started_from_root(pid: int, root: Path) -> bool:
    """True when ``pid`` was launched via a command under ``root`` (e.g. ``.venv/bin/python``).

    ``ss``/``lsof`` report native services only by comm name (``python``), so
    hint matching alone cannot recognize this checkout's own listeners such as
    ``.venv/bin/python -m adapter_service``. Best-effort: unreadable ``/proc``
    entries count as foreign.
    """
    if pid <= 0:
        return False
    proc = Path("/proc") / str(pid)
    try:
        argv0 = (
            (proc / "cmdline").read_bytes().split(b"\0", 1)[0].decode("utf-8", errors="replace")
        )
        if not argv0:
            return False
        command = Path(argv0)
        if not command.is_absolute():
            command = (proc / "cwd").readlink() / command
    except OSError:
        return False
    command = Path(os.path.normpath(command))
    return any(command.is_relative_to(base) for base in {root.absolute(), root.resolve()})


def suggest_alternate_port(
    occupied: int,
    *,
    reserved: set[int],
    profile: dict[str, Any],
    host: str = "127.0.0.1",
    span: int = 500,
) -> int | None:
    """Suggest the next free project-scoped port near ``occupied``."""
    forbidden = set(profile.get("forbidden_defaults") or []) | set(FORBIDDEN_COMMON_PORTS)
    base = int(profile.get("base_hint") or max(32000, occupied - (occupied % 1000)))
    low = max(1025, base)
    high = min(65534, base + max(span, 200))
    candidates = list(range(occupied + 1, high + 1)) + list(range(low, occupied))
    for candidate in candidates:
        if candidate in reserved or candidate in forbidden:
            continue
        if not (1024 < candidate < 65535):
            continue
        if check_port_available(candidate, host=host):
            return candidate
    return None


def default_port_map_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path.cwd()
    return root / DEFAULT_PORT_MAP_REL


def write_port_map(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    return path


def run_preflight(
    profile: dict[str, Any],
    *,
    environ: dict[str, str] | None = None,
    host: str = "127.0.0.1",
    allow_ours: bool = False,
    allowed_pids: set[int] | None = None,
    repo_root: Path | None = None,
    profile_path: Path | None = None,
) -> dict[str, Any]:
    """Check all resolved ports; suggest alternates; optionally tolerate our listeners.

    ``repo_root`` extends ours-detection to processes launched from that
    checkout (venv services survive an MCP gateway crash as orphans).
    """
    resolved = resolve_ports(profile, environ=environ)
    reserved = set(resolved.values())
    ports: dict[str, dict[str, Any]] = {}
    conflicts: list[str] = []
    ok = True
    for key, port in resolved.items():
        available = check_port_available(port, host=host)
        entry: dict[str, Any] = {"port": port, "available": available}
        if not available:
            owner = find_port_owner(port)
            if owner:
                entry["owner"] = owner
            alternate = suggest_alternate_port(
                port, reserved=reserved, profile=profile, host=host
            )
            if alternate is not None:
                entry["suggested_port"] = alternate
                reserved.add(alternate)
            owner_pid = int(owner.get("pid", 0)) if owner else 0
            ours = bool(
                owner_looks_ours(owner)
                or (owner_pid and owner_pid in (allowed_pids or set()))
                or (owner_pid and repo_root is not None and pid_started_from_root(owner_pid, repo_root))
            )
            entry["ours"] = ours
            blocking = not (allow_ours and ours)
            entry["blocking"] = blocking
            if blocking:
                ok = False
                conflicts.append(key)
        ports[key] = entry
    return {
        "ok": ok,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "profile": str(profile_path or DEFAULT_PROFILE_PATH),
        "host": host,
        "ports": ports,
        "resolved": resolved,
        "conflicts": conflicts,
    }

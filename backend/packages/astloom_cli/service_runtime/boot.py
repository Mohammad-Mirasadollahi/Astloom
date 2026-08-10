"""Systemd user/system boot unit for Astloom."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from astloom_cli.service_runtime.paths import UNIT_NAME


def astloom_bin(root: Path) -> Path:
    venv_bin = root / ".venv" / "bin" / "astloom"
    if venv_bin.is_file():
        return venv_bin
    which = Path(sys.executable).resolve().parent / "astloom"
    if which.is_file():
        return which
    return venv_bin


def unit_body(root: Path, *, user: bool) -> str:
    exe = astloom_bin(root)
    after = "network-online.target docker.service"
    wanted = "default.target" if user else "multi-user.target"
    requires = "Requires=docker.service\n" if not user else ""
    return f"""[Unit]
Description=Astloom (Compose postgres/neo4j + MCP HTTP)
After={after}
{requires}
[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory={root}
Environment=ASTLOOM_ROOT={root}
ExecStart={exe} service start
ExecStop={exe} service stop

[Install]
WantedBy={wanted}
"""


def unit_path(*, user: bool) -> Path:
    if user:
        return Path.home() / ".config" / "systemd" / "user" / UNIT_NAME
    return Path("/etc/systemd/system") / UNIT_NAME


def systemctl(args: list[str], *, user: bool) -> subprocess.CompletedProcess[str]:
    cmd = ["systemctl"]
    if user:
        cmd.append("--user")
    cmd.extend(args)
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


def boot_enable(root: Path, *, user: bool = False) -> dict[str, Any]:
    from astloom_cli import service_runtime as runtime

    path = unit_path(user=user)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = unit_body(root, user=user)
    try:
        path.write_text(body, encoding="utf-8")
    except PermissionError as exc:
        raise SystemExit(
            f"error: cannot write {path} ({exc}); retry with sudo or: astloom boot enable --user"
        ) from exc
    reload = runtime._systemctl(["daemon-reload"], user=user)
    enable = runtime._systemctl(["enable", UNIT_NAME], user=user)
    if enable.returncode != 0:
        err = (enable.stderr or enable.stdout or "").strip()
        raise SystemExit(f"error: systemctl enable failed: {err[:500]}")
    return {
        "ok": True,
        "action": "enabled",
        "unit": UNIT_NAME,
        "path": str(path),
        "user": user,
        "daemon_reload_ok": reload.returncode == 0,
        "hint": (
            "user unit: run `loginctl enable-linger $USER` so it starts at boot without login"
            if user
            else None
        ),
    }


def boot_disable(*, user: bool = False) -> dict[str, Any]:
    from astloom_cli import service_runtime as runtime

    disable = runtime._systemctl(["disable", UNIT_NAME], user=user)
    path = unit_path(user=user)
    removed = False
    if path.is_file():
        try:
            path.unlink()
            removed = True
        except PermissionError:
            pass
    runtime._systemctl(["daemon-reload"], user=user)
    return {
        "ok": disable.returncode == 0 or not path.is_file(),
        "action": "disabled",
        "unit": UNIT_NAME,
        "path": str(path),
        "unit_file_removed": removed,
        "user": user,
        "systemctl_returncode": disable.returncode,
    }


def boot_status(root: Path) -> dict[str, Any]:
    from astloom_cli import service_runtime as runtime

    results: dict[str, Any] = {"unit": UNIT_NAME, "modes": {}}
    for label, user in (("system", False), ("user", True)):
        path = unit_path(user=user)
        is_enabled = runtime._systemctl(["is-enabled", UNIT_NAME], user=user)
        results["modes"][label] = {
            "unit_file": str(path),
            "unit_file_present": path.is_file(),
            "enabled": (is_enabled.stdout or "").strip() == "enabled",
            "is_enabled_raw": (is_enabled.stdout or is_enabled.stderr or "").strip(),
        }
    return results

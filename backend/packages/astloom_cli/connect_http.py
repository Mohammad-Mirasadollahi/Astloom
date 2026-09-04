"""Shared HTTPS client helpers for connect / content-push (CA trust + verify)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from astloom_cli.connect_config import ConnectSettings

ACCESS_TOKEN_FILENAME = "access_token"
CA_PEM_REL = Path("certs") / "ca.pem"
# Debian/Ubuntu update-ca-certificates requires a .crt under this dir.
_LINUX_CA_TRUST_NAME = "astloom-private-ca.crt"
_LINUX_CA_TRUST_DIR = Path("/usr/local/share/ca-certificates")

_VERIFY_TRUE = frozenset({"1", "true", "yes", "on"})
_VERIFY_FALSE = frozenset({"0", "false", "no", "off"})


def parse_tls_verify(raw: object, *, default: bool = False) -> bool:
    """Parse connect.yaml / env tls_verify flag. Default is off (lab-friendly)."""
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    text = str(raw).strip().lower()
    if not text:
        return default
    if text in _VERIFY_TRUE:
        return True
    if text in _VERIFY_FALSE:
        return False
    raise SystemExit(
        f"error: auth.tls_verify={raw!r} is invalid; use true/false "
        "(default false — TLS without certificate verification)"
    )


def resolve_ca_file(settings: "ConnectSettings") -> str:
    """Return an existing CA PEM path, or empty string."""
    ca = str(getattr(settings, "ca_file", "") or "").strip()
    if ca:
        path = Path(ca).expanduser()
        if not path.is_file():
            cfg = getattr(settings, "config_path", None)
            if cfg is not None and not path.is_absolute():
                candidate = (Path(cfg).expanduser().resolve().parent / path).resolve()
                if candidate.is_file():
                    path = candidate
        if path.is_file():
            return str(path)
    env_ca = os.environ.get("ASTLOOM_CONNECT_CA_FILE", "").strip()
    if env_ca and Path(env_ca).is_file():
        return env_ca
    return ""


def httpx_verify(settings: "ConnectSettings") -> str | bool:
    """Return httpx ``verify`` value.

    Default (``tls_verify=false``): ``False`` — encrypt in transit, do not validate
    the server certificate (convenient for auto-TLS lab installs).

    When ``tls_verify=true``: require a readable CA PEM (``auth.ca_file`` /
    ``ASTLOOM_CONNECT_CA_FILE`` / auto ``.astloom/certs/ca.pem``) and return
    that path. Missing trust material fails with a clear operator error.
    """
    tls_verify = bool(getattr(settings, "tls_verify", False))
    if not tls_verify:
        return False
    ca = resolve_ca_file(settings)
    if ca:
        return ca
    hint_paths = [
        "auth.ca_file: /path/to/ca.pem",
        "env ASTLOOM_CONNECT_CA_FILE=/path/to/ca.pem",
        "re-run `astloom-client connect` so bootstrap can write .astloom/certs/ca.pem",
        "copy server file {data-root}/certs/ca.pem (often /opt/Astloom-data/certs/ca.pem)",
    ]
    raise SystemExit(
        "error: auth.tls_verify is true but no CA trust file was found.\n"
        "  TLS verification needs the Astloom private CA PEM on the client.\n"
        "  Fix one of:\n"
        + "".join(f"  • {line}\n" for line in hint_paths)
        + "  Or set auth.tls_verify: false (default) to connect without verifying the certificate."
    )


def access_token_path(config_path: Path | None) -> Path | None:
    if config_path is None:
        return None
    return config_path.parent / ACCESS_TOKEN_FILENAME


def default_ca_path(config_path: Path | None) -> Path | None:
    if config_path is None:
        return None
    return config_path.parent / CA_PEM_REL


def read_access_token_file(config_path: Path | None) -> str:
    path = access_token_path(config_path)
    if path is None or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def persist_access_token(config_path: Path | None, token: str) -> Path | None:
    """Write minted access token next to connect.yaml (mode 0600). Never log token."""
    path = access_token_path(config_path)
    if path is None or not token.strip():
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    try:
        tmp.write_text(token.strip() + "\n", encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(path)
        os.chmod(path, 0o600)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
    return path


def persist_ca_pem(config_path: Path | None, ca_pem: str) -> Path | None:
    """Write bootstrap ``ca_pem`` under ``.astloom/certs/ca.pem``."""
    path = default_ca_path(config_path)
    text = (ca_pem or "").strip()
    if path is None or not text:
        return None
    if "BEGIN CERTIFICATE" not in text:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.chmod(tmp, 0o644)
        tmp.replace(path)
        os.chmod(path, 0o644)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
    return path


def ensure_ide_os_trusts_ca(ca_path: str | Path) -> dict[str, Any]:
    """Install the Astloom private CA into the OS trust store for IDE HTTP MCP.

    Cursor (and similar) Streamable HTTP clients use the runtime TLS stack and
    **always verify** certificates. ``auth.tls_verify: false`` only affects the
    Astloom CLI (httpx), not IDE ``mcp.json`` URL transports — without OS trust,
    Cursor logs ``fetch failed`` / ``UNABLE_TO_VERIFY_LEAF_SIGNATURE``.

    Node 20+ (Cursor Remote ``cursor-server``) also needs ``NODE_EXTRA_CA_CERTS``
    (or ``node --use-system-ca``); OS trust alone is not enough for default Node.
    """
    src = Path(str(ca_path)).expanduser()
    result: dict[str, Any] = {
        "ok": False,
        "action": "noop",
        "ca_path": str(src),
        "detail": "",
    }
    if not src.is_file():
        result["detail"] = "ca file missing"
        return result
    text = src.read_text(encoding="utf-8", errors="replace")
    if "BEGIN CERTIFICATE" not in text:
        result["detail"] = "ca file is not a PEM certificate"
        return result
    if sys.platform != "linux":
        result["detail"] = (
            f"OS auto-trust not implemented for {sys.platform}; "
            "install the Astloom ca.pem into the system trust store and set "
            "NODE_EXTRA_CA_CERTS to that path for Cursor Remote"
        )
        return result
    update_bin = shutil.which("update-ca-certificates")
    if update_bin is None:
        result["detail"] = "update-ca-certificates not found (unsupported distro)"
        return result
    dest = _LINUX_CA_TRUST_DIR / _LINUX_CA_TRUST_NAME
    try:
        _LINUX_CA_TRUST_DIR.mkdir(parents=True, exist_ok=True)
        body = text if text.endswith("\n") else text + "\n"
        changed = True
        if dest.is_file() and dest.read_text(encoding="utf-8", errors="replace") == body:
            changed = False
        else:
            dest.write_text(body, encoding="utf-8")
            os.chmod(dest, 0o644)
        proc = subprocess.run(
            [update_bin],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        env_note = _ensure_node_extra_ca_certs(dest)
        result["ok"] = proc.returncode == 0
        result["action"] = "installed" if changed else "refresh"
        if not result["ok"]:
            result["action"] = "install_failed"
        result["detail"] = (proc.stderr or proc.stdout or "").strip()[-400:]
        if env_note:
            result["detail"] = (result["detail"] + " | " + env_note).strip(" |")
        result["dest"] = str(dest)
        result["node_extra_ca_certs"] = str(dest)
        return result
    except PermissionError:
        result["action"] = "need_root"
        result["detail"] = (
            f"cannot write {dest}; re-run connect as root or copy ca.pem there, "
            f"run update-ca-certificates, and set NODE_EXTRA_CA_CERTS={dest}"
        )
        return result
    except OSError as exc:
        result["action"] = "error"
        result["detail"] = str(exc)
        return result


def _ensure_node_extra_ca_certs(ca_dest: Path) -> str:
    """Persist NODE_EXTRA_CA_CERTS so Cursor Remote's Node trusts the private CA."""
    abs_ca = str(ca_dest.resolve())
    line = f'NODE_EXTRA_CA_CERTS="{abs_ca}"'
    notes: list[str] = []
    # /etc/environment (PAM / many remote sessions)
    env_file = Path("/etc/environment")
    try:
        existing = env_file.read_text(encoding="utf-8") if env_file.is_file() else ""
        if "NODE_EXTRA_CA_CERTS=" not in existing:
            with env_file.open("a", encoding="utf-8") as fh:
                if existing and not existing.endswith("\n"):
                    fh.write("\n")
                fh.write(line + "\n")
            notes.append("wrote /etc/environment")
        elif abs_ca not in existing:
            lines = [
                ln
                for ln in existing.splitlines()
                if not ln.strip().startswith("NODE_EXTRA_CA_CERTS=")
            ]
            lines.append(line)
            env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
            notes.append("updated /etc/environment")
    except OSError as exc:
        notes.append(f"/etc/environment skipped ({exc})")
    # Login shells / interactive
    profile = Path("/etc/profile.d/astloom-ca.sh")
    profile_body = (
        "# Managed by astloom-client connect — Cursor Remote TLS for Astloom MCP\n"
        f'export NODE_EXTRA_CA_CERTS="{abs_ca}"\n'
    )
    try:
        if not profile.is_file() or profile.read_text(encoding="utf-8") != profile_body:
            profile.write_text(profile_body, encoding="utf-8")
            os.chmod(profile, 0o644)
            notes.append("wrote /etc/profile.d/astloom-ca.sh")
    except OSError as exc:
        notes.append(f"profile.d skipped ({exc})")
    return "; ".join(notes)
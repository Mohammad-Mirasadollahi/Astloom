"""Shared HTTPS client helpers for connect / content-push (CA trust + verify)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from astloom_cli.connect_config import ConnectSettings

ACCESS_TOKEN_FILENAME = "access_token"
CA_PEM_REL = Path("certs") / "ca.pem"

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
    if ca and Path(ca).is_file():
        return ca
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

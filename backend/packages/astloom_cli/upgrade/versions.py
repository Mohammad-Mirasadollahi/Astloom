"""Product and MCP contract versions for server↔client upgrade handshake."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from astloom_cli import __version__

# Bump when MCP/tool argument contracts break across client and server.
CONTRACT_VERSION = "1"
MIN_CLIENT_CONTRACT = "1"
PRODUCT_VERSION = __version__


def server_version_payload() -> dict[str, str]:
    """Fields advertised by ``platform.ping`` for client compatibility checks."""
    return {
        "product_version": PRODUCT_VERSION,
        "contract_version": CONTRACT_VERSION,
        "min_client_contract": MIN_CLIENT_CONTRACT,
    }


def read_install_versions(root: Path) -> dict[str, str]:
    """Read stamped versions from ``.astloom/install-state.env`` (best effort)."""
    path = root / ".astloom" / "install-state.env"
    out = {
        "product_version": "",
        "contract_version": "",
        "runtime": "",
    }
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key in out:
            out[key] = value
        elif key == "runtime":
            out["runtime"] = value
    return out


def stamp_install_versions(root: Path, *, runtime: str = "") -> dict[str, str]:
    """Persist current product/contract versions into install-state.env."""
    state_dir = root / ".astloom"
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "install-state.env"
    existing: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.strip().startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            existing[k.strip()] = v.strip()
    existing["product_version"] = PRODUCT_VERSION
    existing["contract_version"] = CONTRACT_VERSION
    if runtime:
        existing["runtime"] = runtime
    elif not existing.get("runtime"):
        existing["runtime"] = "host"
    lines = [f"{k}={v}\n" for k, v in sorted(existing.items())]
    path.write_text("".join(lines), encoding="utf-8")
    return {
        "product_version": PRODUCT_VERSION,
        "contract_version": CONTRACT_VERSION,
        "runtime": existing["runtime"],
        "path": str(path),
    }


def parse_install_state_kv(root: Path) -> dict[str, str]:
    """All key=value pairs from install-state.env."""
    path = root / ".astloom" / "install-state.env"
    data: dict[str, str] = {}
    if not path.is_file():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        data[k.strip()] = v.strip()
    return data


def client_version_payload() -> dict[str, Any]:
    return {
        "product_version": PRODUCT_VERSION,
        "contract_version": CONTRACT_VERSION,
        "role": "client",
    }

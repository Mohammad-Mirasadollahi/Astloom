"""version / doctor commands."""

from __future__ import annotations

import argparse
import os
import shutil
import sys

from astloom_cli import __version__
from astloom_cli.util import print_json, repo_root
from usage_profile import list_profile_ids


def cmd_version(_: argparse.Namespace) -> int:
    from astloom_cli.upgrade.versions import CONTRACT_VERSION, PRODUCT_VERSION

    print(f"astloom {__version__}")
    print(f"product {PRODUCT_VERSION}")
    print(f"contract {CONTRACT_VERSION}")
    print(f"root {repo_root()}")
    return 0


def cmd_doctor(_: argparse.Namespace) -> int:
    from astloom_cli.upgrade.versions import (
        CONTRACT_VERSION,
        PRODUCT_VERSION,
        read_install_versions,
        server_version_payload,
    )

    root = repo_root()
    venv_dir = os.environ.get("ASTLOOM_VENV_DIR", ".venv")
    venv_python = root / venv_dir / "bin" / "python"
    astloom_bin = root / venv_dir / "bin" / "astloom"
    ok = True
    checks = {
        "repo_root": str(root),
        "venv_dir": venv_dir,
        "venv_python": venv_python.is_file(),
        "astloom_on_venv_path": astloom_bin.is_file(),
        "which_astloom": shutil.which("astloom"),
        "profiles": list_profile_ids(),
        "product_version": PRODUCT_VERSION,
        "contract_version": CONTRACT_VERSION,
        "install_versions": read_install_versions(root),
        "server_advertisement": server_version_payload(),
    }
    for name in (
        "fastapi",
        "usage_profile",
        "astloom_cli",
        "astloom_backup",
        "mcp_gateway_service",
    ):
        try:
            if name == "mcp_gateway_service":
                sys.path.insert(0, str(root / "backend" / "services" / "mcp-gateway-service" / "src"))
            __import__(name if name != "mcp_gateway_service" else "mcp_gateway_service")
            checks[f"import_{name}"] = True
        except Exception as exc:  # noqa: BLE001
            checks[f"import_{name}"] = f"FAIL: {exc}"
            ok = False
    try:
        from astloom_cli.install_root_marker import looks_like_astloom_root, stamp_install_root_from_env

        if looks_like_astloom_root(root):
            stamped = stamp_install_root_from_env(root)
            checks["install_root_markers"] = [str(p) for p in stamped]
    except Exception as exc:  # noqa: BLE001 — doctor must not fail on marker I/O
        checks["install_root_markers"] = f"skip: {exc}"
    print_json(checks)
    return 0 if ok and checks["venv_python"] else 1

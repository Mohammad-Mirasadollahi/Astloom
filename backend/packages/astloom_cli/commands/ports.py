"""Port profile preflight commands."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from astloom_cli.util import print_json, repo_root
from port_profile import PortProfileError, load_profile, resolve_ports, run_preflight, write_port_map
from port_profile.loader import DEFAULT_PORT_MAP_REL, DEFAULT_PROFILE_PATH


def _ports_profile_path(args: argparse.Namespace) -> Path | None:
    raw = str(getattr(args, "profile", "") or "").strip()
    return Path(raw) if raw else None


def _port_map_path(args: argparse.Namespace) -> Path:
    raw = str(getattr(args, "write_map", "") or "").strip()
    if raw and raw not in {"1", "true", "True", "yes"}:
        return Path(raw)
    return repo_root() / DEFAULT_PORT_MAP_REL


def cmd_ports_show(args: argparse.Namespace) -> int:
    path = _ports_profile_path(args)
    try:
        profile = load_profile(path)
        resolved = resolve_ports(profile)
    except PortProfileError as exc:
        raise SystemExit(f"error: {exc}") from exc
    print_json({"profile": str(path or DEFAULT_PROFILE_PATH), "ports": resolved})
    return 0


def cmd_ports_check(args: argparse.Namespace) -> int:
    path = _ports_profile_path(args)
    allow_ours = bool(getattr(args, "allow_ours", False))
    try:
        profile = load_profile(path)
        report = run_preflight(
            profile,
            profile_path=path or DEFAULT_PROFILE_PATH,
            allow_ours=allow_ours,
            repo_root=repo_root(),
        )
    except PortProfileError as exc:
        raise SystemExit(f"error: {exc}") from exc

    write = getattr(args, "write_map", None)
    map_path: Path | None = None
    if write is not None and str(write) != "":
        map_path = _port_map_path(args)
        write_port_map(map_path, report)

    payload: dict[str, Any] = {
        "ok": report["ok"],
        "ports": report["ports"],
        "profile": report["profile"],
        "conflicts": report["conflicts"],
    }
    if map_path is not None:
        payload["port_map"] = str(map_path)
    print_json(payload)
    return 0 if report["ok"] else 1

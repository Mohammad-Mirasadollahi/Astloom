"""Log tails and service detail collection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from astloom_cli.service_runtime.paths import code_graph_log_path, mcp_log_path


def read_log_tail(path: Path, *, lines: int = 80) -> dict[str, Any]:
    """Return the last *lines* of a log file (for diagnosis when start fails)."""
    if lines < 1:
        lines = 1
    if not path.is_file():
        return {
            "path": str(path),
            "exists": False,
            "lines": [],
            "text": "",
        }
    try:
        raw = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return {
            "path": str(path),
            "exists": True,
            "error": str(exc),
            "lines": [],
            "text": "",
        }
    tail = raw[-lines:]
    return {
        "path": str(path),
        "exists": True,
        "line_count": len(raw),
        "shown": len(tail),
        "lines": tail,
        "text": "\n".join(tail),
    }


def collect_detail(root: Path, report: dict[str, Any], *, lines: int = 80) -> dict[str, Any]:
    """Gather MCP + code-graph + unhealthy Compose log tails for ``astloom service detail``."""
    # Late lookup so tests can monkeypatch ``service_runtime.compose_logs_tail``.
    from astloom_cli import service_runtime as runtime

    mcp = report.get("mcp") or {}
    https_apis = report.get("https_apis") or {}
    log_path = Path(str(mcp.get("log") or mcp_log_path(root)))
    graph_log = Path(str(https_apis.get("log") or code_graph_log_path(root)))
    detail: dict[str, Any] = {
        "mcp_http": read_log_tail(log_path, lines=lines),
        "code_graph_https": read_log_tail(graph_log, lines=lines),
        "compose": {},
    }
    compose = report.get("compose") or {}
    for name, info in (compose.get("services") or {}).items():
        health = str(info.get("health") or "")
        if health == "healthy":
            continue
        try:
            detail["compose"][name] = runtime.compose_logs_tail(root, name, lines=lines)
        except SystemExit as exc:
            detail["compose"][name] = {"service": name, "ok": False, "error": str(exc), "lines": []}
    return detail


def dump_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True)

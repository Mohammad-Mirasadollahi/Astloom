"""MCP token usage JSONL under Astloom-data/mcp-usage (or ASTLOOM_MCP_USAGE_LOG_DIR)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from astloom_cli.util import repo_root

DEFAULT_DIR_REL = Path(".astloom") / "mcp-usage"
EVENTS_NAME = "events.jsonl"
ENV_DIR = "ASTLOOM_MCP_USAGE_LOG_DIR"
ENV_MAX = "ASTLOOM_MCP_USAGE_LOG_MAX_BYTES"
DEFAULT_MAX_BYTES = 256 * 1024 * 1024  # 256 MiB


def approx_tokens_from_chars(chars: int) -> int:
    return max(0, int(chars) // 4)


def approx_tokens_from_obj(obj: Any) -> int:
    return approx_tokens_from_chars(len(json.dumps(obj, ensure_ascii=False, sort_keys=True)))


def usage_log_dir(environ: dict[str, str] | None = None) -> Path:
    env = environ if environ is not None else os.environ
    raw = str(env.get(ENV_DIR) or "").strip()
    if raw:
        path = Path(raw).expanduser()
        return path if path.is_absolute() else (repo_root() / path).resolve()
    from astloom_cli.data_root import mcp_usage_dir

    return mcp_usage_dir(install_root=repo_root(), environ=dict(env)).resolve()


def events_path(environ: dict[str, str] | None = None) -> Path:
    return usage_log_dir(environ) / EVENTS_NAME


def usage_log_max_bytes(environ: dict[str, str] | None = None) -> int:
    env = environ if environ is not None else os.environ
    raw = str(env.get(ENV_MAX) or "").strip()
    if not raw:
        return DEFAULT_MAX_BYTES
    try:
        return max(1024 * 1024, int(raw))
    except ValueError as exc:
        raise SystemExit(f"error: {ENV_MAX} must be an integer byte count") from exc


def _trim_jsonl(path: Path, max_bytes: int) -> None:
    if not path.is_file():
        return
    try:
        size = path.stat().st_size
    except OSError:
        return
    if size <= max_bytes:
        return
    # Drop oldest half of lines (FIFO-ish without rewrite cost of full rotate).
    try:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError:
        return
    if len(lines) < 2:
        return
    keep = lines[len(lines) // 2 :]
    path.write_text("".join(keep), encoding="utf-8")


def append_mcp_usage_event(
    event: dict[str, Any],
    *,
    environ: dict[str, str] | None = None,
) -> Path | None:
    """Best-effort append; never raises (MCP path must stay up)."""
    try:
        directory = usage_log_dir(environ)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / EVENTS_NAME
        row = {
            **event,
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        _trim_jsonl(path, usage_log_max_bytes(environ))
        return path
    except Exception:
        return None


def _parse_ts(raw: str) -> datetime:
    dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def load_mcp_usage_events(
    *,
    start: datetime,
    end: datetime,
    environ: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    path = events_path(environ)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts_raw = row.get("ts")
            if not ts_raw:
                continue
            try:
                ts = _parse_ts(str(ts_raw))
            except ValueError:
                continue
            if start <= ts <= end:
                rows.append(row)
    return rows

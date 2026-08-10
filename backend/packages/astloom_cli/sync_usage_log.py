"""Sync usage reports: one JSON file per run, folder FIFO at 5 GiB default."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from astloom_cli.util import repo_root

DEFAULT_DIR_REL = Path(".astloom") / "sync-usage"
DEFAULT_DIR_MAX_BYTES = 5_368_709_120  # 5 GiB
ENV_DIR = "ASTLOOM_SYNC_USAGE_LOG_DIR"
ENV_DIR_MAX = "ASTLOOM_SYNC_USAGE_LOG_DIR_MAX_BYTES"
# Back-compat aliases (file path → parent dir; file max ignored for folder cap)
ENV_PATH_LEGACY = "ASTLOOM_SYNC_USAGE_LOG_PATH"
ENV_MAX_LEGACY = "ASTLOOM_SYNC_USAGE_LOG_MAX_BYTES"


def execution_at_now() -> str:
    """Wall-clock execution start: date and time to the second."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def execution_at_filename(execution_at: str) -> str:
    """Safe filename from ``YYYY-MM-DD HH:MM:SS`` → ``YYYY-MM-DD_HH-MM-SS.json``."""
    stamp = execution_at.strip().replace(" ", "_").replace(":", "-")
    return f"{stamp}.json"


def usage_log_dir(environ: dict[str, str] | None = None) -> Path:
    env = environ if environ is not None else os.environ
    raw = str(env.get(ENV_DIR) or env.get(ENV_PATH_LEGACY) or "").strip()
    if raw:
        path = Path(raw).expanduser()
        resolved = path if path.is_absolute() else (repo_root() / path).resolve()
        # Legacy: if a .jsonl file path was configured, use its parent as the folder.
        if resolved.suffix in {".jsonl", ".json"} and not resolved.is_dir():
            return resolved.parent
        return resolved
    from astloom_cli.data_root import sync_usage_dir

    return sync_usage_dir(install_root=repo_root(), environ=dict(env)).resolve()


def usage_log_dir_max_bytes(environ: dict[str, str] | None = None) -> int:
    env = environ if environ is not None else os.environ
    raw = str(env.get(ENV_DIR_MAX) or env.get(ENV_MAX_LEGACY) or "").strip()
    if not raw:
        return DEFAULT_DIR_MAX_BYTES
    try:
        value = int(raw)
    except ValueError as exc:
        raise SystemExit(f"error: {ENV_DIR_MAX} must be an integer byte count") from exc
    return max(1024 * 1024, value)  # at least 1 MiB


def approx_tokens_from_chars(chars: int) -> int:
    return max(0, int(chars) // 4)


def _dir_size_bytes(directory: Path) -> int:
    total = 0
    if not directory.is_dir():
        return 0
    for path in directory.rglob("*"):
        if path.is_file():
            try:
                total += path.stat().st_size
            except OSError:
                continue
    return total


def _fifo_trim_dir(directory: Path, max_bytes: int) -> None:
    """Delete oldest files (by mtime, then name) until folder size ≤ max_bytes."""
    if not directory.is_dir():
        return
    while _dir_size_bytes(directory) > max_bytes:
        files = [p for p in directory.iterdir() if p.is_file() and p.suffix == ".json"]
        if not files:
            # Also remove stray non-json if somehow filling the dir
            files = [p for p in directory.iterdir() if p.is_file()]
        if not files:
            return
        files.sort(key=lambda p: (p.stat().st_mtime, p.name))
        try:
            files[0].unlink()
        except OSError:
            return


def _unique_path(directory: Path, execution_at: str) -> Path:
    base = directory / execution_at_filename(execution_at)
    if not base.exists():
        return base
    # Same-second collision: append -2, -3, …
    stem = base.stem
    for i in range(2, 10_000):
        candidate = directory / f"{stem}-{i}.json"
        if not candidate.exists():
            return candidate
    raise SystemExit(f"error: too many usage reports for second {execution_at}")


def append_sync_usage_record(record: dict[str, Any], *, environ: dict[str, str] | None = None) -> Path:
    """Write one JSON report file named by execution time; FIFO-trim the folder."""
    directory = usage_log_dir(environ)
    directory.mkdir(parents=True, exist_ok=True)
    execution_at = str(record.get("execution_at") or execution_at_now())
    record = {**record, "execution_at": execution_at}
    path = _unique_path(directory, execution_at)
    path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _fifo_trim_dir(directory, usage_log_dir_max_bytes(environ))
    return path


def build_sync_usage_record(
    *,
    scope: str,
    report: dict[str, Any],
    tasks: list[dict[str, Any]],
    duration_sec: float,
    tokens_in: int,
    tokens_out: int,
    execution_at: str | None = None,
) -> dict[str, Any]:
    tokens_total = int(tokens_in) + int(tokens_out)
    return {
        "execution_at": execution_at or execution_at_now(),
        "kind": "sync",
        "scope": scope,
        "duration_sec": round(float(duration_sec), 3),
        "tokens": {
            "input": int(tokens_in),
            "output": int(tokens_out),
            "total": tokens_total,
            "unit": "approx_chars/4",
        },
        "tasks": tasks,
        "report": report,
    }


def task_entry(
    *,
    name: str,
    duration_sec: float | None,
    tokens_in: int = 0,
    tokens_out: int = 0,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": name,
        "duration_sec": None if duration_sec is None else round(float(duration_sec), 3),
        "tokens": {
            "input": int(tokens_in),
            "output": int(tokens_out),
            "total": int(tokens_in) + int(tokens_out),
        },
    }
    if extra:
        row.update(extra)
    return row


def estimate_output_tokens(*, symbols_documented: int, docs_indexed: int = 0) -> int:
    """Rough output size when real LLM usage is unavailable (local/stub docs)."""
    return approx_tokens_from_chars(int(symbols_documented) * 256 + int(docs_indexed) * 128)


class TimedPhase:
    """Simple wall-clock timer for sync subtasks."""

    def __init__(self) -> None:
        self._t0 = time.perf_counter()
        self.elapsed_sec = 0.0

    def stop(self) -> float:
        self.elapsed_sec = time.perf_counter() - self._t0
        return self.elapsed_sec


"""Optional filesystem poller that marks pending-sync for freshness banners.

Stdlib-only (no watchdog dependency). Prefer commit/CI ingest for durable
index updates; this only surfaces stale banners until the next ingest.

**Batching (required):** agent coding can produce thousands of edits in seconds.
Changes are always coalesced — never one pending-sync POST/print per keystroke.
Flush when the tree has been quiet for ``--debounce`` seconds, or when
``--max-wait`` elapses since the first change in the open batch (whichever first).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


DEFAULT_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs"}
# Quiet period after last observed change before flushing a batch.
DEFAULT_DEBOUNCE_S = 30.0
# Ceiling: flush even if the agent is still writing (bursting).
DEFAULT_MAX_WAIT_S = 120.0
DEFAULT_POLL_S = 2.0


def snapshot(root: Path, extensions: set[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in extensions:
            continue
        parts = set(path.parts)
        if parts & {"node_modules", ".git", ".venv", "venv", "__pycache__", "dist", "build"}:
            continue
        try:
            out[str(path.resolve())] = path.stat().st_mtime
        except OSError:
            continue
    return out


def poll_once(
    root: Path,
    previous: dict[str, float],
    *,
    extensions: set[str],
) -> tuple[dict[str, float], list[str]]:
    current = snapshot(root, extensions)
    changed: list[str] = []
    for path, mtime in current.items():
        if previous.get(path) != mtime:
            changed.append(path)
    for path in previous:
        if path not in current:
            changed.append(path)
    return current, sorted(set(changed))


class ChangeBatcher:
    """Accumulate paths; flush only after debounce quiet or max_wait."""

    def __init__(self, *, debounce_s: float, max_wait_s: float) -> None:
        self.debounce_s = max(0.0, float(debounce_s))
        # Independent ceiling: may be shorter than debounce so continuous agent
        # bursts still flush periodically even while never "quiet".
        self.max_wait_s = max(0.0, float(max_wait_s))
        self._pending: set[str] = set()
        self._first_change_at: float | None = None
        self._last_change_at: float | None = None

    def add(self, paths: list[str], *, now: float | None = None) -> None:
        if not paths:
            return
        stamp = float(now if now is not None else time.time())
        if self._first_change_at is None:
            self._first_change_at = stamp
        self._last_change_at = stamp
        self._pending.update(paths)

    def ready(self, *, now: float | None = None) -> bool:
        if not self._pending or self._first_change_at is None or self._last_change_at is None:
            return False
        stamp = float(now if now is not None else time.time())
        quiet = stamp - self._last_change_at >= self.debounce_s
        aged = self.max_wait_s > 0 and stamp - self._first_change_at >= self.max_wait_s
        return quiet or aged

    def flush(self) -> list[str]:
        paths = sorted(self._pending)
        self._pending.clear()
        self._first_change_at = None
        self._last_change_at = None
        return paths

    @property
    def size(self) -> int:
        return len(self._pending)


def to_relative(root: Path, absolute: str) -> str:
    try:
        return str(Path(absolute).relative_to(root))
    except ValueError:
        return absolute


def emit_batch(root: Path, absolutes: list[str]) -> list[str]:
    rels = [to_relative(root, p) for p in absolutes]
    payload = {"batch_size": len(rels), "paths": rels}
    print(json.dumps(payload, sort_keys=True), flush=True)
    base = os.environ.get("ASTLOOM_CODE_GRAPH_URL", "").rstrip("/")
    if base and os.environ.get("ASTLOOM_PROJECT_ID") and rels:
        _post_pending_batch(base, rels)
    return rels


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Poll a tree and batch pending-sync marks. "
            "Never fires per keystroke — debounce + max-wait coalescing."
        )
    )
    parser.add_argument("--path", required=True, help="Directory to watch")
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_POLL_S,
        help=f"Poll interval seconds (default {DEFAULT_POLL_S})",
    )
    parser.add_argument(
        "--debounce",
        type=float,
        default=DEFAULT_DEBOUNCE_S,
        help=f"Quiet seconds before flushing a batch (default {DEFAULT_DEBOUNCE_S})",
    )
    parser.add_argument(
        "--max-wait",
        type=float,
        default=DEFAULT_MAX_WAIT_S,
        help=f"Max seconds to hold a batch while still changing (default {DEFAULT_MAX_WAIT_S})",
    )
    parser.add_argument("--once", action="store_true", help="Single poll delta, flush batch, exit")
    parser.add_argument(
        "--extensions",
        default=",".join(sorted(DEFAULT_EXTENSIONS)),
        help="Comma-separated extensions",
    )
    args = parser.parse_args(argv)
    root = Path(args.path).resolve()
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2
    extensions = {e if e.startswith(".") else f".{e}" for e in args.extensions.split(",") if e.strip()}
    batcher = ChangeBatcher(debounce_s=args.debounce, max_wait_s=args.max_wait)
    state = snapshot(root, extensions)
    if args.once:
        time.sleep(max(0.05, args.interval))
        state, changed = poll_once(root, state, extensions=extensions)
        batcher.add(changed)
        if batcher.size:
            # --once: flush immediately (batch already coalesced in one poll)
            emit_batch(root, batcher.flush())
        else:
            print(json.dumps({"batch_size": 0, "paths": []}, sort_keys=True), flush=True)
        return 0

    print(
        f"watching {root} poll={args.interval}s debounce={args.debounce}s "
        f"max_wait={args.max_wait}s (batched pending-sync; ctrl+c to stop)",
        flush=True,
    )
    try:
        while True:
            time.sleep(args.interval)
            state, changed = poll_once(root, state, extensions=extensions)
            batcher.add(changed)
            if batcher.ready():
                emit_batch(root, batcher.flush())
    except KeyboardInterrupt:
        if batcher.size:
            emit_batch(root, batcher.flush())
        return 0


def _post_pending_batch(base: str, file_paths: list[str]) -> None:
    try:
        import urllib.request

        project = os.environ["ASTLOOM_PROJECT_ID"]
        tenant = os.environ.get("ASTLOOM_TENANT_ID", "default")
        workspace = os.environ.get("ASTLOOM_WORKSPACE_ID", "default")
        url = f"{base}/api/v1/projects/{project}/graph/pending-sync"
        body = json.dumps({"file_paths": file_paths}).encode()
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Tenant-Id": tenant,
                "X-Workspace-Id": workspace,
            },
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10).read()
    except Exception as exc:  # noqa: BLE001
        print(f"warn: pending-sync batch post failed: {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())

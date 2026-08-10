"""Client NDJSON consumer for streaming ingest-push progress."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from typing import Any


def stream_accept_headers() -> dict[str, str]:
    return {"Accept": "application/x-ndjson"}


def consume_ndjson_ingest_push(
    *,
    lines: Iterable[str | bytes],
    on_progress: Callable[[dict[str, Any]], None],
    begin_phase: Callable[[], None] | None = None,
) -> dict[str, Any]:
    last_phase: str | None = None
    for raw in lines:
        text = (
            raw.strip()
            if isinstance(raw, str)
            else raw.decode("utf-8", errors="replace").strip()
        )
        if not text:
            continue
        try:
            obj = json.loads(text)
        except ValueError as exc:
            raise SystemExit(
                f"error: ingest-push stream: malformed line: {text[:200]}"
            ) from exc
        if not isinstance(obj, dict):
            raise SystemExit(f"error: ingest-push stream: malformed line: {text[:200]}")
        kind = obj.get("type")
        if kind == "progress":
            phase = obj.get("phase")
            if begin_phase and phase != last_phase and last_phase is not None:
                begin_phase()
            last_phase = phase
            event = {k: v for k, v in obj.items() if k != "type"}
            on_progress(event)
        elif kind == "result":
            return {k: v for k, v in obj.items() if k != "type"}
        elif kind == "error":
            raise SystemExit(
                f"error: ingest-push stream: {obj.get('message') or 'unknown'}"
            )
        else:
            raise SystemExit(f"error: ingest-push stream: unknown type {kind!r}")
    raise SystemExit("error: ingest-push stream ended without result")

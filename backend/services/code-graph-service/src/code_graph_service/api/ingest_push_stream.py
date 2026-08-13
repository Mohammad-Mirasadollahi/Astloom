"""NDJSON framing for streaming content-push ingest progress."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

from ..domain.errors import ClientDisconnected

PROGRESS = "progress"
RESULT = "result"
ERROR = "error"
# Keep the HTTPS stream alive while LiteLLM/embed work produces no file events.
# Client read timeout is idle-between-chunks; silence > that looks like a hang.
STREAM_HEARTBEAT_SEC = 15.0


def wants_ndjson_stream(*, accept: str | None, stream_query: str | None) -> bool:
    if (stream_query or "").strip() in {"1", "true", "yes"}:
        return True
    text = (accept or "").lower()
    return "application/x-ndjson" in text


def ndjson_line(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


Emit = Callable[[dict[str, Any] | None], None]


def build_progress_stream() -> tuple["asyncio.Queue[dict[str, Any] | None]", Emit]:
    """Event-loop queue plus a thread-safe ``emit`` for the worker thread.

    ``emit`` may only be called from the push worker thread (or the loop thread);
    it never blocks and never needs an executor thread. A ``None`` item is the
    stop sentinel. Must be called from inside the running event loop.
    """
    loop = asyncio.get_running_loop()
    q: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

    def emit(item: dict[str, Any] | None) -> None:
        try:
            loop.call_soon_threadsafe(q.put_nowait, item)
        except RuntimeError:
            # Loop already closed: the client is gone, there is nobody to deliver to.
            pass

    return q, emit


def heartbeat_event() -> dict[str, Any]:
    return {"type": PROGRESS, "phase": "ingest", "status": "heartbeat"}


async def iter_queue_with_heartbeat(
    q: "asyncio.Queue[dict[str, Any] | None]",
    *,
    heartbeat_sec: float | None = None,
):
    """Yield queue items; emit a progress heartbeat when the worker is silent."""
    interval = STREAM_HEARTBEAT_SEC if heartbeat_sec is None else float(heartbeat_sec)
    timeout = max(0.05, interval)
    while True:
        try:
            item = await asyncio.wait_for(q.get(), timeout=timeout)
        except asyncio.TimeoutError:
            yield heartbeat_event()
            continue
        if item is None:
            break
        yield item


def run_push_with_progress(emit: Emit, work: Callable[[], dict[str, Any]]) -> None:
    """Run ``work()`` and emit its terminal outcome, then a stop sentinel.

    ``work`` is responsible for emitting its own PROGRESS lines (via an
    ``on_progress`` hook wired by the caller). It should return the result
    payload on success or raise ``ClientDisconnected`` when cancelled mid-flight.
    """
    try:
        out = work()
        emit({"type": RESULT, **out})
    except ClientDisconnected as exc:
        emit({"type": ERROR, "message": str(exc.message or "cancelled during ingest-push")})
    except Exception as exc:  # noqa: BLE001 — surface any worker failure as an error line
        emit({"type": ERROR, "message": str(exc)[:500]})
    finally:
        emit(None)

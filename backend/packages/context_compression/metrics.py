"""Process-local compression counters (CLI / MCP stats)."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _Counters:
    calls: int = 0
    skipped: int = 0
    applied: int = 0
    lossy: int = 0
    original_chars: int = 0
    compressed_chars: int = 0
    by_content_type: dict[str, int] = field(default_factory=dict)


_LOCK = threading.Lock()
_COUNTERS = _Counters()


def record(result: Any) -> None:
    """Record one CompressResult into process counters."""
    with _LOCK:
        _COUNTERS.calls += 1
        orig = int(getattr(result, "original_chars", 0) or 0)
        comp = int(getattr(result, "compressed_chars", 0) or 0)
        _COUNTERS.original_chars += orig
        _COUNTERS.compressed_chars += comp
        if getattr(result, "skipped", False):
            _COUNTERS.skipped += 1
        else:
            _COUNTERS.applied += 1
        if getattr(result, "lossy", False):
            _COUNTERS.lossy += 1
        kind = str(getattr(result, "content_type", "") or "unknown")
        _COUNTERS.by_content_type[kind] = _COUNTERS.by_content_type.get(kind, 0) + 1


def reset() -> None:
    with _LOCK:
        global _COUNTERS
        _COUNTERS = _Counters()


def snapshot() -> dict[str, Any]:
    with _LOCK:
        saved = max(0, _COUNTERS.original_chars - _COUNTERS.compressed_chars)
        pct = (
            round(100.0 * saved / _COUNTERS.original_chars, 2)
            if _COUNTERS.original_chars
            else 0.0
        )
        return {
            "calls": _COUNTERS.calls,
            "skipped": _COUNTERS.skipped,
            "applied": _COUNTERS.applied,
            "lossy": _COUNTERS.lossy,
            "original_chars": _COUNTERS.original_chars,
            "compressed_chars": _COUNTERS.compressed_chars,
            "chars_saved": saved,
            "pct_saved": pct,
            "by_content_type": dict(_COUNTERS.by_content_type),
        }

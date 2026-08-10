"""Tiny in-process sliding-window rate limiter for connect auth endpoints."""

from __future__ import annotations

import time
from collections import defaultdict, deque


class InProcessRateLimiter:
    """Allow up to ``max_events`` per ``window_seconds`` for each key."""

    def __init__(self, *, max_events: int, window_seconds: float = 60.0) -> None:
        self._max_events = max_events
        self._window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self._window_seconds:
            hits.popleft()
        if len(hits) >= self._max_events:
            return False
        hits.append(now)
        return True

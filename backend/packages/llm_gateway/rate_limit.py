"""RPM session gate: sliding-window starts + in-flight tracking for LiteLLM."""

from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

HISTORY_SIZE = 100
SessionKind = Literal["complete", "embed"]
SessionStatus = Literal["in_flight", "ok", "error", "cancelled"]


def _wall_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


@dataclass
class RpmSession:
    session_id: str
    kind: SessionKind
    model: str
    started_at_wall: str
    started_at_mono: float
    status: SessionStatus = "in_flight"
    waited_sec: float = 0.0
    ended_at_wall: str | None = None
    ended_at_mono: float | None = None
    error_detail: str | None = None
    correlation_id: str | None = None
    file_path: str | None = None
    symbol_id: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "kind": self.kind,
            "model": self.model,
            "started_at": self.started_at_wall,
            "ended_at": self.ended_at_wall,
            "status": self.status,
            "waited_sec": round(self.waited_sec, 3),
            "error_detail": self.error_detail,
            "correlation_id": self.correlation_id,
            "file_path": self.file_path,
            "symbol_id": self.symbol_id,
        }


@dataclass
class SessionMeta:
    model: str = ""
    correlation_id: str | None = None
    file_path: str | None = None
    symbol_id: str | None = None


class RpmSessionGate:
    """Allow at most `rpm` starts per rolling minute and `inflight_cap` concurrent sessions."""

    def __init__(
        self,
        rpm: int,
        *,
        inflight_cap: int | None = None,
        history_size: int = HISTORY_SIZE,
        clock: Any | None = None,
    ) -> None:
        if rpm < 1:
            raise ValueError("rpm must be >= 1")
        cap = rpm if inflight_cap is None else int(inflight_cap)
        if cap < 1:
            raise ValueError("inflight_cap must be >= 1")
        self.rpm = rpm
        self.inflight_cap = cap
        self._timestamps: list[float] = []
        self._inflight: dict[str, RpmSession] = {}
        self._history: deque[RpmSession] = deque(maxlen=max(1, int(history_size)))
        self._lock = threading.Lock()
        self._capacity_changed = threading.Condition(self._lock)
        self._clock = clock or time.monotonic

    def acquire(self, kind: SessionKind = "complete", meta: SessionMeta | None = None) -> RpmSession:
        """Block until a slot is available; return an in-flight session."""
        meta = meta or SessionMeta()
        waited = 0.0
        t_wait0 = float(self._clock())
        with self._capacity_changed:
            while True:
                now = float(self._clock())
                self._prune(now)
                if len(self._timestamps) < self.rpm and len(self._inflight) < self.inflight_cap:
                    self._timestamps.append(now)
                    waited = max(0.0, now - t_wait0)
                    session = RpmSession(
                        session_id=uuid.uuid4().hex,
                        kind=kind,
                        model=meta.model or "",
                        started_at_wall=_wall_now(),
                        started_at_mono=now,
                        waited_sec=waited,
                        correlation_id=meta.correlation_id,
                        file_path=meta.file_path,
                        symbol_id=meta.symbol_id,
                    )
                    self._inflight[session.session_id] = session
                    return session
                timeout = self._wait_timeout(now)
                self._capacity_changed.wait(timeout=timeout)

    def release(
        self,
        session: RpmSession,
        status: SessionStatus = "ok",
        *,
        error_detail: str | None = None,
        model: str | None = None,
    ) -> None:
        if status == "in_flight":
            raise ValueError("release status must be terminal")
        with self._capacity_changed:
            current = self._inflight.pop(session.session_id, None)
            if current is None:
                return
            now = float(self._clock())
            current.status = status
            current.ended_at_mono = now
            current.ended_at_wall = _wall_now()
            if error_detail:
                current.error_detail = str(error_detail)[:500]
            if model:
                current.model = model
            self._history.appendleft(current)
            self._capacity_changed.notify_all()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            now = float(self._clock())
            self._prune(now)
            return {
                "rpm": self.rpm,
                "inflight_cap": self.inflight_cap,
                "starts_in_window": len(self._timestamps),
                "inflight_count": len(self._inflight),
                "inflight": [s.to_public_dict() for s in self._inflight.values()],
                "history": [s.to_public_dict() for s in self._history],
            }

    def _prune(self, now: float) -> None:
        cutoff = now - 60.0
        self._timestamps = [t for t in self._timestamps if t > cutoff]

    def _wait_timeout(self, now: float) -> float:
        if self._timestamps and len(self._timestamps) >= self.rpm:
            return max(0.01, 60.0 - (now - self._timestamps[0]))
        return 0.05


# Backward-compatible alias for imports/tests that still say RpmLimiter.
RpmLimiter = RpmSessionGate

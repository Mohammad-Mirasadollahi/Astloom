"""Adaptive sync progress tracker."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from astloom_cli.sync_progress.constants import (
    BLEND_EWMA_ALPHA,
    DEFAULT_INTERVAL_SEC,
    EARLY_RATE_AFTER_SEC,
    SAMPLE_KEEP_SEC,
)
from astloom_cli.sync_progress.formatters import wall_clock_now
from astloom_cli.sync_progress.rate import estimate_rate
from astloom_cli.sync_progress.render import print_progress_line
from astloom_cli.sync_progress.store import clear_snapshot, progress_path, write_snapshot


@dataclass
class SyncProgressTracker:
    """Adaptive progress reporter for astloom sync."""

    scope: str
    path: str
    interval_sec: float = DEFAULT_INTERVAL_SEC
    progress_file: Path | None = None
    _t0: float = field(default_factory=lambda: time.monotonic())
    _last_print: float = 0.0
    _last_pct_printed: float = -1.0
    _samples: list[tuple[float, int]] = field(default_factory=list)
    _ewma_rate: float | None = None  # files / second (smoothed blend)
    _rate_basis: str = ""
    _latest: dict[str, Any] = field(default_factory=dict)
    _finished: bool = False
    _had_rate: bool = False
    _lock: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        import threading

        if self.progress_file is None:
            self.progress_file = progress_path()
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)
        object.__setattr__(self, "_lock", threading.Lock())

    def __call__(self, event: dict[str, Any]) -> None:
        self.update(event)

    def begin_phase(self) -> None:
        """Reset rate/ETA samples for a new sync phase (e.g. code → docs)."""
        with self._lock:
            self._t0 = time.monotonic()
            self._last_print = 0.0
            self._last_pct_printed = -1.0
            self._samples.clear()
            self._ewma_rate = None
            self._rate_basis = ""
            self._latest = {}
            self._finished = False
            self._had_rate = False

    def update(self, event: dict[str, Any]) -> None:
        with self._lock:
            self._update_unlocked(event)

    def update_sessions(self, sessions: dict[str, Any]) -> None:
        with self._lock:
            if not self._latest:
                return
            now = time.monotonic()
            sessions_changed = self._latest.get("llm_sessions") != sessions
            due = (now - self._last_print) >= self.interval_sec
            need_early_rate = (
                not self._had_rate
                and (now - self._t0) >= EARLY_RATE_AFTER_SEC
            )
            # Unchanged sessions: still refresh ETA/rate on interval, and once
            # when the early provisional rate becomes available.
            if not sessions_changed and not due and not need_early_rate:
                return
            event = dict(self._latest)
            event.update(
                {
                    "rpm": int(sessions.get("rpm") or 0),
                    "rpm_inflight_cap": int(sessions.get("inflight_cap") or 0),
                    "rpm_inflight": int(sessions.get("inflight_count") or 0),
                    "rpm_starts_in_window": int(sessions.get("starts_in_window") or 0),
                    "llm_sessions": dict(sessions),
                }
            )
            self._update_unlocked(event)

    def _update_unlocked(self, event: dict[str, Any]) -> None:
        event = dict(event)
        previous_sessions = self._latest.get("llm_sessions")
        previous_status = str(self._latest.get("status") or "")
        previous_phase = str(self._latest.get("phase") or "")
        if "llm_sessions" not in event and isinstance(previous_sessions, dict):
            event["llm_sessions"] = dict(previous_sessions)
            event.setdefault("rpm", int(previous_sessions.get("rpm") or 0))
            event.setdefault(
                "rpm_inflight_cap",
                int(previous_sessions.get("inflight_cap") or 0),
            )
            event.setdefault(
                "rpm_inflight",
                int(previous_sessions.get("inflight_count") or 0),
            )
            event.setdefault(
                "rpm_starts_in_window",
                int(previous_sessions.get("starts_in_window") or 0),
            )
        now = time.monotonic()
        done = int(event.get("done") or 0)
        total = max(int(event.get("total") or 0), 0)
        in_flight = int(event.get("files_in_flight") or 0)
        status = str(event.get("status") or "")
        phase = str(event.get("phase") or "")
        # New phase (code → embeddings/docs): reset ETA samples so percent/rate
        # are not blended with the previous phase's counters.
        if phase and previous_phase and phase != previous_phase:
            self._t0 = now
            self._last_print = 0.0
            self._last_pct_printed = -1.0
            self._samples.clear()
            self._ewma_rate = None
            self._rate_basis = ""
            self._had_rate = False
            self._finished = False
        self._latest = event
        self._samples.append((now, done))
        cutoff = now - SAMPLE_KEEP_SEC
        self._samples = [s for s in self._samples if s[0] >= cutoff]

        estimated = estimate_rate(
            self._samples,
            t0=self._t0,
            now=now,
            done=done,
            in_flight=in_flight,
            total=total,
            interval_sec=self.interval_sec,
        )
        if estimated is not None:
            rate, basis = estimated
            if rate > 0:
                if self._ewma_rate is None:
                    self._ewma_rate = rate
                else:
                    self._ewma_rate = (
                        BLEND_EWMA_ALPHA * rate
                        + (1.0 - BLEND_EWMA_ALPHA) * self._ewma_rate
                    )
                self._rate_basis = basis

        # Rate/ETA stay file-completion based. Display percent also half-credits
        # in-flight files so the bar moves while workers wait on LLM/embed/RPM
        # (otherwise 0% can sit unchanged for many minutes with full parallelism).
        pct = (100.0 * done / total) if total else 0.0
        if total > 0 and in_flight > 0 and done < total:
            display_done = min(float(total), float(done) + 0.5 * float(in_flight))
            pct = 100.0 * display_done / float(total)
        elapsed = now - self._t0
        eta = None
        remaining = max(total - done, 0)
        if self._ewma_rate and self._ewma_rate > 0 and remaining > 0:
            eta = remaining / self._ewma_rate

        snapshot = {
            "active": status not in {"finished", "cancelled"},
            "scope": self.scope,
            "path": self.path,
            "phase": event.get("phase"),
            "status": status,
            "done": done,
            "total": total,
            "percent": round(pct, 1),
            "elapsed_sec": round(elapsed, 1),
            "eta_sec": None if eta is None else round(eta, 1),
            "files_per_sec": None if not self._ewma_rate else round(self._ewma_rate, 3),
            "rate_basis": self._rate_basis or None,
            "file": event.get("file") or "",
            "symbols_indexed": int(event.get("symbols_indexed") or 0),
            "edges_written": int(event.get("edges_written") or 0),
            "approx_tokens": int(event.get("approx_tokens") or 0),
            "chars_read": int(event.get("chars_read") or 0),
            "docs_indexed": int(event.get("docs_indexed") or 0),
            "links_created": int(event.get("links_created") or 0),
            "anchors_registered": int(event.get("anchors_registered") or 0),
            "files_in_flight": in_flight,
            "files_in_flight_paths": list(event.get("files_in_flight_paths") or [])[:8],
            "file_workers": int(event.get("file_workers") or 0),
            "prior_indexed": int(event.get("prior_indexed") or 0),
            "queue_new": int(event.get("queue_new") or 0),
            "queue_changed": int(event.get("queue_changed") or 0),
            "queue_unchanged": int(event.get("queue_unchanged") or 0),
            "embeddings_refreshed": int(event.get("embeddings_refreshed") or 0),
            "rpm": int(event.get("rpm") or 0),
            "rpm_inflight_cap": int(event.get("rpm_inflight_cap") or 0),
            "rpm_inflight": int(event.get("rpm_inflight") or 0),
            "rpm_starts_in_window": int(event.get("rpm_starts_in_window") or 0),
            "llm_sessions": dict(event.get("llm_sessions") or {}),
            "pid": os.getpid(),
            "updated_at": time.time(),
            "logged_at": wall_clock_now(),
        }
        self._write(snapshot)

        if status in {"finished", "cancelled"}:
            self._finished = True

        # Empty queue (noop): keep snapshot for live readers, no 0/0 theater —
        # except pre-queue warmup statuses so the console is not silent for minutes.
        pre_queue = status in {"preparing", "discovering", "loading"}
        if total == 0 and not pre_queue:
            return

        # Force only on status *transition* into start/finish/cancel/prep — not every
        # RPM session poll while status remains "started"/"finished".
        milestone = status in {
            "started",
            "finished",
            "cancelled",
            "preparing",
            "discovering",
            "loading",
            "finalizing",
        }
        force = (milestone and status != previous_status) or (
            pct >= 100.0 and self._last_pct_printed < 100.0
        )
        # Terminal statuses: keep the snapshot file fresh, but do not reprint the same
        # finished/cancelled block every progress_interval (looks hung while later phases
        # like embedding_refresh still run).
        if status in {"finished", "cancelled"} and status == previous_status and not force:
            return
        due = (now - self._last_print) >= self.interval_sec
        rate_became_available = bool(self._ewma_rate) and not self._had_rate
        if self._ewma_rate:
            self._had_rate = True
        if not (force or due or rate_became_available):
            return
        self._last_print = now
        self._last_pct_printed = pct
        print_progress_line(snapshot)

    def finish(self, *, cancelled: bool = False) -> None:
        with self._lock:
            if self._finished:
                self.clear()
                return
            if self._latest:
                event = dict(self._latest)
                if cancelled:
                    event["status"] = "cancelled"
                    # Keep real done count — do not jump to 100% on Ctrl+C.
                else:
                    event["status"] = "finished"
                    event["done"] = int(event.get("total") or event.get("done") or 0)
                self._update_unlocked(event)
            self.clear()

    def clear(self) -> None:
        clear_snapshot(self.progress_file)

    def _write(self, snapshot: dict[str, Any]) -> None:
        assert self.progress_file is not None
        write_snapshot(self.progress_file, snapshot)

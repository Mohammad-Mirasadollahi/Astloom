"""Adaptive file-completion rate for sync ETA."""

from __future__ import annotations

from astloom_cli.sync_progress.constants import (
    EARLY_RATE_AFTER_SEC,
    LIFETIME_WEIGHT,
    MIN_DONE_FOR_LIFETIME,
    RECENT_WEIGHT,
    RECENT_WINDOW_SEC,
)


def lifetime_rate(*, t0: float, now: float, done: int) -> float | None:
    if done < MIN_DONE_FOR_LIFETIME:
        return None
    elapsed = now - t0
    if elapsed < 0.5:
        return None
    return done / elapsed


def recent_rate(
    samples: list[tuple[float, int]],
    *,
    now: float,
    done: int,
    interval_sec: float,
) -> float | None:
    if done <= 0:
        return None
    window = max(RECENT_WINDOW_SEC, float(interval_sec))
    # Oldest sample still inside the recent window (or just outside for Δ).
    older = [(t, d) for t, d in samples if now - t >= min(window, 5.0)]
    if not older:
        return None
    t0, d0 = older[0]
    dt = now - t0
    dd = done - d0
    if dt <= 0 or dd <= 0:
        return None
    return dd / dt


def estimate_rate(
    samples: list[tuple[float, int]],
    *,
    t0: float,
    now: float,
    done: int,
    in_flight: int = 0,
    total: int = 0,
    interval_sec: float,
) -> tuple[float, str] | None:
    """Return ``(files_per_sec, basis)`` for ETA.

    Prefer a **blend of lifetime average and recent-window average** once
    files have finished (stable against one slow file, still tracks sustained
    slowdowns). Before any completion, use a conservative provisional pace.
    """
    elapsed = now - t0
    lifetime = lifetime_rate(t0=t0, now=now, done=done)
    recent = recent_rate(samples, now=now, done=done, interval_sec=interval_sec)

    if lifetime is not None and recent is not None:
        blended = LIFETIME_WEIGHT * lifetime + RECENT_WEIGHT * recent
        return blended, "avg+recent"
    if lifetime is not None:
        return lifetime, "avg"
    if recent is not None:
        return recent, "recent"

    if elapsed < EARLY_RATE_AFTER_SEC or total <= 0:
        return None
    # Provisional only while nothing has finished yet.
    active = max(int(in_flight), 1)
    return active / elapsed, "provisional"

"""Formatting helpers for sync progress display."""

from __future__ import annotations


def wall_clock_now() -> str:
    """Local wall clock to the second: ``YYYY-MM-DD HH:MM:SS``."""
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format_duration(seconds: float) -> str:
    sec = max(0, int(seconds))
    if sec < 60:
        return f"{sec}s"
    minutes, rem = divmod(sec, 60)
    if minutes < 60:
        return f"{minutes}m {rem}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def format_bar(pct: float, *, width: int = 24) -> str:
    pct = max(0.0, min(100.0, pct))
    filled = int(round(width * pct / 100.0))
    return "[" + ("#" * filled) + ("-" * (width - filled)) + "]"

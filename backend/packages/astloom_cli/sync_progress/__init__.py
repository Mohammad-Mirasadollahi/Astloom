"""Live sync progress: percent, ETA, adaptive rate, status snapshot file.

Public API stays importable as ``astloom_cli.sync_progress``.
"""

from __future__ import annotations

from astloom_cli.sync_progress.constants import (
    DEFAULT_INTERVAL_SEC,
    PROGRESS_FILENAME,
)
from astloom_cli.sync_progress.formatters import format_bar, format_duration, wall_clock_now
from astloom_cli.sync_progress.store import progress_path, read_live_progress
from astloom_cli.sync_progress.tracker import SyncProgressTracker

__all__ = [
    "DEFAULT_INTERVAL_SEC",
    "PROGRESS_FILENAME",
    "SyncProgressTracker",
    "format_bar",
    "format_duration",
    "progress_path",
    "read_live_progress",
    "wall_clock_now",
]

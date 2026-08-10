"""Live sync progress constants."""

from __future__ import annotations

PROGRESS_FILENAME = "sync-progress.json"
DEFAULT_INTERVAL_SEC = 30.0
# Start showing rate/ETA within the first 10s even if no file has finished yet.
EARLY_RATE_AFTER_SEC = 5.0
SAMPLE_KEEP_SEC = 180.0
# Recent window for adaptive pace (resists single slow files less than pure instant).
RECENT_WINDOW_SEC = 60.0
# Blend: favor lifetime avg for stability; recent pulls ETA when pace sustains a change.
LIFETIME_WEIGHT = 0.65
RECENT_WEIGHT = 0.35
# Light EWMA on the blended rate so printed ETA does not jump every tick.
BLEND_EWMA_ALPHA = 0.22
# Need a few completions before trusting lifetime over provisional.
MIN_DONE_FOR_LIFETIME = 1

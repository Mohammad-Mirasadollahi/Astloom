"""Shared constants for sanitization and retrieval heuristics."""

from __future__ import annotations

import re

SECRET = re.compile(r"(?i)((?:api[_-]?key|token|password|secret)\s*[:=]\s*)([^\s,;]+)")
HISTORY_TERMS = {
    "history",
    "historical",
    "audit",
    "past",
    "previous",
    "timeline",
    "root-cause",
    "migration",
}

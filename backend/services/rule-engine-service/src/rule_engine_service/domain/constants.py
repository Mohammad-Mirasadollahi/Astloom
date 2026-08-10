"""Shared constants for rule matching and redaction."""

from __future__ import annotations

import re

SENSITIVE_DOMAINS = {"revenue", "security", "compliance", "production", "auth", "billing"}
TASK_TRIGGERS = {"api", "schema", "contract", "migration", "route"}
SECRET = re.compile(r"(?i)((?:api[_-]?key|token|password|secret)\s*[:=]\s*)([^\s,;]+)")

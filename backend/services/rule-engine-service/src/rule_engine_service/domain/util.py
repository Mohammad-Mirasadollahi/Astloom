"""Small pure helpers for rule-engine domain / application."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import json
import re
from typing import Any

from .constants import SECRET
from .enums import Severity


def now() -> str:
    return datetime.now(UTC).isoformat()


def sanitize(value: Any) -> Any:
    if isinstance(value, str):
        return SECRET.sub(r"\1[REDACTED]", value)
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize(item) for key, item in value.items()}
    return value


def digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return sha256(encoded).hexdigest()


def tokenize(value: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9_-]*", value.lower())


def severity_score(severity: Severity) -> float:
    return {Severity.LOW: 0.25, Severity.MEDIUM: 0.5, Severity.HIGH: 0.75, Severity.CRITICAL: 1.0}[severity]

"""Pure helpers: hashing, redaction, timestamps, severity."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import json
import re
from typing import Any

from .enums import Severity
from .models import CodeSymbol

CRITICAL_TAGS = {"auth", "authorization", "security", "billing", "pricing"}
HIGH_TAGS = {"api", "route", "schema", "contract", "migration", "public"}
SECRET = re.compile(r"(?i)((?:api[_-]?key|token|password|secret)\s*[:=]\s*)([^\s,;]+)")


def severity_for(symbol: CodeSymbol) -> Severity:
    tags = {tag.lower() for tag in symbol.tags} | {symbol.kind.lower()}
    if tags & CRITICAL_TAGS:
        return Severity.CRITICAL
    if tags & HIGH_TAGS:
        return Severity.HIGH
    if not symbol.doc_required:
        return Severity.LOW
    return Severity.MEDIUM


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


def normalize_source(value: str) -> str:
    """Drop formatting noise while preserving control-flow tokens."""
    without_block = re.sub(r"/\*.*?\*/", "", value, flags=re.S)
    without_line = re.sub(r"#.*$|//.*$", "", without_block, flags=re.M)
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|[0-9]+|[(){}\[\].,=:<>!&|+*/%-]", without_line)
    return " ".join(tokens)

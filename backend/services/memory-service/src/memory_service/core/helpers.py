"""Pure helpers for timestamps, sanitization, and text scoring inputs."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import json
import re
from typing import Any

from .constants import SECRET
from .enums import QuestionState
from .errors import ValidationError


def now() -> str:
    return datetime.now(UTC).isoformat()


def parse_timestamp(value: str) -> datetime:
    text = str(value).strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def normalize_optional_timestamp(value: Any, field: str) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return parse_timestamp(str(value)).isoformat()
    except ValueError as exc:
        raise ValidationError(f"{field} must be an ISO-8601 timestamp") from exc


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


def tokenize(value: str) -> set[str]:
    return {part for part in re.findall(r"[a-z0-9][a-z0-9_-]*", value.lower()) if len(part) > 1}


def normalize_question(value: str) -> str:
    normalized = " ".join(re.findall(r"[a-z0-9][a-z0-9_-]*", value.lower()))
    if not normalized:
        raise ValidationError("question is required")
    return normalized


def slug(value: str) -> str:
    return "-".join(sorted(tokenize(value)))[:80] or "unspecified"


def estimate_tokens(value: str) -> int:
    return max(1, len(value.split()))


def documentation_outcome(state: QuestionState) -> str:
    return {
        QuestionState.DRAFT_GENERATED: "documentation_draft",
        QuestionState.SEARCHING: "task",
        QuestionState.BLOCKED_BY_GAP: "knowledge_gap",
    }.get(state, state.value)

from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from binascii import Error as BinasciiError
from datetime import UTC, datetime
from hashlib import sha256
import json
import re
from typing import Any
from urllib.parse import urlsplit

from .enums import TicketState
from .errors import ValidationError
from .models import ExternalTicket

SECRET = re.compile(r"(?i)((?:api[_-]?key|token|password|secret)\s*[:=]\s*)([^\s,;]+)")


def channel_for(intent: str, domain: str) -> str:
    if intent in {"API_READY", "DOC_DRIFT_FOUND"}:
        return "ide.notifications"
    if intent in {"CODE_RELEASED", "DEPLOYMENT_COMPLETED", "DOWNSTREAM_TASK_REQUESTED"}:
        return "department.workflows"
    if intent.startswith("TASK_"):
        return "agent.tasks"
    return f"domain.{domain}"


def nested(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def normalize_status_map(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValidationError("status_map must be an object")
    normalized: dict[str, str] = {}
    for key, mapped in value.items():
        source = str(key).strip()
        target = str(mapped).strip()
        if not source or not target:
            continue
        try:
            TicketState(target)
        except ValueError as exc:
            raise ValidationError(f"status_map target {target!r} is not a portable ticket status") from exc
        normalized[source] = target
    return normalized


def bounded_text(value: Any, field: str, max_length: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > max_length:
        raise ValidationError(f"{field} exceeds {max_length} characters")
    return text


def normalize_timestamp(value: Any, field: str, *, required: bool) -> str | None:
    if value is None or str(value).strip() == "":
        if required:
            raise ValidationError(f"{field} is required")
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValidationError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValidationError(f"{field} must include a timezone")
    return parsed.astimezone(UTC).isoformat()


def normalize_remote_url(value: Any) -> str | None:
    text = bounded_text(value, "remote_url", 2048)
    if text is None:
        return None
    parsed = urlsplit(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError("remote_url must use http or https")
    if parsed.username or parsed.password or sanitize(text) != text:
        raise ValidationError("remote_url must not contain credentials")
    return text


def encode_ticket_page_token(ticket: ExternalTicket) -> str:
    payload = json.dumps([ticket.updated_at, ticket.id], separators=(",", ":")).encode()
    return urlsafe_b64encode(payload).decode()


def decode_ticket_page_token(token: str) -> tuple[str, str]:
    try:
        payload = json.loads(urlsafe_b64decode(token.encode()).decode())
    except (BinasciiError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("invalid page_token") from exc
    if not isinstance(payload, list) or len(payload) != 2 or not all(isinstance(item, str) and item for item in payload):
        raise ValidationError("invalid page_token")
    normalize_timestamp(payload[0], "page_token", required=True)
    return payload[0], payload[1]


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

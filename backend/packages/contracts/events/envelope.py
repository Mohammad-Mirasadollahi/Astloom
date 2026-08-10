"""Minimal outbox / broker event envelope helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

# Common across core-data / memory / docs-sync outbox emits, plus HLD scope ids.
# Services today often emit `event_version`; this contract standardizes on `schema_version`.
REQUIRED_ENVELOPE_FIELDS = (
    "event_id",
    "event_type",
    "schema_version",
    "occurred_at",
    "correlation_id",
    "tenant_id",
    "workspace_id",
    "project_id",
    "payload",
)


def make_event_envelope(
    *,
    event_type: str,
    correlation_id: str,
    tenant_id: str,
    workspace_id: str,
    project_id: str,
    payload: dict[str, Any] | None = None,
    schema_version: str | int = 1,
    event_id: str | None = None,
    occurred_at: str | None = None,
    producer: str | None = None,
) -> dict[str, Any]:
    envelope: dict[str, Any] = {
        "event_id": event_id or str(uuid4()),
        "event_type": event_type,
        "schema_version": schema_version,
        "occurred_at": occurred_at or datetime.now(UTC).isoformat(),
        "correlation_id": correlation_id,
        "tenant_id": tenant_id,
        "workspace_id": workspace_id,
        "project_id": project_id,
        "payload": dict(payload or {}),
    }
    if producer is not None:
        envelope["producer"] = producer
    return envelope


def validate_event_envelope(payload: dict[str, Any]) -> list[str]:
    if not isinstance(payload, dict):
        return ["event envelope must be an object"]
    # Accept legacy service emits that use event_version instead of schema_version.
    if "schema_version" not in payload and "event_version" in payload:
        payload = {**payload, "schema_version": payload["event_version"]}
    errors: list[str] = []
    for field in REQUIRED_ENVELOPE_FIELDS:
        if field not in payload:
            errors.append(f"missing {field}")
    if "payload" in payload and not isinstance(payload.get("payload"), dict):
        errors.append("payload must be an object")
    for field in (
        "event_id",
        "event_type",
        "occurred_at",
        "correlation_id",
        "tenant_id",
        "workspace_id",
        "project_id",
    ):
        if field in payload and not str(payload.get(field) or "").strip():
            errors.append(f"{field} must be a non-empty string")
    if "schema_version" in payload and payload.get("schema_version") in (None, ""):
        errors.append("schema_version is required")
    return errors

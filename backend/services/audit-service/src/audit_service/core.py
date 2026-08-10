from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4


class AuditError(Exception):
    def __init__(self, code: str, category: str, message: str):
        super().__init__(message)
        self.code, self.category, self.message = code, category, message


class ValidationError(AuditError):
    def __init__(self, message: str):
        super().__init__("validation_error", "validation_error", message)


class ConflictError(AuditError):
    def __init__(self, message: str):
        super().__init__("conflict_error", "conflict_error", message)


class NotFoundError(AuditError):
    def __init__(self, message: str):
        super().__init__("not_found", "not_found_error", message)


@dataclass(frozen=True)
class Scope:
    tenant_id: str
    workspace_id: str
    project_id: str

    def __post_init__(self) -> None:
        if not all((self.tenant_id.strip(), self.workspace_id.strip(), self.project_id.strip())):
            raise ValidationError("tenant_id, workspace_id, and project_id are required")


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"

class Store(Protocol):
    def begin_idempotency(self, scope: Scope, key: str, resource: str) -> str | None: ...
    def complete_idempotency(self, scope: Scope, key: str, resource: str, resource_id: str) -> None: ...
    def append_event(self, event: dict[str, Any]) -> None: ...
    def put_audit_event(self, event: dict[str, Any]) -> None: ...
    def list_audit_events(self, scope: Scope, correlation_id: str | None = None) -> list[dict[str, Any]]: ...
    def get_audit_event(self, event_id: str, scope: Scope) -> dict[str, Any]: ...


class AuditService:
    def __init__(self, store: Store):
        self.store = store

    def record_event(
        self,
        scope: Scope,
        actor_id: str,
        correlation_id: str,
        idempotency_key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        action = str(payload.get("action") or "").strip()
        entity_ref = str(payload.get("entity_ref") or "").strip()
        evidence_refs = payload.get("evidence_refs") or []
        if not action or not entity_ref:
            raise ValidationError("action and entity_ref are required")
        if not isinstance(evidence_refs, list):
            raise ValidationError("evidence_refs must be a list")
        existing = self.store.begin_idempotency(scope, idempotency_key, "audit_event")
        if existing:
            return self.store.get_audit_event(existing, scope)
        event_id = _new_id("aud")
        event = {
            "id": event_id,
            "tenant_id": scope.tenant_id,
            "workspace_id": scope.workspace_id,
            "project_id": scope.project_id,
            "actor_id": actor_id,
            "correlation_id": correlation_id,
            "action": action,
            "entity_ref": entity_ref,
            "evidence_refs": list(evidence_refs),
            "details": dict(payload.get("details") or {}),
            "created_at": _now(),
            "immutable": True,
        }
        self.store.put_audit_event(event)
        self.store.complete_idempotency(scope, idempotency_key, "audit_event", event_id)
        self.store.append_event({"event_type": "audit.recorded", "event_id": event_id, "correlation_id": correlation_id})
        return event

    def timeline(self, scope: Scope, correlation_id: str) -> list[dict[str, Any]]:
        if not correlation_id.strip():
            raise ValidationError("correlation_id is required")
        return self.store.list_audit_events(scope, correlation_id=correlation_id)

    def get_event(self, scope: Scope, event_id: str) -> dict[str, Any]:
        return self.store.get_audit_event(event_id, scope)

    def evidence_trail(self, scope: Scope, entity_ref: str) -> list[dict[str, Any]]:
        """Immutable evidence trail for one entity within project scope."""
        if not entity_ref.strip():
            raise ValidationError("entity_ref is required")
        events = self.store.list_audit_events(scope)
        return [e for e in events if e.get("entity_ref") == entity_ref]

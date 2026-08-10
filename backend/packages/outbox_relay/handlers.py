from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import uuid4

from .types import utc_now


@dataclass(frozen=True)
class HandlerResult:
    handler: str
    ok: bool
    detail: str = ""


class RelayHandler(Protocol):
    name: str

    def handle(self, event: dict[str, Any], *, source: str) -> HandlerResult: ...


CORE_DATA_MEMORY_EVENTS = frozenset(
    {
        "activity.recorded",
        "worklog.created",
        "decision.created",
        "issue.discovered",
        "task.created",
    }
)


class MemoryFromCoreDataHandler:
    """Create candidate semantic memory from core-data create/activity events."""

    name = "memory_from_core_data"

    def __init__(self, memory_service: Any) -> None:
        self._memory = memory_service

    def handle(self, event: dict[str, Any], *, source: str) -> HandlerResult:
        if source != "core-data":
            return HandlerResult(self.name, True, "skipped:not-core-data")
        event_type = str(event.get("event_type") or "")
        if event_type not in CORE_DATA_MEMORY_EVENTS:
            return HandlerResult(self.name, True, f"skipped:{event_type}")
        scope_ids = _scope(event)
        if scope_ids is None:
            return HandlerResult(self.name, False, "missing scope")
        from memory_service.core import Scope

        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        title = str(data.get("title") or payload.get("title") or event_type)
        body = _memory_body(event_type, payload)
        key = f"outbox-memory:{event.get('event_id')}"
        self._memory.create_memory(
            Scope(*scope_ids),
            str(event.get("actor_ref") or "outbox-relay"),
            str(event.get("correlation_id") or event.get("event_id") or uuid4()),
            key,
            {
                "kind": "semantic",
                "state": "candidate",
                "title": title[:200],
                "body": body,
                "tags": ["outbox", "core-data", event_type],
                "evidence_refs": list(event.get("evidence_refs") or [])
                or [f"event:{event.get('event_id')}"],
                "source_refs": [f"core-data:{payload.get('id') or event.get('causation_id') or ''}"],
                "confidence": 0.7,
            },
        )
        return HandlerResult(self.name, True, "memory-created")


class AuditMirrorHandler:
    """Mirror every relayed event into audit-service for compliance trail."""

    name = "audit_mirror"

    def __init__(self, audit_service: Any) -> None:
        self._audit = audit_service

    def handle(self, event: dict[str, Any], *, source: str) -> HandlerResult:
        scope_ids = _scope(event)
        if scope_ids is None:
            return HandlerResult(self.name, False, "missing scope")
        from audit_service.core import Scope

        event_id = str(event.get("event_id") or "")
        event_type = str(event.get("event_type") or "unknown")
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        entity_ref = str(payload.get("id") or event.get("causation_id") or event_id or "unknown")
        self._audit.record_event(
            Scope(*scope_ids),
            str(event.get("actor_ref") or "outbox-relay"),
            str(event.get("correlation_id") or event_id or uuid4()),
            f"outbox-audit:{event_id}",
            {
                "action": f"outbox.{source}.{event_type}",
                "entity_ref": entity_ref,
                "evidence_refs": list(event.get("evidence_refs") or []) or [f"event:{event_id}"],
                "details": {
                    "source": source,
                    "event_type": event_type,
                    "producer": event.get("producer") or event.get("source"),
                },
            },
        )
        return HandlerResult(self.name, True, "audit-recorded")


class BrokerForwardHandler:
    """Publish core-data activity/task events onto the adapter broker channel."""

    name = "broker_forward"

    def __init__(self, adapter_service: Any) -> None:
        self._adapter = adapter_service

    def handle(self, event: dict[str, Any], *, source: str) -> HandlerResult:
        if source != "core-data":
            return HandlerResult(self.name, True, "skipped:not-core-data")
        event_type = str(event.get("event_type") or "")
        intent = _intent_for(event_type)
        if intent is None:
            return HandlerResult(self.name, True, f"skipped:{event_type}")
        scope_ids = _scope(event)
        if scope_ids is None:
            return HandlerResult(self.name, False, "missing scope")
        from adapter_service.core import Scope

        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        correlation_id = str(event.get("correlation_id") or event.get("event_id") or uuid4())
        message = {
            "message_id": f"outbox-{event.get('event_id')}",
            "schema_version": "1.0.0",
            "sender": "outbox-relay",
            "sender_type": "system",
            "tenant_id": scope_ids[0],
            "project_id": scope_ids[2],
            "intent": intent,
            "domain": "engineering",
            "payload": {
                "event_type": event_type,
                "record": payload,
            },
            "status": "emitted",
            "refs": list(event.get("evidence_refs") or []) or [f"event:{event.get('event_id')}"],
            "correlation_id": correlation_id,
            "created_at": str(event.get("occurred_at") or utc_now()),
        }
        self._adapter.publish_agent_event(
            Scope(*scope_ids),
            str(event.get("actor_ref") or "outbox-relay"),
            correlation_id,
            f"outbox-broker:{event.get('event_id')}",
            message,
        )
        return HandlerResult(self.name, True, f"broker:{intent}")


class TicketDispatchHandler:
    """Dispatch ExternalTicketCreate outbox events through TrackerAdapter."""

    name = "ticket_dispatch"

    def __init__(self, adapter_service: Any) -> None:
        self._adapter = adapter_service

    def handle(self, event: dict[str, Any], *, source: str) -> HandlerResult:
        if source != "adapter":
            return HandlerResult(self.name, True, "skipped:not-adapter")
        event_type = str(event.get("event_type") or "")
        if event_type != "ExternalTicketDispatchRequested":
            return HandlerResult(self.name, True, f"skipped:{event_type}")
        scope_ids = _scope(event)
        if scope_ids is None:
            return HandlerResult(self.name, False, "missing scope")
        from adapter_service.core import Scope

        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        ticket_id = str(payload.get("ticket_id") or "").strip()
        if not ticket_id:
            return HandlerResult(self.name, False, "missing ticket_id")
        event_id = str(event.get("event_id") or uuid4())
        self._adapter.dispatch_external_ticket(
            Scope(*scope_ids),
            str(event.get("actor_ref") or "outbox-relay"),
            str(event.get("correlation_id") or event_id),
            f"outbox-ticket-dispatch:{event_id}",
            ticket_id,
        )
        return HandlerResult(self.name, True, f"dispatched:{ticket_id}")


def _scope(event: dict[str, Any]) -> tuple[str, str, str] | None:
    tenant = str(event.get("tenant_id") or "").strip()
    workspace = str(event.get("workspace_id") or "").strip()
    project = str(event.get("project_id") or "").strip()
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    if not all((tenant, workspace, project)):
        tenant = tenant or str(payload.get("tenant_id") or "").strip()
        workspace = workspace or str(payload.get("workspace_id") or "").strip()
        project = project or str(payload.get("project_id") or "").strip()
    if not all((tenant, workspace, project)):
        scope = payload.get("scope") if isinstance(payload.get("scope"), dict) else {}
        tenant = tenant or str(scope.get("tenant_id") or "").strip()
        workspace = workspace or str(scope.get("workspace_id") or "").strip()
        project = project or str(scope.get("project_id") or "").strip()
    if not all((tenant, workspace, project)):
        return None
    return tenant, workspace, project


def _memory_body(event_type: str, payload: dict[str, Any]) -> str:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    parts = [
        f"Core-data event {event_type}.",
        f"Record id: {payload.get('id')}.",
        f"Kind: {payload.get('kind')}.",
        f"Status: {payload.get('status')}.",
    ]
    if data.get("title"):
        parts.append(f"Title: {data.get('title')}.")
    if data.get("instructions"):
        parts.append(f"Instructions: {data.get('instructions')}.")
    if data.get("summary"):
        parts.append(f"Summary: {data.get('summary')}.")
    return " ".join(str(part) for part in parts if part)


def _intent_for(event_type: str) -> str | None:
    mapping = {
        "activity.recorded": "TASK_STARTED",
        "task.created": "TASK_STARTED",
        "worklog.created": "TASK_STARTED",
        "issue.discovered": "TEST_FAILURE_DETECTED",
        "decision.created": "API_READY",
    }
    return mapping.get(event_type)

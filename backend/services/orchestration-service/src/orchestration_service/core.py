from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import uuid4


class OrchestrationError(Exception):
    def __init__(self, code: str, category: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code, self.category, self.message = code, category, message
        self.details = details or {}


class ValidationError(OrchestrationError):
    def __init__(self, message: str):
        super().__init__("validation_error", "validation_error", message)


class ConflictError(OrchestrationError):
    def __init__(self, message: str, *, code: str = "conflict_error", details: dict[str, Any] | None = None):
        super().__init__(code, "conflict_error", message, details)


class NotFoundError(OrchestrationError):
    def __init__(self, message: str):
        super().__init__("not_found", "not_found_error", message)


class AgentTicketState(StrEnum):
    CREATED = "created"
    ASSIGNED = "assigned"
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    REVIEW = "review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


TERMINAL_TICKET_STATES = {
    AgentTicketState.COMPLETED,
    AgentTicketState.FAILED,
    AgentTicketState.CANCELED,
}

# command -> (from_states, to_state)
TICKET_TRANSITIONS: dict[str, tuple[set[AgentTicketState], AgentTicketState]] = {
    "claim": ({AgentTicketState.ASSIGNED}, AgentTicketState.CLAIMED),
    "start": (
        {AgentTicketState.CLAIMED, AgentTicketState.BLOCKED, AgentTicketState.REVIEW},
        AgentTicketState.IN_PROGRESS,
    ),
    "block": ({AgentTicketState.IN_PROGRESS, AgentTicketState.CLAIMED}, AgentTicketState.BLOCKED),
    "submit-review": ({AgentTicketState.IN_PROGRESS}, AgentTicketState.REVIEW),
    "complete": ({AgentTicketState.REVIEW, AgentTicketState.IN_PROGRESS}, AgentTicketState.COMPLETED),
    "fail": (
        {
            AgentTicketState.CREATED,
            AgentTicketState.ASSIGNED,
            AgentTicketState.CLAIMED,
            AgentTicketState.IN_PROGRESS,
            AgentTicketState.BLOCKED,
            AgentTicketState.REVIEW,
        },
        AgentTicketState.FAILED,
    ),
    "cancel": (
        {
            AgentTicketState.CREATED,
            AgentTicketState.ASSIGNED,
            AgentTicketState.CLAIMED,
            AgentTicketState.IN_PROGRESS,
            AgentTicketState.BLOCKED,
            AgentTicketState.REVIEW,
        },
        AgentTicketState.CANCELED,
    ),
}


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
    def put_batch(self, batch: dict[str, Any]) -> None: ...
    def get_batch(self, batch_id: str, scope: Scope) -> dict[str, Any]: ...
    def put_assignment(self, assignment: dict[str, Any]) -> None: ...
    def get_assignment(self, assignment_id: str, scope: Scope) -> dict[str, Any]: ...
    def list_assignments(self, scope: Scope, batch_id: str | None = None) -> list[dict[str, Any]]: ...
    def put_agent_ticket(self, ticket: dict[str, Any], expected_version: int | None = None) -> None: ...
    def get_agent_ticket(self, ticket_id: str, scope: Scope) -> dict[str, Any]: ...
    def list_agent_tickets(
        self,
        scope: Scope,
        *,
        status: str | None = None,
        agent_id: str | None = None,
        task_id: str | None = None,
    ) -> list[dict[str, Any]]: ...


class OrchestrationService:
    def __init__(self, store: Store):
        self.store = store

    def open_work_batch(
        self,
        scope: Scope,
        actor_id: str,
        correlation_id: str,
        idempotency_key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        title = str(payload.get("title") or "").strip()
        if not title:
            raise ValidationError("title is required")
        existing = self.store.begin_idempotency(scope, idempotency_key, "work_batch")
        if existing:
            return self.store.get_batch(existing, scope)
        batch_id = _new_id("wb")
        batch = {
            "id": batch_id,
            "tenant_id": scope.tenant_id,
            "workspace_id": scope.workspace_id,
            "project_id": scope.project_id,
            "title": title,
            "status": "open",
            "opened_by": actor_id,
            "correlation_id": correlation_id,
            "task_ids": [str(t) for t in (payload.get("task_ids") or [])],
            "created_at": _now(),
            "updated_at": _now(),
        }
        self.store.put_batch(batch)
        self.store.complete_idempotency(scope, idempotency_key, "work_batch", batch_id)
        self.store.append_event({"event_type": "work_batch.opened", "batch_id": batch_id})
        return batch

    def route_task(
        self,
        scope: Scope,
        actor_id: str,
        correlation_id: str,
        idempotency_key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        task_id = str(payload.get("task_id") or "").strip()
        agent_type = str(payload.get("agent_type") or "").strip()
        batch_id = str(payload.get("batch_id") or "").strip() or None
        if not task_id or not agent_type:
            raise ValidationError("task_id and agent_type are required")
        if batch_id:
            batch = self.store.get_batch(batch_id, scope)
            if batch["status"] not in {"open", "routing"}:
                raise ConflictError("work batch is not open for routing")
        existing = self.store.begin_idempotency(scope, idempotency_key, "assignment")
        if existing:
            return self.store.get_assignment(existing, scope)
        assignment_id = _new_id("asg")
        assignment = {
            "id": assignment_id,
            "tenant_id": scope.tenant_id,
            "workspace_id": scope.workspace_id,
            "project_id": scope.project_id,
            "task_id": task_id,
            "agent_type": agent_type,
            "batch_id": batch_id,
            "status": "assigned",
            "routed_by": actor_id,
            "correlation_id": correlation_id,
            "created_at": _now(),
        }
        self.store.put_assignment(assignment)
        if batch_id:
            batch = self.store.get_batch(batch_id, scope)
            batch["status"] = "routing"
            batch["updated_at"] = _now()
            if task_id not in batch["task_ids"]:
                batch["task_ids"].append(task_id)
            self.store.put_batch(batch)
        self.store.complete_idempotency(scope, idempotency_key, "assignment", assignment_id)
        self.store.append_event({"event_type": "task.routed", "assignment_id": assignment_id})
        return assignment

    def close_work_batch(self, scope: Scope, batch_id: str) -> dict[str, Any]:
        batch = self.store.get_batch(batch_id, scope)
        if batch["status"] == "closed":
            return batch
        batch["status"] = "closed"
        batch["updated_at"] = _now()
        self.store.put_batch(batch)
        self.store.append_event({"event_type": "work_batch.closed", "batch_id": batch_id})
        return batch

    def complete_assignment(self, scope: Scope, assignment_id: str, actor_id: str) -> dict[str, Any]:
        assignment = self.store.get_assignment(assignment_id, scope)
        if assignment["status"] == "completed":
            return assignment
        if assignment["status"] != "assigned":
            raise ConflictError("assignment cannot be completed from current status")
        assignment["status"] = "completed"
        assignment["completed_by"] = actor_id
        assignment["completed_at"] = _now()
        self.store.put_assignment(assignment)
        self.store.append_event({"event_type": "assignment.completed", "assignment_id": assignment_id})
        return assignment

    def list_assignments(self, scope: Scope, batch_id: str | None = None) -> list[dict[str, Any]]:
        return self.store.list_assignments(scope, batch_id=batch_id)

    def create_agent_ticket(
        self,
        scope: Scope,
        actor_id: str,
        correlation_id: str,
        idempotency_key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        title = str(payload.get("title") or "").strip()
        agent_id = str(payload.get("agent_id") or "").strip() or None
        if not title:
            raise ValidationError("title is required")
        existing = self.store.begin_idempotency(scope, idempotency_key, "agent_ticket")
        if existing:
            return self.store.get_agent_ticket(existing, scope)
        ticket_id = _new_id("atk")
        timestamp = _now()
        status = AgentTicketState.ASSIGNED.value if agent_id else AgentTicketState.CREATED.value
        ticket = {
            "id": ticket_id,
            "tenant_id": scope.tenant_id,
            "workspace_id": scope.workspace_id,
            "project_id": scope.project_id,
            "title": title,
            "status": status,
            "agent_id": agent_id,
            "agent_type": str(payload.get("agent_type") or "").strip() or None,
            "task_id": str(payload.get("task_id") or "").strip() or None,
            "acceptance_criteria": str(payload.get("acceptance_criteria") or "").strip() or None,
            "block_reason": None,
            "changeset_id": None,
            "changeset_revision": None,
            "fail_reason": None,
            "cancel_reason": None,
            "assigned_by": actor_id if agent_id else None,
            "correlation_id": correlation_id,
            "version": 1,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        self.store.put_agent_ticket(ticket)
        self.store.complete_idempotency(scope, idempotency_key, "agent_ticket", ticket_id)
        self.store.append_event(
            {
                "event_type": "AgentTicketCreated",
                "ticket_id": ticket_id,
                "status": ticket["status"],
                "correlation_id": correlation_id,
            }
        )
        return ticket

    def get_agent_ticket(self, scope: Scope, ticket_id: str) -> dict[str, Any]:
        return self.store.get_agent_ticket(ticket_id, scope)

    def list_agent_tickets(
        self,
        scope: Scope,
        *,
        status: str | None = None,
        agent_id: str | None = None,
        task_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return self.store.list_agent_tickets(scope, status=status, agent_id=agent_id, task_id=task_id)

    def transition_agent_ticket(
        self,
        scope: Scope,
        actor_id: str,
        correlation_id: str,
        idempotency_key: str,
        ticket_id: str,
        command: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = dict(payload or {})
        expected_version = body.get("expected_version")
        if not isinstance(expected_version, int) or expected_version < 1:
            raise ValidationError("expected_version must be a positive integer")
        resource = f"agent_ticket:{command}"
        existing = self.store.begin_idempotency(scope, idempotency_key, resource)
        if existing:
            return self.store.get_agent_ticket(existing, scope)
        ticket = self.store.get_agent_ticket(ticket_id, scope)
        if ticket["version"] != expected_version:
            raise ConflictError(
                "agent ticket version does not match",
                code="version_conflict",
                details={"current_version": ticket["version"], "current_status": ticket["status"]},
            )
        current = AgentTicketState(ticket["status"])
        if command == "reassign":
            new_agent = str(body.get("agent_id") or "").strip()
            if not new_agent:
                raise ValidationError("agent_id is required for reassign")
            if current in TERMINAL_TICKET_STATES:
                raise ConflictError("terminal agent ticket cannot be reassigned")
            if current not in {
                AgentTicketState.CREATED,
                AgentTicketState.ASSIGNED,
                AgentTicketState.CLAIMED,
                AgentTicketState.IN_PROGRESS,
                AgentTicketState.BLOCKED,
                AgentTicketState.REVIEW,
            }:
                raise ConflictError("agent ticket cannot be reassigned from current status")
            ticket["agent_id"] = new_agent
            if body.get("agent_type") is not None:
                ticket["agent_type"] = str(body.get("agent_type") or "").strip() or None
            ticket["status"] = AgentTicketState.ASSIGNED.value
            ticket["block_reason"] = None
            ticket["assigned_by"] = actor_id
            event_type = "AgentTicketReassigned"
        else:
            if command not in TICKET_TRANSITIONS:
                raise ValidationError(f"unsupported agent ticket command: {command}")
            allowed_from, target = TICKET_TRANSITIONS[command]
            if current not in allowed_from:
                raise ConflictError(
                    f"cannot {command} agent ticket from status {current.value}",
                    details={"current_status": current.value},
                )
            if command == "block":
                reason = str(body.get("reason") or "").strip()
                if not reason:
                    raise ValidationError("reason is required for block")
                ticket["block_reason"] = reason
            if command == "submit-review":
                ticket["changeset_id"] = str(body.get("changeset_id") or "").strip() or ticket.get("changeset_id")
                ticket["changeset_revision"] = (
                    str(body.get("changeset_revision") or "").strip() or ticket.get("changeset_revision")
                )
            if command == "fail":
                ticket["fail_reason"] = str(body.get("reason") or "").strip() or None
            if command == "cancel":
                ticket["cancel_reason"] = str(body.get("reason") or "").strip() or None
            if command == "start" and current == AgentTicketState.BLOCKED:
                ticket["block_reason"] = None
            ticket["status"] = target.value
            event_type = {
                "claim": "AgentTicketClaimed",
                "start": "AgentTicketStarted",
                "block": "AgentTicketBlocked",
                "submit-review": "AgentTicketSubmittedForReview",
                "complete": "AgentTicketCompleted",
                "fail": "AgentTicketFailed",
                "cancel": "AgentTicketCanceled",
            }[command]
        ticket["version"] = int(ticket["version"]) + 1
        ticket["updated_at"] = _now()
        ticket["last_actor_id"] = actor_id
        ticket["correlation_id"] = correlation_id
        try:
            self.store.put_agent_ticket(ticket, expected_version=expected_version)
        except ConflictError as exc:
            current_ticket = self.store.get_agent_ticket(ticket_id, scope)
            raise ConflictError(
                "agent ticket changed concurrently",
                code="version_conflict",
                details={
                    "current_version": current_ticket["version"],
                    "current_status": current_ticket["status"],
                },
            ) from exc
        self.store.complete_idempotency(scope, idempotency_key, resource, ticket_id)
        self.store.append_event(
            {
                "event_type": event_type,
                "ticket_id": ticket_id,
                "status": ticket["status"],
                "version": ticket["version"],
                "correlation_id": correlation_id,
                "actor_id": actor_id,
            }
        )
        return ticket

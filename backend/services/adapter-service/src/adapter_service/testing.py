from __future__ import annotations

from copy import deepcopy
from typing import Any

from .core import (
    AdapterMapping,
    BrokerEvent,
    ConflictError,
    Connector,
    DeadLetterRecord,
    Delivery,
    DepartmentTask,
    ExternalTicket,
    NotFoundError,
    Scope,
    Subscription,
    decode_ticket_page_token,
    digest,
    encode_ticket_page_token,
)


class InMemoryStore:
    """Deterministic Store fake for unit and transport-contract tests."""

    def __init__(self) -> None:
        self._connectors: dict[str, Connector] = {}
        self._mappings: dict[str, AdapterMapping] = {}
        self._subscriptions: dict[str, Subscription] = {}
        self._events: dict[str, BrokerEvent] = {}
        self._deliveries: dict[str, Delivery] = {}
        self._dead: dict[str, DeadLetterRecord] = {}
        self._tickets: dict[str, ExternalTicket] = {}
        self._department_tasks: dict[str, DepartmentTask] = {}
        self._idempotency: dict[tuple[str, str, str], tuple[str, str]] = {}
        self._outbox: list[dict[str, Any]] = []

    @staticmethod
    def _scope_key(scope: Scope) -> str:
        return "|".join((scope.tenant_id, scope.workspace_id, scope.project_id, scope.project_group_id or ""))

    @staticmethod
    def _same_project(left: Scope, right: Scope) -> bool:
        return (left.tenant_id, left.workspace_id, left.project_id) == (right.tenant_id, right.workspace_id, right.project_id)

    def get_connector(self, connector_id: str, scope: Scope) -> Connector:
        item = self._connectors.get(connector_id)
        if item is None or not self._same_project(item.scope, scope):
            raise NotFoundError("connector not found in project scope")
        return deepcopy(item)

    def put_connector(self, connector: Connector) -> None:
        self._connectors[connector.id] = deepcopy(connector)

    def list_connectors(self, scope: Scope) -> list[Connector]:
        items = [item for item in self._connectors.values() if self._same_project(item.scope, scope)]
        return deepcopy(sorted(items, key=lambda item: (item.created_at, item.id)))

    def put_mapping(self, mapping: AdapterMapping) -> None:
        self._mappings[mapping.id] = deepcopy(mapping)

    def list_mappings(self, scope: Scope, connector_id: str | None = None) -> list[AdapterMapping]:
        items = [item for item in self._mappings.values() if self._same_project(item.scope, scope)]
        if connector_id is not None:
            items = [item for item in items if item.connector_id == connector_id]
        return deepcopy(sorted(items, key=lambda item: (item.created_at, item.id)))

    def get_subscription(self, subscription_id: str, scope: Scope) -> Subscription:
        item = self._subscriptions.get(subscription_id)
        if item is None or not self._same_project(item.scope, scope):
            raise NotFoundError("subscription not found in project scope")
        return deepcopy(item)

    def put_subscription(self, subscription: Subscription) -> None:
        self._subscriptions[subscription.id] = deepcopy(subscription)

    def list_subscriptions(self, scope: Scope) -> list[Subscription]:
        items = [item for item in self._subscriptions.values() if self._same_project(item.scope, scope)]
        return deepcopy(sorted(items, key=lambda item: (item.created_at, item.id)))

    def put_event(self, event: BrokerEvent) -> None:
        self._events[event.id] = deepcopy(event)

    def get_event(self, event_id: str, scope: Scope) -> BrokerEvent:
        item = self._events.get(event_id)
        if item is None or not self._same_project(item.scope, scope):
            raise NotFoundError("broker event not found in project scope")
        return deepcopy(item)

    def list_events(self, scope: Scope, channel: str | None = None) -> list[BrokerEvent]:
        items = [item for item in self._events.values() if self._same_project(item.scope, scope)]
        if channel is not None:
            items = [item for item in items if item.channel == channel]
        return deepcopy(sorted(items, key=lambda item: (item.created_at, item.id)))

    def put_delivery(self, delivery: Delivery) -> None:
        self._deliveries[delivery.id] = deepcopy(delivery)

    def list_deliveries(self, scope: Scope) -> list[Delivery]:
        items = [item for item in self._deliveries.values() if self._same_project(item.scope, scope)]
        return deepcopy(sorted(items, key=lambda item: (item.created_at, item.id)))

    def put_dead_letter(self, record: DeadLetterRecord) -> None:
        self._dead[record.id] = deepcopy(record)

    def list_dead_letters(self, scope: Scope) -> list[DeadLetterRecord]:
        items = [item for item in self._dead.values() if self._same_project(item.scope, scope)]
        return deepcopy(sorted(items, key=lambda item: (item.created_at, item.id)))

    def get_ticket(self, ticket_id: str, scope: Scope) -> ExternalTicket:
        item = self._tickets.get(ticket_id)
        if item is None or not self._same_project(item.scope, scope):
            raise NotFoundError("external ticket not found in project scope")
        return deepcopy(item)

    def put_ticket(self, ticket: ExternalTicket, expected_version: int | None = None) -> None:
        current = self._tickets.get(ticket.id)
        if expected_version is not None and (current is None or current.version != expected_version):
            raise ConflictError("external ticket changed concurrently")
        self._tickets[ticket.id] = deepcopy(ticket)

    def list_tickets(
        self,
        scope: Scope,
        *,
        connector_id: str | None = None,
        status: str | None = None,
        external_ref: str | None = None,
        department: str | None = None,
        updated_after: str | None = None,
        page_size: int = 50,
        page_token: str | None = None,
    ) -> tuple[list[ExternalTicket], str | None]:
        items = [item for item in self._tickets.values() if self._same_project(item.scope, scope)]
        if connector_id is not None:
            items = [item for item in items if item.connector_id == connector_id]
        if status is not None:
            items = [item for item in items if item.status.value == status]
        if external_ref is not None:
            items = [item for item in items if item.external_ref == external_ref]
        if department is not None:
            items = [item for item in items if item.department == department]
        if updated_after is not None:
            items = [item for item in items if item.updated_at > updated_after]
        items = sorted(items, key=lambda item: (item.updated_at, item.id), reverse=True)
        if page_token:
            token_key = decode_ticket_page_token(page_token)
            items = [item for item in items if (item.updated_at, item.id) < token_key]
        page = items[:page_size]
        next_token = encode_ticket_page_token(page[-1]) if len(items) > page_size and page else None
        return deepcopy(page), next_token

    def put_department_task(self, task: DepartmentTask) -> None:
        self._department_tasks[task.id] = deepcopy(task)

    def list_department_tasks(self, scope: Scope) -> list[DepartmentTask]:
        items = [item for item in self._department_tasks.values() if self._same_project(item.scope, scope)]
        return deepcopy(sorted(items, key=lambda item: (item.created_at, item.id)))

    def idempotent(self, scope: Scope, command: str, key: str, payload: dict[str, Any]) -> str | None:
        remembered = self._idempotency.get((self._scope_key(scope), command, key))
        if remembered is None:
            return None
        fingerprint, record_id = remembered
        if fingerprint != digest(payload):
            raise ConflictError("idempotency key was reused with a different payload")
        return record_id

    def remember(self, scope: Scope, command: str, key: str, payload: dict[str, Any], record_id: str) -> None:
        self._idempotency[(self._scope_key(scope), command, key)] = (digest(payload), record_id)

    def event(self, payload: dict[str, Any]) -> None:
        self._outbox.append(deepcopy(payload))

    def outbox(self) -> list[dict[str, Any]]:
        return deepcopy(sorted(self._outbox, key=lambda event: (event["occurred_at"], event["event_id"])))

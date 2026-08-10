from __future__ import annotations

from typing import Any
from uuid import uuid4

from .broker import BrokerCommands
from .connectors import ConnectorCommands
from .context import ContextCommands
from .errors import ValidationError
from .helpers import now
from .models import Scope
from .protocols import Store, TrackerAdapter
from .tickets import TicketCommands


class AdapterService(ConnectorCommands, BrokerCommands, TicketCommands, ContextCommands):
    def __init__(
        self,
        store: Store,
        max_delivery_attempts: int = 2,
        tracker_adapters: dict[str, TrackerAdapter] | None = None,
    ):
        self.store = store
        self.max_delivery_attempts = max_delivery_attempts
        self.tracker_adapters = dict(tracker_adapters or {})

    def _require_key(self, key: str) -> None:
        if not key:
            raise ValidationError("Idempotency-Key header is required")

    def emit(
        self,
        event_type: str,
        payload: dict[str, Any],
        scope: Scope,
        actor: str,
        correlation_id: str,
        key: str,
        causation_id: str,
        evidence_refs: list[str],
    ) -> None:
        self.store.event(
            {
                "event_id": str(uuid4()),
                "event_type": event_type,
                "event_version": 1,
                "occurred_at": now(),
                "producer": "adapter-service",
                "tenant_id": scope.tenant_id,
                "workspace_id": scope.workspace_id,
                "project_id": scope.project_id,
                "project_group_id": scope.project_group_id,
                "actor_ref": actor,
                "correlation_id": correlation_id,
                "causation_id": causation_id,
                "idempotency_key": key,
                "payload": payload,
                "evidence_refs": evidence_refs,
            }
        )

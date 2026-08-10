from __future__ import annotations

from enum import StrEnum


class ConnectorState(StrEnum):
    PENDING = "pending_configuration"
    VALIDATING = "validating"
    READY = "ready"
    DEGRADED = "degraded"
    DISABLED = "disabled"
    FAILED = "failed"
    REVOKED = "revoked"


class DeliveryState(StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    RETRYING = "retrying"
    DEAD_LETTERED = "dead_lettered"


class SubscriptionState(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class TicketState(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELED = "canceled"


class TicketDispatchState(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD_LETTERED = "dead_lettered"


class TicketSyncState(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD_LETTERED = "dead_lettered"


class MappingState(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"

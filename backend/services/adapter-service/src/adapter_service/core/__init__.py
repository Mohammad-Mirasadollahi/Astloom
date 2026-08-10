"""Adapter-service domain core (modular package with stable public imports)."""

from __future__ import annotations

from .constants import ALLOWED_INTENTS, CLEARANCE_RANK, DEPARTMENT_TRIGGERS, REQUIRED_MESSAGE_FIELDS
from .enums import (
    ConnectorState,
    DeliveryState,
    MappingState,
    SubscriptionState,
    TicketDispatchState,
    TicketState,
    TicketSyncState,
)
from .errors import AdapterError, ConflictError, NotFoundError, ValidationError
from .helpers import (
    bounded_text,
    channel_for,
    decode_ticket_page_token,
    digest,
    encode_ticket_page_token,
    nested,
    normalize_remote_url,
    normalize_status_map,
    normalize_timestamp,
    now,
    sanitize,
)
from .models import (
    AdapterMapping,
    BrokerEvent,
    Connector,
    DeadLetterRecord,
    Delivery,
    DepartmentTask,
    DispatchAck,
    ExternalTicket,
    Scope,
    Subscription,
)
from .protocols import Store, TrackerAdapter
from .service import AdapterService

# Backward-compatible private aliases used by older call sites / tests if any.
_nested = nested
_normalize_status_map = normalize_status_map

__all__ = [
    "ALLOWED_INTENTS",
    "CLEARANCE_RANK",
    "DEPARTMENT_TRIGGERS",
    "REQUIRED_MESSAGE_FIELDS",
    "AdapterError",
    "AdapterMapping",
    "AdapterService",
    "BrokerEvent",
    "ConflictError",
    "Connector",
    "ConnectorState",
    "DeadLetterRecord",
    "Delivery",
    "DeliveryState",
    "DepartmentTask",
    "DispatchAck",
    "ExternalTicket",
    "MappingState",
    "NotFoundError",
    "Scope",
    "Store",
    "Subscription",
    "SubscriptionState",
    "TicketDispatchState",
    "TicketState",
    "TicketSyncState",
    "TrackerAdapter",
    "ValidationError",
    "bounded_text",
    "channel_for",
    "decode_ticket_page_token",
    "digest",
    "encode_ticket_page_token",
    "nested",
    "normalize_remote_url",
    "normalize_status_map",
    "normalize_timestamp",
    "now",
    "sanitize",
]

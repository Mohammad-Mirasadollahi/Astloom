from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .enums import (
    ConnectorState,
    DeliveryState,
    MappingState,
    SubscriptionState,
    TicketDispatchState,
    TicketState,
    TicketSyncState,
)
from .errors import ValidationError


@dataclass(frozen=True)
class Scope:
    tenant_id: str
    workspace_id: str
    project_id: str
    project_group_id: str | None = None

    def __post_init__(self) -> None:
        if not all((self.tenant_id.strip(), self.workspace_id.strip(), self.project_id.strip())):
            raise ValidationError("tenant_id, workspace_id, and project_id are required")


@dataclass
class Connector:
    id: str
    scope: Scope
    actor_id: str
    correlation_id: str
    vendor: str
    name: str
    capabilities: list[str]
    auth_profile: str
    trust_level: str
    status: ConnectorState
    credential_fingerprint: str
    created_at: str
    updated_at: str
    version: int = 1

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "project_id": self.scope.project_id,
            "actor_id": self.actor_id,
            "correlation_id": self.correlation_id,
            "vendor": self.vendor,
            "name": self.name,
            "capabilities": self.capabilities,
            "auth_profile": self.auth_profile,
            "trust_level": self.trust_level,
            "status": self.status.value,
            "credential_fingerprint": self.credential_fingerprint,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class AdapterMapping:
    id: str
    scope: Scope
    connector_id: str
    vendor_schema_version: str
    field_map: dict[str, str]
    status: MappingState
    created_at: str
    updated_at: str
    version: int = 1
    status_map: dict[str, str] | None = None
    reopen_policy: str = "allow_remote"
    unknown_status_policy: str = "reject"
    fallback_status: str = "open"
    mapping_version: int = 1

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "project_id": self.scope.project_id,
            "connector_id": self.connector_id,
            "vendor_schema_version": self.vendor_schema_version,
            "field_map": self.field_map,
            "status_map": self.status_map or {},
            "reopen_policy": self.reopen_policy,
            "unknown_status_policy": self.unknown_status_policy,
            "fallback_status": self.fallback_status,
            "mapping_version": self.mapping_version,
            "status": self.status.value,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class Subscription:
    id: str
    scope: Scope
    actor_id: str
    correlation_id: str
    channel: str
    subscriber_type: str
    endpoint: str
    filter_intents: list[str]
    filter_domains: list[str]
    status: SubscriptionState
    fail_mode: str
    created_at: str
    updated_at: str
    version: int = 1

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "project_id": self.scope.project_id,
            "actor_id": self.actor_id,
            "correlation_id": self.correlation_id,
            "channel": self.channel,
            "subscriber_type": self.subscriber_type,
            "endpoint": self.endpoint,
            "filter_intents": self.filter_intents,
            "filter_domains": self.filter_domains,
            "status": self.status.value,
            "fail_mode": self.fail_mode,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class BrokerEvent:
    id: str
    scope: Scope
    channel: str
    message: dict[str, Any]
    created_at: str

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "project_id": self.scope.project_id,
            "channel": self.channel,
            "message": self.message,
            "created_at": self.created_at,
        }


@dataclass
class Delivery:
    id: str
    scope: Scope
    event_id: str
    subscription_id: str
    status: DeliveryState
    attempts: int
    last_error: str | None
    created_at: str
    updated_at: str

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "project_id": self.scope.project_id,
            "event_id": self.event_id,
            "subscription_id": self.subscription_id,
            "status": self.status.value,
            "attempts": self.attempts,
            "last_error": self.last_error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class DeadLetterRecord:
    id: str
    scope: Scope
    event_id: str
    subscription_id: str
    reason: str
    message: dict[str, Any]
    created_at: str

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "project_id": self.scope.project_id,
            "event_id": self.event_id,
            "subscription_id": self.subscription_id,
            "reason": self.reason,
            "message": self.message,
            "created_at": self.created_at,
        }


@dataclass
class ExternalTicket:
    id: str
    scope: Scope
    actor_id: str
    correlation_id: str
    connector_id: str
    external_ref: str
    title: str
    status: TicketState
    department: str
    source_event_id: str | None
    evidence_refs: list[str]
    created_at: str
    updated_at: str
    version: int = 1
    description_summary: str | None = None
    priority: str | None = None
    severity: str | None = None
    assignee_ref: str | None = None
    due_at: str | None = None
    labels: list[str] | None = None
    remote_url: str | None = None
    external_updated_at: str | None = None
    sync_source: str | None = None
    sync_reason: str | None = None
    last_sync_status: TicketSyncState = TicketSyncState.PENDING
    last_sync_error: str | None = None
    dispatch_status: TicketDispatchState = TicketDispatchState.PENDING
    dispatch_attempts: int = 1
    extension: dict[str, Any] | None = None

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "project_id": self.scope.project_id,
            "actor_id": self.actor_id,
            "correlation_id": self.correlation_id,
            "connector_id": self.connector_id,
            "external_ref": self.external_ref,
            "title": self.title,
            "status": self.status.value,
            "department": self.department,
            "source_event_id": self.source_event_id,
            "evidence_refs": self.evidence_refs,
            "description_summary": self.description_summary,
            "priority": self.priority,
            "severity": self.severity,
            "assignee_ref": self.assignee_ref,
            "due_at": self.due_at,
            "labels": self.labels or [],
            "remote_url": self.remote_url,
            "external_updated_at": self.external_updated_at,
            "sync_source": self.sync_source,
            "sync_reason": self.sync_reason,
            "last_sync_status": self.last_sync_status.value,
            "last_sync_error": self.last_sync_error,
            "dispatch_status": self.dispatch_status.value,
            "dispatch_attempts": self.dispatch_attempts,
            "extension": self.extension or {},
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class DepartmentTask:
    id: str
    scope: Scope
    department: str
    title: str
    trigger_intent: str
    source_message_id: str
    approval_required: bool
    status: str
    created_at: str

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "project_id": self.scope.project_id,
            "department": self.department,
            "title": self.title,
            "trigger_intent": self.trigger_intent,
            "source_message_id": self.source_message_id,
            "approval_required": self.approval_required,
            "status": self.status,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class DispatchAck:
    ok: bool
    external_ref: str | None = None
    remote_url: str | None = None
    external_updated_at: str | None = None
    error: str | None = None

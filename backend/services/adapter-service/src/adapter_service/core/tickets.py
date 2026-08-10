from __future__ import annotations

import json
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from .enums import (
    ConnectorState,
    MappingState,
    TicketDispatchState,
    TicketState,
    TicketSyncState,
)
from .errors import ConflictError, ValidationError
from .helpers import (
    bounded_text,
    decode_ticket_page_token,
    normalize_remote_url,
    normalize_timestamp,
    now,
    sanitize,
)
from .models import AdapterMapping, ExternalTicket, Scope


class TicketCommands:
    def create_external_ticket(self, scope: Scope, actor: str, correlation_id: str, key: str, payload: dict[str, Any]) -> ExternalTicket:
        self._require_key(key)
        remote_url = normalize_remote_url(payload.get("remote_url"))
        payload = sanitize(payload)
        missing = [field for field in ("connector_id", "title", "department") if not payload.get(field)]
        if missing:
            raise ValidationError("missing required fields: " + ", ".join(missing))
        connector = self.store.get_connector(payload["connector_id"], scope)
        if connector.status != ConnectorState.READY:
            raise ConflictError("connector is not ready")
        extension = payload.get("extension") or {}
        if not isinstance(extension, dict):
            raise ValidationError("extension must be an object")
        if len(json.dumps(extension, sort_keys=True, default=str).encode()) > 16_384:
            raise ValidationError("extension exceeds 16384 bytes")
        generated_ref = uuid5(
            NAMESPACE_URL,
            "|".join((scope.tenant_id, scope.workspace_id, scope.project_id, key)),
        )
        command_payload = {
            "connector_id": payload["connector_id"],
            "title": bounded_text(payload["title"], "title", 500),
            "department": bounded_text(payload["department"], "department", 100),
            "external_ref": bounded_text(payload.get("external_ref"), "external_ref", 500) or f"ext:{generated_ref}",
            "source_event_id": payload.get("source_event_id"),
            "evidence_refs": sorted(set(payload.get("evidence_refs") or [])),
            "description_summary": bounded_text(payload.get("description_summary"), "description_summary", 4000),
            "priority": bounded_text(payload.get("priority"), "priority", 100),
            "severity": bounded_text(payload.get("severity"), "severity", 100),
            "assignee_ref": bounded_text(payload.get("assignee_ref"), "assignee_ref", 500),
            "due_at": normalize_timestamp(payload.get("due_at"), "due_at", required=False),
            "labels": sorted({str(item).strip() for item in (payload.get("labels") or []) if str(item).strip()}),
            "remote_url": remote_url,
            "extension": extension,
        }
        prior = self.store.idempotent(scope, "create_external_ticket", key, command_payload)
        if prior:
            return self.store.get_ticket(prior, scope)
        timestamp = now()
        ticket = ExternalTicket(
            id=str(uuid4()),
            scope=scope,
            actor_id=actor,
            correlation_id=correlation_id,
            connector_id=command_payload["connector_id"],
            external_ref=command_payload["external_ref"],
            title=command_payload["title"] or "",
            status=TicketState.OPEN,
            department=command_payload["department"] or "",
            source_event_id=command_payload.get("source_event_id"),
            evidence_refs=command_payload["evidence_refs"],
            created_at=timestamp,
            updated_at=timestamp,
            description_summary=command_payload["description_summary"],
            priority=command_payload["priority"],
            severity=command_payload["severity"],
            assignee_ref=command_payload["assignee_ref"],
            due_at=command_payload["due_at"],
            labels=command_payload["labels"],
            remote_url=command_payload["remote_url"],
            extension=command_payload["extension"],
        )
        self.store.put_ticket(ticket)
        self.store.remember(scope, "create_external_ticket", key, command_payload, ticket.id)
        self.emit("ExternalTicketCreated", ticket.public(), scope, actor, correlation_id, key, ticket.id, ticket.evidence_refs)
        self.emit(
            "ExternalTicketDispatchRequested",
            {"ticket_id": ticket.id, "dispatch_status": ticket.dispatch_status.value, "attempt": ticket.dispatch_attempts},
            scope,
            actor,
            correlation_id,
            key,
            ticket.id,
            ticket.evidence_refs,
        )
        return ticket
    
    def get_external_ticket(self, scope: Scope, ticket_id: str) -> ExternalTicket:
        return self.store.get_ticket(ticket_id, scope)
    
    def list_external_tickets(
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
        if page_size < 1 or page_size > 100:
            raise ValidationError("page_size must be between 1 and 100")
        normalized_status: str | None = None
        if status:
            try:
                normalized_status = TicketState(status).value
            except ValueError as exc:
                raise ValidationError("invalid ticket status") from exc
        normalized_after = normalize_timestamp(updated_after, "updated_after", required=False)
        if page_token:
            decode_ticket_page_token(page_token)
        return self.store.list_tickets(
            scope,
            connector_id=connector_id,
            status=normalized_status,
            external_ref=external_ref,
            department=department,
            updated_after=normalized_after,
            page_size=page_size,
            page_token=page_token,
        )
    
    def sync_external_status(
        self,
        scope: Scope,
        actor: str,
        correlation_id: str,
        key: str,
        ticket_id: str,
        status: str,
        expected_version: int,
        external_updated_at: str,
        source: str = "manual",
        reason: str | None = None,
    ) -> ExternalTicket:
        self._require_key(key)
        self._require_version(expected_version)
        allowed_sources = {"manual", "webhook", "poll", "adapter", "reconciliation"}
        if source not in allowed_sources:
            raise ValidationError("invalid sync source")
        normalized_external_at = normalize_timestamp(external_updated_at, "external_updated_at", required=True)
        normalized_reason = bounded_text(sanitize(reason), "reason", 2000)
        payload = {
            "ticket_id": ticket_id,
            "status": status,
            "expected_version": expected_version,
            "external_updated_at": normalized_external_at,
            "source": source,
            "reason": normalized_reason,
        }
        prior = self.store.idempotent(scope, "sync_external_status", key, payload)
        if prior:
            return self.store.get_ticket(prior, scope)
        ticket = self.store.get_ticket(ticket_id, scope)
        mapping = self._active_mapping(scope, ticket.connector_id)
        if ticket.version != expected_version:
            self._reject_external_status(ticket, scope, actor, correlation_id, key, status, "version_conflict")
            raise ConflictError(
                "external ticket version does not match",
                code="version_conflict",
                details={"current_version": ticket.version, "current_status": ticket.status.value},
            )
        try:
            target_status = self.map_vendor_status(status, mapping)
        except ValidationError:
            self._reject_external_status(ticket, scope, actor, correlation_id, key, status, "invalid_status")
            raise
        if ticket.external_updated_at and normalized_external_at < ticket.external_updated_at:
            self._reject_external_status(ticket, scope, actor, correlation_id, key, status, "stale_external_update")
            raise ConflictError(
                "external status update is older than the accepted remote state",
                code="stale_external_update",
                details={"current_version": ticket.version, "current_status": ticket.status.value},
            )
        try:
            self._validate_ticket_transition(ticket.status, target_status, source, mapping)
        except ValidationError:
            self._reject_external_status(ticket, scope, actor, correlation_id, key, status, "transition_not_allowed")
            raise
        changed = any(
            (
                ticket.status != target_status,
                ticket.external_updated_at != normalized_external_at,
                ticket.sync_source != source,
                ticket.sync_reason != normalized_reason,
                ticket.last_sync_status != TicketSyncState.SUCCEEDED,
                ticket.last_sync_error is not None,
                ticket.dispatch_status != TicketDispatchState.SUCCEEDED,
            )
        )
        previous_dispatch = ticket.dispatch_status
        if changed:
            ticket.status = target_status
            ticket.external_updated_at = normalized_external_at
            ticket.sync_source = source
            ticket.sync_reason = normalized_reason
            ticket.last_sync_status = TicketSyncState.SUCCEEDED
            ticket.last_sync_error = None
            ticket.dispatch_status = TicketDispatchState.SUCCEEDED
            ticket.version += 1
            ticket.updated_at = now()
            try:
                self.store.put_ticket(ticket, expected_version=expected_version)
            except ConflictError as exc:
                current = self.store.get_ticket(ticket_id, scope)
                self._reject_external_status(current, scope, actor, correlation_id, key, status, "version_conflict")
                raise ConflictError(
                    "external ticket changed concurrently",
                    code="version_conflict",
                    details={"current_version": current.version, "current_status": current.status.value},
                ) from exc
        self.store.remember(scope, "sync_external_status", key, payload, ticket.id)
        self.emit(
            "ExternalStatusSynced",
            {
                **ticket.public(),
                "changed": changed,
                "mapping_version": mapping.mapping_version if mapping else None,
            },
            scope,
            actor,
            correlation_id,
            key,
            ticket.id,
            ticket.evidence_refs,
        )
        if previous_dispatch != TicketDispatchState.SUCCEEDED and ticket.dispatch_status == TicketDispatchState.SUCCEEDED:
            self.emit(
                "ExternalTicketDispatchSucceeded",
                {"ticket_id": ticket.id, "dispatch_status": ticket.dispatch_status.value},
                scope,
                actor,
                correlation_id,
                key,
                ticket.id,
                ticket.evidence_refs,
            )
        return ticket
    
    def retry_external_ticket_dispatch(
        self,
        scope: Scope,
        actor: str,
        correlation_id: str,
        key: str,
        ticket_id: str,
        expected_version: int,
        reason: str | None = None,
    ) -> ExternalTicket:
        self._require_key(key)
        self._require_version(expected_version)
        normalized_reason = bounded_text(sanitize(reason), "reason", 2000)
        payload = {"ticket_id": ticket_id, "expected_version": expected_version, "reason": normalized_reason}
        prior = self.store.idempotent(scope, "retry_external_ticket_dispatch", key, payload)
        if prior:
            return self.store.get_ticket(prior, scope)
        ticket = self.store.get_ticket(ticket_id, scope)
        if ticket.version != expected_version:
            raise ConflictError(
                "external ticket version does not match",
                code="version_conflict",
                details={"current_version": ticket.version, "current_status": ticket.status.value},
            )
        ticket.dispatch_status = TicketDispatchState.PENDING
        ticket.dispatch_attempts += 1
        ticket.last_sync_status = TicketSyncState.PENDING
        ticket.last_sync_error = None
        ticket.sync_reason = normalized_reason
        ticket.version += 1
        ticket.updated_at = now()
        try:
            self.store.put_ticket(ticket, expected_version=expected_version)
        except ConflictError as exc:
            current = self.store.get_ticket(ticket_id, scope)
            raise ConflictError(
                "external ticket changed concurrently",
                code="version_conflict",
                details={"current_version": current.version, "current_status": current.status.value},
            ) from exc
        self.store.remember(scope, "retry_external_ticket_dispatch", key, payload, ticket.id)
        self.emit(
            "ExternalTicketDispatchRequested",
            {"ticket_id": ticket.id, "dispatch_status": ticket.dispatch_status.value, "attempt": ticket.dispatch_attempts},
            scope,
            actor,
            correlation_id,
            key,
            ticket.id,
            ticket.evidence_refs,
        )
        return ticket
    
    def record_external_ticket_dispatch_result(
        self,
        scope: Scope,
        actor: str,
        correlation_id: str,
        key: str,
        ticket_id: str,
        expected_version: int,
        dispatch_status: str,
        remote_url: str | None = None,
        external_ref: str | None = None,
        error: str | None = None,
    ) -> ExternalTicket:
        self._require_key(key)
        self._require_version(expected_version)
        try:
            target = TicketDispatchState(dispatch_status)
        except ValueError as exc:
            raise ValidationError("invalid dispatch status") from exc
        if target == TicketDispatchState.PENDING:
            raise ValidationError("dispatch result status cannot be pending")
        normalized_url = normalize_remote_url(remote_url)
        normalized_ref = bounded_text(sanitize(external_ref), "external_ref", 500)
        normalized_error = bounded_text(sanitize(error), "error", 2000)
        if target in {TicketDispatchState.FAILED, TicketDispatchState.DEAD_LETTERED} and not normalized_error:
            raise ValidationError("error is required for failed dispatch results")
        payload = {
            "ticket_id": ticket_id,
            "expected_version": expected_version,
            "dispatch_status": target.value,
            "remote_url": normalized_url,
            "external_ref": normalized_ref,
            "error": normalized_error,
        }
        prior = self.store.idempotent(scope, "record_external_ticket_dispatch_result", key, payload)
        if prior:
            return self.store.get_ticket(prior, scope)
        ticket = self.store.get_ticket(ticket_id, scope)
        if ticket.version != expected_version:
            raise ConflictError(
                "external ticket version does not match",
                code="version_conflict",
                details={"current_version": ticket.version, "current_status": ticket.status.value},
            )
        ticket.dispatch_status = target
        ticket.last_sync_status = TicketSyncState(target.value)
        ticket.last_sync_error = normalized_error
        ticket.remote_url = normalized_url or ticket.remote_url
        ticket.external_ref = normalized_ref or ticket.external_ref
        ticket.version += 1
        ticket.updated_at = now()
        try:
            self.store.put_ticket(ticket, expected_version=expected_version)
        except ConflictError as exc:
            current = self.store.get_ticket(ticket_id, scope)
            raise ConflictError(
                "external ticket changed concurrently",
                code="version_conflict",
                details={"current_version": current.version, "current_status": current.status.value},
            ) from exc
        self.store.remember(scope, "record_external_ticket_dispatch_result", key, payload, ticket.id)
        event_type = (
            "ExternalTicketDispatchSucceeded"
            if target == TicketDispatchState.SUCCEEDED
            else "ExternalTicketDispatchFailed"
        )
        self.emit(
            event_type,
            {
                "ticket_id": ticket.id,
                "dispatch_status": target.value,
                "attempt": ticket.dispatch_attempts,
                "error": normalized_error,
            },
            scope,
            actor,
            correlation_id,
            key,
            ticket.id,
            ticket.evidence_refs,
        )
        return ticket
    
    def dispatch_external_ticket(
        self,
        scope: Scope,
        actor: str,
        correlation_id: str,
        key: str,
        ticket_id: str,
    ) -> ExternalTicket:
        """Execute remote create via TrackerAdapter and record the dispatch result."""
        self._require_key(key)
        ticket = self.store.get_ticket(ticket_id, scope)
        if ticket.dispatch_status == TicketDispatchState.SUCCEEDED:
            return ticket
        connector = self.store.get_connector(ticket.connector_id, scope)
        mapping = self._active_mapping(scope, ticket.connector_id) or AdapterMapping(
            id="implicit",
            scope=scope,
            connector_id=ticket.connector_id,
            vendor_schema_version="1.0.0",
            field_map={"status": "status"},
            status=MappingState.ACTIVE,
            created_at=now(),
            updated_at=now(),
        )
        adapter = self.tracker_adapters.get(connector.vendor) or self.tracker_adapters.get("local")
        if adapter is None:
            return self.record_external_ticket_dispatch_result(
                scope,
                actor,
                correlation_id,
                key,
                ticket_id,
                ticket.version,
                TicketDispatchState.FAILED.value,
                error=f"no tracker adapter registered for vendor {connector.vendor}",
            )
        ack = adapter.create_remote(ticket, connector, mapping)
        if ack.ok:
            return self.record_external_ticket_dispatch_result(
                scope,
                actor,
                correlation_id,
                key,
                ticket_id,
                ticket.version,
                TicketDispatchState.SUCCEEDED.value,
                remote_url=ack.remote_url,
                external_ref=ack.external_ref,
            )
        status = (
            TicketDispatchState.DEAD_LETTERED.value
            if ticket.dispatch_attempts >= self.max_delivery_attempts
            else TicketDispatchState.FAILED.value
        )
        return self.record_external_ticket_dispatch_result(
            scope,
            actor,
            correlation_id,
            key,
            ticket_id,
            ticket.version,
            status,
            error=ack.error or "tracker adapter create failed",
        )
    
    def push_external_ticket_status(
        self,
        scope: Scope,
        actor: str,
        correlation_id: str,
        key: str,
        ticket_id: str,
        expected_version: int,
        status: str | None = None,
    ) -> ExternalTicket:
        """Push portable status to the remote tracker via TrackerAdapter.update_remote_status."""
        self._require_key(key)
        self._require_version(expected_version)
        payload = {
            "ticket_id": ticket_id,
            "expected_version": expected_version,
            "status": status,
        }
        prior = self.store.idempotent(scope, "push_external_ticket_status", key, payload)
        if prior:
            return self.store.get_ticket(prior, scope)
        ticket = self.store.get_ticket(ticket_id, scope)
        if ticket.version != expected_version:
            raise ConflictError(
                "external ticket version does not match",
                code="version_conflict",
                details={"current_version": ticket.version, "current_status": ticket.status.value},
            )
        target = ticket.status
        if status is not None:
            mapping_for_status = self._active_mapping(scope, ticket.connector_id)
            target = self.map_vendor_status(status, mapping_for_status)
        connector = self.store.get_connector(ticket.connector_id, scope)
        mapping = self._active_mapping(scope, ticket.connector_id) or AdapterMapping(
            id="implicit",
            scope=scope,
            connector_id=ticket.connector_id,
            vendor_schema_version="1.0.0",
            field_map={"status": "status"},
            status=MappingState.ACTIVE,
            created_at=now(),
            updated_at=now(),
        )
        adapter = self.tracker_adapters.get(connector.vendor) or self.tracker_adapters.get("local")
        if adapter is None:
            raise ValidationError(f"no tracker adapter registered for vendor {connector.vendor}")
        updater = getattr(adapter, "update_remote_status", None)
        if not callable(updater):
            raise ValidationError(f"tracker adapter for {connector.vendor} does not support status updates")
        ack = updater(ticket, connector, mapping, target)
        if not ack.ok:
            failed = self.record_external_ticket_dispatch_result(
                scope,
                actor,
                correlation_id,
                f"{key}:push-failed",
                ticket_id,
                ticket.version,
                TicketDispatchState.FAILED.value,
                error=ack.error or "tracker adapter status update failed",
            )
            self.store.remember(scope, "push_external_ticket_status", key, payload, failed.id)
            return failed
        if ticket.status != target:
            ticket.status = target
        if ack.external_updated_at:
            ticket.external_updated_at = ack.external_updated_at
        if ack.remote_url:
            ticket.remote_url = ack.remote_url
        if ack.external_ref:
            ticket.external_ref = ack.external_ref
        ticket.dispatch_status = TicketDispatchState.SUCCEEDED
        ticket.last_sync_status = TicketSyncState.SUCCEEDED
        ticket.last_sync_error = None
        ticket.sync_source = "adapter"
        ticket.sync_reason = f"pushed status {target.value}"
        ticket.version += 1
        ticket.updated_at = now()
        try:
            self.store.put_ticket(ticket, expected_version=expected_version)
        except ConflictError as exc:
            current = self.store.get_ticket(ticket_id, scope)
            raise ConflictError(
                "external ticket changed concurrently",
                code="version_conflict",
                details={"current_version": current.version, "current_status": current.status.value},
            ) from exc
        self.store.remember(scope, "push_external_ticket_status", key, payload, ticket.id)
        self.emit(
            "ExternalTicketStatusPushed",
            {
                **ticket.public(),
                "mapping_version": mapping.mapping_version,
                "pushed_status": target.value,
            },
            scope,
            actor,
            correlation_id,
            key,
            ticket.id,
            ticket.evidence_refs,
        )
        return ticket
    
    def map_vendor_status(self, status: str, mapping: AdapterMapping | None) -> TicketState:
        raw = str(status or "").strip()
        if not raw:
            raise ValidationError("invalid ticket status")
        status_map = (mapping.status_map if mapping and mapping.status_map else {}) or {}
        mapped = status_map.get(raw) or status_map.get(raw.lower()) or raw
        try:
            return TicketState(mapped)
        except ValueError:
            policy = (mapping.unknown_status_policy if mapping else "reject") or "reject"
            if policy == "fallback" and mapping is not None:
                try:
                    return TicketState(mapping.fallback_status)
                except ValueError as exc:
                    raise ValidationError("invalid ticket status") from exc
            raise ValidationError("invalid ticket status")
    
    def _reject_external_status(
        self,
        ticket: ExternalTicket,
        scope: Scope,
        actor: str,
        correlation_id: str,
        key: str,
        requested_status: str,
        reason_code: str,
    ) -> None:
        self.emit(
            "ExternalStatusRejected",
            {
                "ticket_id": ticket.id,
                "requested_status": requested_status,
                "reason_code": reason_code,
                "current_status": ticket.status.value,
                "current_version": ticket.version,
            },
            scope,
            actor,
            correlation_id,
            key,
            ticket.id,
            ticket.evidence_refs,
        )
    
    @staticmethod
    def _require_version(expected_version: int) -> None:
        if not isinstance(expected_version, int) or expected_version < 1:
            raise ValidationError("expected_version must be a positive integer")
    
    @staticmethod
    def _validate_ticket_transition(
        current: TicketState,
        target: TicketState,
        source: str,
        mapping: AdapterMapping | None = None,
    ) -> None:
        remote_sources = {"webhook", "poll", "adapter", "reconciliation"}
        if current in {TicketState.DONE, TicketState.CANCELED} and target in {TicketState.OPEN, TicketState.IN_PROGRESS}:
            policy = (mapping.reopen_policy if mapping else "allow_remote") or "allow_remote"
            if policy == "deny":
                raise ValidationError("reopening a terminal external ticket is denied by connector mapping policy")
            if source not in remote_sources:
                raise ValidationError("reopening a terminal external ticket requires a remote sync source")

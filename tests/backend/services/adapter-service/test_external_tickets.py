"""Focused ExternalTicket unit tests for the modular adapter_service.core package."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from adapter_service.api import build_app
from adapter_service.core import (
    AdapterService,
    ConflictError,
    NotFoundError,
    Scope,
    TicketState,
    ValidationError,
    encode_ticket_page_token,
    normalize_status_map,
)
from adapter_service.core.helpers import decode_ticket_page_token
from adapter_service.core.tickets import TicketCommands
from adapter_service.testing import InMemoryStore
from adapter_service.trackers import LocalTrackerAdapter

SCOPE = Scope("t", "w", "p")


def _ready_connector(service: AdapterService, *, vendor: str = "tracker", **mapping: object):
    connector = service.register_connector(
        SCOPE,
        "ops",
        "corr",
        f"reg-{uuid4().hex[:8]}",
        {
            "vendor": vendor,
            "name": "ticket-unit-connector",
            "capabilities": ["tickets"],
            "auth_profile": "token",
            "credential": "secret",
            **mapping,
        },
    )
    return service.validate_connector(SCOPE, "ops", "corr", f"val-{uuid4().hex[:8]}", connector.id)


def _ticket_payload(connector_id: str, suffix: str = "1") -> dict:
    return {
        "connector_id": connector_id,
        "title": f"Unit ticket {suffix}",
        "department": "platform-engineering",
        "external_ref": f"UNIT-{suffix}",
        "priority": "high",
        "labels": ["unit"],
    }


def test_modular_ticket_commands_are_composed_into_adapter_service():
    assert issubclass(AdapterService, TicketCommands)
    assert hasattr(AdapterService, "create_external_ticket")
    assert hasattr(AdapterService, "push_external_ticket_status")


def test_create_rejects_invalid_remote_url_and_missing_connector():
    store = InMemoryStore()
    service = AdapterService(store, tracker_adapters={"local": LocalTrackerAdapter()})
    connector = _ready_connector(service)

    with pytest.raises(ValidationError, match="remote_url"):
        service.create_external_ticket(
            SCOPE,
            "ops",
            "corr",
            "bad-url",
            {**_ticket_payload(connector.id), "remote_url": "ftp://example.com/x"},
        )

    with pytest.raises(NotFoundError, match="connector"):
        service.create_external_ticket(
            SCOPE,
            "ops",
            "corr",
            "missing-connector",
            _ticket_payload("missing-connector-id"),
        )


def test_sync_same_state_is_idempotent_and_cancel_transition():
    store = InMemoryStore()
    service = AdapterService(store, tracker_adapters={"local": LocalTrackerAdapter()})
    connector = _ready_connector(service)
    ticket = service.create_external_ticket(SCOPE, "ops", "corr", "same-create", _ticket_payload(connector.id))

    first = service.sync_external_status(
        SCOPE,
        "ops",
        "corr",
        "same-sync-1",
        ticket.id,
        "open",
        ticket.version,
        "2026-08-01T10:00:00+00:00",
        source="webhook",
        reason="noop",
    )
    assert first.status == TicketState.OPEN
    assert first.version == ticket.version + 1

    second = service.sync_external_status(
        SCOPE,
        "ops",
        "corr",
        "same-sync-2",
        first.id,
        "open",
        first.version,
        "2026-08-01T10:00:00+00:00",
        source="webhook",
        reason="noop",
    )
    assert second.version == first.version
    assert second.status == TicketState.OPEN

    canceled = service.sync_external_status(
        SCOPE,
        "ops",
        "corr",
        "cancel-sync",
        second.id,
        "canceled",
        second.version,
        "2026-08-01T10:00:01+00:00",
        source="webhook",
    )
    assert canceled.status == TicketState.CANCELED
    assert canceled.version == second.version + 1


def test_unknown_status_fallback_policy():
    store = InMemoryStore()
    service = AdapterService(store, tracker_adapters={"local": LocalTrackerAdapter()})
    connector = _ready_connector(
        service,
        status_map={"Done": "done"},
        unknown_status_policy="fallback",
        fallback_status="in_progress",
    )
    mapping = service.get_adapter_mapping(SCOPE, connector.id)[0]
    assert service.map_vendor_status("WeirdVendorState", mapping) == TicketState.IN_PROGRESS

    ticket = service.create_external_ticket(SCOPE, "ops", "corr", "fb-create", _ticket_payload(connector.id, "fb"))
    synced = service.sync_external_status(
        SCOPE,
        "ops",
        "corr",
        "fb-sync",
        ticket.id,
        "WeirdVendorState",
        ticket.version,
        "2026-08-01T11:00:00Z",
        source="webhook",
    )
    assert synced.status == TicketState.IN_PROGRESS


def test_push_status_version_conflict_and_http_route():
    store = InMemoryStore()
    service = AdapterService(store, tracker_adapters={"tracker": LocalTrackerAdapter()})
    connector = _ready_connector(service)
    ticket = service.create_external_ticket(SCOPE, "ops", "corr", "push-create", _ticket_payload(connector.id, "p"))
    dispatched = service.dispatch_external_ticket(SCOPE, "ops", "corr", "push-dispatch", ticket.id)
    assert dispatched.dispatch_status.value == "succeeded"

    with pytest.raises(ConflictError) as exc:
        service.push_external_ticket_status(
            SCOPE,
            "ops",
            "corr",
            "push-conflict",
            dispatched.id,
            expected_version=1,
            status="done",
        )
    assert exc.value.code == "version_conflict"

    with TestClient(build_app(service=service)) as client:
        response = client.post(
            f"/api/v1/projects/p/external-tickets/{dispatched.id}:push-status",
            headers={
                "X-Tenant-Id": "t",
                "X-Workspace-Id": "w",
                "X-Actor-Id": "ops",
                "X-Correlation-Id": "push-http",
                "Idempotency-Key": "push-http-ok",
            },
            json={"expected_version": dispatched.version, "status": "done"},
        )
    assert response.status_code == 200, response.text
    body = response.json()["ticket"]
    assert body["status"] == "done"
    assert body["dispatch_status"] == "succeeded"
    assert any(item["event_type"] == "ExternalTicketStatusPushed" for item in store.outbox())


def test_record_dispatch_result_validation():
    store = InMemoryStore()
    service = AdapterService(store, tracker_adapters={"local": LocalTrackerAdapter()})
    connector = _ready_connector(service)
    ticket = service.create_external_ticket(SCOPE, "ops", "corr", "disp-create", _ticket_payload(connector.id, "d"))

    with pytest.raises(ValidationError, match="invalid dispatch status"):
        service.record_external_ticket_dispatch_result(
            SCOPE,
            "ops",
            "corr",
            "disp-bad",
            ticket.id,
            ticket.version,
            "not-a-status",
        )

    with pytest.raises(ValidationError, match="cannot be pending"):
        service.record_external_ticket_dispatch_result(
            SCOPE,
            "ops",
            "corr",
            "disp-pending",
            ticket.id,
            ticket.version,
            "pending",
        )

    with pytest.raises(ValidationError, match="error is required"):
        service.record_external_ticket_dispatch_result(
            SCOPE,
            "ops",
            "corr",
            "disp-failed-no-error",
            ticket.id,
            ticket.version,
            "failed",
        )

    ok = service.record_external_ticket_dispatch_result(
        SCOPE,
        "ops",
        "corr",
        "disp-ok",
        ticket.id,
        ticket.version,
        "succeeded",
        remote_url="https://local.tracker.invalid/UNIT-d",
        external_ref="UNIT-d",
    )
    assert ok.dispatch_status.value == "succeeded"
    assert ok.external_ref == "UNIT-d"
    assert ok.version == ticket.version + 1


def test_ticket_helpers_page_token_and_status_map():
    store = InMemoryStore()
    service = AdapterService(store, tracker_adapters={"local": LocalTrackerAdapter()})
    connector = _ready_connector(service)
    ticket = service.create_external_ticket(SCOPE, "ops", "corr", "tok-create", _ticket_payload(connector.id, "tok"))

    token = encode_ticket_page_token(ticket)
    updated_at, ticket_id = decode_ticket_page_token(token)
    assert updated_at == ticket.updated_at
    assert ticket_id == ticket.id

    with pytest.raises(ValidationError, match="invalid page_token"):
        decode_ticket_page_token("not-a-token")

    assert normalize_status_map({"Done": "done", "To Do": "open"}) == {"Done": "done", "To Do": "open"}
    with pytest.raises(ValidationError, match="portable ticket status"):
        normalize_status_map({"Done": "finished"})


def test_dispatch_uses_local_adapter_when_vendor_unregistered():
    store = InMemoryStore()
    service = AdapterService(store, tracker_adapters={"local": LocalTrackerAdapter()})
    connector = _ready_connector(service, vendor="unknown-cloud-tracker")
    ticket = service.create_external_ticket(SCOPE, "ops", "corr", "local-fb-create", _ticket_payload(connector.id, "lf"))

    dispatched = service.dispatch_external_ticket(SCOPE, "ops", "corr", "local-fb-dispatch", ticket.id)
    assert dispatched.dispatch_status.value == "succeeded"
    assert dispatched.external_ref
    assert dispatched.remote_url
    assert any(item["event_type"] == "ExternalTicketDispatchSucceeded" for item in store.outbox())

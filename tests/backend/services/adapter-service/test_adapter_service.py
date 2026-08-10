import pytest
from fastapi.testclient import TestClient

from adapter_service.api import app
from adapter_service.core import AdapterService, ConflictError, NotFoundError, Scope, ValidationError
from adapter_service.testing import InMemoryStore


SCOPE = Scope("t", "w", "p")


def universal(sender: str, intent: str, status: str, refs=None, **payload):
    return {
        "message_id": f"msg-{sender}-{intent}",
        "schema_version": "1.0.0",
        "sender": sender,
        "sender_type": "agent",
        "tenant_id": "t",
        "project_id": "p",
        "intent": intent,
        "domain": "engineering",
        "payload": payload or {"summary": intent},
        "status": status,
        "refs": refs or [],
        "correlation_id": "corr-1",
        "created_at": "2026-07-18T12:00:00+00:00",
    }


def ready_connector(service: AdapterService, key: str, vendor: str):
    connector = service.register_connector(
        SCOPE,
        "ops",
        "corr",
        key,
        {
            "vendor": vendor,
            "name": f"{vendor}-agent",
            "capabilities": ["can_edit_code", "can_report_task_state"],
            "auth_profile": "token",
            "credential": f"{vendor}-secret",
        },
    )
    return service.validate_connector(SCOPE, "ops", "corr", key + "-validate", connector.id)


def test_two_vendors_exchange_task_state_and_ide_receives_api_ready():
    store = InMemoryStore()
    service = AdapterService(store)

    vendor_a = ready_connector(service, "conn-a", "acme")
    vendor_b = ready_connector(service, "conn-b", "globex")
    assert {item["vendor"] for item in service.discover_capabilities(SCOPE)} == {"acme", "globex"}

    peer = service.subscribe(
        SCOPE,
        "ops",
        "corr",
        "sub-peer",
        {
            "channel": "agent.tasks",
            "subscriber_type": "agent",
            "endpoint": f"vendor://{vendor_b.vendor}/inbox",
            "filter_intents": ["TASK_STARTED", "TASK_COMPLETED"],
        },
    )
    ide = service.subscribe(
        SCOPE,
        "ops",
        "corr",
        "sub-ide",
        {
            "channel": "ide.notifications",
            "subscriber_type": "ide",
            "endpoint": "ide://plugin/notifications",
            "filter_intents": ["API_READY"],
        },
    )

    normalized = service.normalize_vendor_event(
        SCOPE,
        "ops",
        "corr",
        "norm-1",
        vendor_a.id,
        {"id": "v1", "intent": "TASK_STARTED", "status": "running", "task_id": "task-9", "summary": "started"},
    )
    published = service.publish_agent_event(SCOPE, "ops", "corr", "pub-1", normalized["message"])
    assert published["channel"] == "agent.tasks"
    delivered_subs = {item["subscription_id"] for item in published["deliveries"] if item["status"] == "delivered"}
    assert peer.id in delivered_subs

    api_ready = service.publish_agent_event(
        SCOPE,
        "ops",
        "corr",
        "pub-2",
        universal("acme", "API_READY", "completed", refs=["api:/v1/users"], summary="Users API ready"),
    )
    assert api_ready["channel"] == "ide.notifications"
    assert any(item["subscription_id"] == ide.id and item["status"] == "delivered" for item in api_ready["deliveries"])
    assert any(event["event_type"] == "IdeNotificationSent" for event in store.outbox())


def test_dead_letter_replay_and_code_release_department_tasks():
    store = InMemoryStore()
    service = AdapterService(store)
    connector = ready_connector(service, "conn-a", "acme")

    failing = service.subscribe(
        SCOPE,
        "ops",
        "corr",
        "sub-fail",
        {
            "channel": "department.workflows",
            "subscriber_type": "webhook",
            "endpoint": "https://example.invalid/hook",
            "fail_mode": "always",
        },
    )
    result = service.publish_agent_event(
        SCOPE,
        "ops",
        "corr",
        "pub-release",
        universal("acme", "CODE_RELEASED", "completed", refs=["release:1.2.0"], summary="backend release"),
    )
    assert result["channel"] == "department.workflows"
    assert any(item["subscription_id"] == failing.id and item["status"] == "dead_lettered" for item in result["deliveries"])
    assert service.get_dead_letter_queue(SCOPE)
    departments = {task.department for task in service.list_department_tasks(SCOPE)}
    assert {"marketing", "support", "devops"} <= departments

    replayed = service.replay(SCOPE, "ops", "corr", "replay-1", "department.workflows")
    assert replayed["replayed_count"] == 1

    ticket = service.create_external_ticket(
        SCOPE,
        "ops",
        "corr",
        "ticket-1",
        {"connector_id": connector.id, "title": "Announce release", "department": "marketing", "source_event_id": result["event"]["id"]},
    )
    synced = service.sync_external_status(
        SCOPE,
        "ops",
        "corr",
        "sync-1",
        ticket.id,
        "done",
        ticket.version,
        "2026-07-29T00:00:00Z",
        "webhook",
    )
    assert synced.status.value == "done"
    assert service.list_department_tasks(Scope("other", "w", "p")) == []


def test_api_contract_routes_are_registered():
    routes = {route.path for route in app(AdapterService(InMemoryStore())).routes}
    assert "/api/v1/projects/{project_id}/connectors" in routes
    assert "/api/v1/projects/{project_id}/agent-events" in routes
    assert "/api/v1/projects/{project_id}/dead-letters" in routes
    assert "/api/v1/projects/{project_id}/department-tasks" in routes
    assert "/api/v1/projects/{project_id}/context:inject" in routes
    assert "/api/v1/projects/{project_id}/external-tickets" in routes
    assert "/api/v1/projects/{project_id}/external-tickets/{ticket_id}" in routes
    assert "/api/v1/projects/{project_id}/external-tickets/{ticket_id}:retry-dispatch" in routes
    assert "/api/v1/projects/{project_id}/external-tickets/{ticket_id}:record-dispatch-result" in routes


def test_context_injection_and_unauthorized_subscriber():
    store = InMemoryStore()
    service = AdapterService(store)
    ready_connector(service, "conn-a", "acme")

    denied = service.inject_context(
        SCOPE,
        "ops",
        "corr",
        "ctx-deny",
        {
            "tool_ref": "ide://plugin",
            "tenant_id": "other-tenant",
            "items": [{"title": "Secret", "body": "token=super-secret-value", "sensitivity": "restricted"}],
        },
    )
    assert denied["status"] == "denied"
    assert denied["reason_code"] == "tenant_mismatch"

    allowed = service.inject_context(
        SCOPE,
        "ops",
        "corr",
        "ctx-ok",
        {
            "tool_ref": "ide://plugin",
            "sensitivity_clearance": "public",
            "items": [
                {"title": "Public", "body": "safe note", "sensitivity": "public"},
                {"title": "Secret", "body": "token=super-secret-value", "sensitivity": "restricted"},
            ],
        },
    )
    assert allowed["status"] == "allowed"
    bodies = {item["title"]: item for item in allowed["package"]["items"]}
    assert bodies["Public"]["redacted"] is False
    assert bodies["Secret"]["redacted"] is True
    assert bodies["Secret"]["body"] == "[REDACTED]"
    assert "super-secret-value" not in bodies["Secret"]["body"]

    allowed_peer = service.subscribe(
        SCOPE,
        "ops",
        "corr",
        "sub-ok",
        {"channel": "agent.tasks", "subscriber_type": "agent", "endpoint": "vendor://acme/inbox"},
    )
    denied_peer = service.subscribe(
        SCOPE,
        "ops",
        "corr",
        "sub-deny",
        {
            "channel": "agent.tasks",
            "subscriber_type": "agent",
            "endpoint": "vendor://evil/inbox",
            "fail_mode": "unauthorized",
        },
    )
    published = service.publish_agent_event(
        SCOPE,
        "ops",
        "corr",
        "pub-auth",
        universal("acme", "TASK_STARTED", "running", refs=["task:1"], summary="started"),
    )
    delivered = {item["subscription_id"] for item in published["deliveries"] if item["status"] == "delivered"}
    assert allowed_peer.id in delivered
    assert denied_peer.id not in delivered


def test_register_connector_rejects_invalid_trust_level():
    from adapter_service.core import ValidationError

    service = AdapterService(InMemoryStore())
    try:
        service.register_connector(
            SCOPE,
            "ops",
            "corr",
            "bad-trust",
            {
                "vendor": "acme",
                "name": "acme-agent",
                "capabilities": ["can_edit_code"],
                "auth_profile": "token",
                "trust_level": "superuser",
            },
        )
        raise AssertionError("expected ValidationError")
    except ValidationError as exc:
        assert "trust_level" in exc.message


def test_register_connector_denied_by_admin_matrix():
    from adapter_service.core import ValidationError

    service = AdapterService(InMemoryStore())
    try:
        service.register_connector(
            SCOPE,
            "ops",
            "corr",
            "denied-install",
            {
                "vendor": "acme",
                "name": "acme-agent",
                "capabilities": ["can_edit_code"],
                "auth_profile": "token",
                "actor_roles": ["viewer"],
            },
        )
        raise AssertionError("expected ValidationError")
    except ValidationError as exc:
        assert "adapter.install" in exc.message


def test_register_connector_fails_closed_when_governance_missing(monkeypatch):
    from adapter_service.core import ValidationError
    import builtins

    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "architecture_governance" or name.startswith("architecture_governance."):
            raise ImportError("missing architecture_governance")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    monkeypatch.setenv("ASTLOOM_ENFORCE_ADMIN_MATRIX", "1")
    service = AdapterService(InMemoryStore())
    try:
        service.register_connector(
            SCOPE,
            "ops",
            "corr",
            "enforce-missing-gov",
            {
                "vendor": "acme",
                "name": "acme-agent",
                "capabilities": ["can_edit_code"],
                "auth_profile": "token",
            },
        )
        raise AssertionError("expected ValidationError")
    except ValidationError as exc:
        assert "architecture_governance" in exc.message


def _external_ticket_payload(connector_id: str, suffix: str = "1") -> dict:
    return {
        "connector_id": connector_id,
        "title": f"Ticket {suffix}",
        "department": "platform-engineering",
        "description_summary": "Verify the external ticket contract",
        "priority": "high",
        "severity": "medium",
        "assignee_ref": "team:platform",
        "due_at": "2026-08-01T10:00:00Z",
        "labels": ["ticketing", "audit", "ticketing"],
        "remote_url": f"https://tracker.example.invalid/TKT-{suffix}",
        "evidence_refs": ["doc:ticketing"],
        "extension": {"safe": "value", "token": "token=do-not-store"},
    }


def test_external_ticket_queries_fields_pagination_and_scope():
    store = InMemoryStore()
    service = AdapterService(store)
    connector = ready_connector(service, "ticket-query", "tracker")

    first = service.create_external_ticket(
        SCOPE,
        "ops",
        "corr",
        "ticket-create-1",
        _external_ticket_payload(connector.id, "1"),
    )
    retry = service.create_external_ticket(
        SCOPE,
        "ops",
        "corr",
        "ticket-create-1",
        _external_ticket_payload(connector.id, "1"),
    )
    second_payload = _external_ticket_payload(connector.id, "2")
    second_payload["external_ref"] = "TRACKER-2"
    second = service.create_external_ticket(SCOPE, "ops", "corr", "ticket-create-2", second_payload)

    assert retry.id == first.id
    assert retry.external_ref == first.external_ref
    assert first.labels == ["audit", "ticketing"]
    assert first.extension == {"safe": "value", "token": "token=[REDACTED]"}
    assert first.due_at == "2026-08-01T10:00:00+00:00"

    page_one, token = service.list_external_tickets(SCOPE, connector_id=connector.id, page_size=1)
    page_two, final_token = service.list_external_tickets(SCOPE, connector_id=connector.id, page_size=1, page_token=token)
    assert {page_one[0].id, page_two[0].id} == {first.id, second.id}
    assert token is not None
    assert final_token is None

    filtered, _ = service.list_external_tickets(SCOPE, external_ref="TRACKER-2")
    assert [item.id for item in filtered] == [second.id]
    assert service.get_external_ticket(SCOPE, first.id).id == first.id
    with pytest.raises(NotFoundError):
        service.get_external_ticket(Scope("other", "w", "p"), first.id)


def test_external_ticket_status_concurrency_ordering_and_dispatch_events():
    store = InMemoryStore()
    service = AdapterService(store)
    connector = ready_connector(service, "ticket-status", "tracker")
    ticket = service.create_external_ticket(
        SCOPE,
        "ops",
        "corr",
        "status-create",
        _external_ticket_payload(connector.id),
    )

    done = service.sync_external_status(
        SCOPE,
        "ops",
        "corr",
        "status-done",
        ticket.id,
        "done",
        1,
        "2026-07-29T10:00:00Z",
        "webhook",
        "completed remotely",
    )
    unchanged = service.sync_external_status(
        SCOPE,
        "ops",
        "corr",
        "status-same",
        ticket.id,
        "done",
        2,
        "2026-07-29T10:00:00Z",
        "webhook",
        "completed remotely",
    )
    assert done.version == 2
    assert unchanged.version == 2
    assert unchanged.dispatch_status.value == "succeeded"

    with pytest.raises(ConflictError) as stale:
        service.sync_external_status(
            SCOPE,
            "ops",
            "corr",
            "status-stale",
            ticket.id,
            "in_progress",
            2,
            "2026-07-29T09:59:59Z",
            "webhook",
        )
    assert stale.value.code == "stale_external_update"

    with pytest.raises(ConflictError) as concurrent:
        service.sync_external_status(
            SCOPE,
            "ops",
            "corr",
            "status-conflict",
            ticket.id,
            "in_progress",
            1,
            "2026-07-29T10:01:00Z",
            "webhook",
        )
    assert concurrent.value.code == "version_conflict"
    assert concurrent.value.details == {"current_version": 2, "current_status": "done"}

    with pytest.raises(ValidationError):
        service.sync_external_status(
            SCOPE,
            "ops",
            "corr",
            "status-reopen-manual",
            ticket.id,
            "open",
            2,
            "2026-07-29T10:01:00Z",
            "manual",
        )

    events = store.outbox()
    assert any(item["event_type"] == "ExternalTicketDispatchSucceeded" for item in events)
    rejected = [item for item in events if item["event_type"] == "ExternalStatusRejected"]
    assert {item["payload"]["reason_code"] for item in rejected} == {
        "stale_external_update",
        "transition_not_allowed",
        "version_conflict",
    }


def test_external_ticket_http_queries_conflict_and_retry_dispatch():
    store = InMemoryStore()
    service = AdapterService(store)
    connector = ready_connector(service, "ticket-http", "tracker")
    client = TestClient(app(service))
    read_headers = {"X-Tenant-Id": "t", "X-Workspace-Id": "w"}
    command_headers = {
        **read_headers,
        "X-Actor-Id": "ops",
        "X-Correlation-Id": "corr-http",
        "Idempotency-Key": "http-create",
    }

    created = client.post(
        "/api/v1/projects/p/external-tickets",
        headers=command_headers,
        json=_external_ticket_payload(connector.id),
    )
    assert created.status_code == 200
    ticket = created.json()["ticket"]

    listed = client.get(
        "/api/v1/projects/p/external-tickets",
        headers=read_headers,
        params={"status": "open", "page_size": 1},
    )
    fetched = client.get(f"/api/v1/projects/p/external-tickets/{ticket['id']}", headers=read_headers)
    hidden = client.get(
        f"/api/v1/projects/other/external-tickets/{ticket['id']}",
        headers=read_headers,
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [ticket["id"]]
    assert fetched.status_code == 200
    assert hidden.status_code == 404

    conflict_headers = {**command_headers, "Idempotency-Key": "http-conflict"}
    conflict = client.post(
        f"/api/v1/projects/p/external-tickets/{ticket['id']}:sync-status",
        headers=conflict_headers,
        json={
            "status": "done",
            "expected_version": 99,
            "external_updated_at": "2026-07-29T10:00:00Z",
            "source": "webhook",
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["error_code"] == "version_conflict"
    assert conflict.json()["error"]["details"]["current_version"] == 1

    dispatch_headers = {**command_headers, "Idempotency-Key": "http-dispatch-failed"}
    failed = client.post(
        f"/api/v1/projects/p/external-tickets/{ticket['id']}:record-dispatch-result",
        headers=dispatch_headers,
        json={"expected_version": 1, "dispatch_status": "failed", "error": "token=super-secret-value"},
    )
    assert failed.status_code == 200
    assert failed.json()["ticket"]["version"] == 2
    assert failed.json()["ticket"]["dispatch_status"] == "failed"
    assert failed.json()["ticket"]["last_sync_error"] == "token=[REDACTED]"

    retry_headers = {**command_headers, "Idempotency-Key": "http-retry"}
    retried = client.post(
        f"/api/v1/projects/p/external-tickets/{ticket['id']}:retry-dispatch",
        headers=retry_headers,
        json={"expected_version": 2, "reason": "operator retry"},
    )
    assert retried.status_code == 200
    assert retried.json()["ticket"]["version"] == 3
    assert retried.json()["ticket"]["dispatch_attempts"] == 2
    assert any(item["event_type"] == "ExternalTicketDispatchFailed" for item in store.outbox())


def test_external_ticket_status_map_reopen_policy_and_dispatch_adapter():
    from adapter_service.trackers import LocalTrackerAdapter
    from outbox_relay.handlers import TicketDispatchHandler

    store = InMemoryStore()
    service = AdapterService(store, tracker_adapters={"local": LocalTrackerAdapter(), "tracker": LocalTrackerAdapter()})
    connector = service.register_connector(
        SCOPE,
        "ops",
        "corr",
        "map-reg",
        {
            "vendor": "tracker",
            "name": "mapped-tracker",
            "capabilities": ["tickets"],
            "auth_profile": "token",
            "credential": "secret",
            "status_map": {"Done": "done", "To Do": "open"},
            "reopen_policy": "deny",
            "unknown_status_policy": "fallback",
            "fallback_status": "in_progress",
            "mapping_version": 3,
        },
    )
    service.validate_connector(SCOPE, "ops", "corr", "map-val", connector.id)
    mapping = service.get_adapter_mapping(SCOPE, connector.id)[0]
    assert mapping.mapping_version == 3
    assert service.map_vendor_status("Done", mapping).value == "done"
    assert service.map_vendor_status("Weird", mapping).value == "in_progress"

    ticket = service.create_external_ticket(SCOPE, "ops", "corr", "map-create", _external_ticket_payload(connector.id, "m1"))
    dispatched = service.dispatch_external_ticket(SCOPE, "ops", "corr", "map-dispatch", ticket.id)
    assert dispatched.dispatch_status.value == "succeeded"
    assert dispatched.remote_url

    synced = service.sync_external_status(
        SCOPE,
        "ops",
        "corr",
        "map-sync",
        ticket.id,
        "Done",
        dispatched.version,
        "2026-07-30T12:00:00Z",
        source="webhook",
    )
    assert synced.status.value == "done"
    assert any(
        item["event_type"] == "ExternalStatusSynced" and item["payload"].get("mapping_version") == 3
        for item in store.outbox()
    )

    try:
        service.sync_external_status(
            SCOPE,
            "ops",
            "corr",
            "map-reopen",
            ticket.id,
            "To Do",
            synced.version,
            "2026-07-30T13:00:00Z",
            source="webhook",
        )
        raise AssertionError("expected reopen denial")
    except ValidationError as exc:
        assert "denied" in exc.message

    # Outbox handler path
    store2 = InMemoryStore()
    service2 = AdapterService(store2, tracker_adapters={"tracker": LocalTrackerAdapter()})
    connector2 = ready_connector(service2, "handler-conn", "tracker")
    created = service2.create_external_ticket(
        SCOPE, "ops", "corr", "handler-create", _external_ticket_payload(connector2.id, "h1")
    )
    event = next(item for item in store2.outbox() if item["event_type"] == "ExternalTicketDispatchRequested")
    result = TicketDispatchHandler(service2).handle(event, source="adapter")
    assert result.ok
    refreshed = service2.get_external_ticket(SCOPE, created.id)
    assert refreshed.dispatch_status.value == "succeeded"


def test_external_ticket_unknown_status_reject_and_tracker_registry():
    from adapter_service.trackers import build_tracker_registry

    empty = build_tracker_registry({})
    assert set(empty) == {"local"}
    with_env = build_tracker_registry(
        {
            "ASTLOOM_JIRA_BASE_URL": "https://example.atlassian.net",
            "ASTLOOM_JIRA_EMAIL": "ops@example.com",
            "ASTLOOM_JIRA_API_TOKEN": "token",
            "ASTLOOM_JIRA_PROJECT_KEY": "AC",
        }
    )
    assert "jira" in with_env

    store = InMemoryStore()
    service = AdapterService(store)
    connector = service.register_connector(
        SCOPE,
        "ops",
        "corr",
        "reject-reg",
        {
            "vendor": "tracker",
            "name": "reject-tracker",
            "capabilities": ["tickets"],
            "auth_profile": "token",
            "credential": "secret",
            "unknown_status_policy": "reject",
            "status_map": {"Done": "done"},
        },
    )
    service.validate_connector(SCOPE, "ops", "corr", "reject-val", connector.id)
    mapping = service.get_adapter_mapping(SCOPE, connector.id)[0]
    try:
        service.map_vendor_status("Weird", mapping)
        raise AssertionError("expected ValidationError")
    except ValidationError:
        pass
    ticket = service.create_external_ticket(
        SCOPE, "ops", "corr", "reject-create", _external_ticket_payload(connector.id, "r1")
    )
    try:
        service.sync_external_status(
            SCOPE,
            "ops",
            "corr",
            "reject-sync",
            ticket.id,
            "Weird",
            ticket.version,
            "2026-07-30T12:00:00Z",
            source="webhook",
        )
        raise AssertionError("expected ValidationError")
    except ValidationError:
        pass
    assert any(item["event_type"] == "ExternalStatusRejected" for item in store.outbox())


def test_external_ticket_push_status_filters_dead_letter_reopen_and_idempotency_conflict():
    from adapter_service.trackers import LocalTrackerAdapter

    store = InMemoryStore()
    service = AdapterService(
        store,
        max_delivery_attempts=1,
        tracker_adapters={"tracker": LocalTrackerAdapter()},
    )
    connector = service.register_connector(
        SCOPE,
        "ops",
        "corr",
        "opt-reg",
        {
            "vendor": "tracker",
            "name": "opt-tracker",
            "capabilities": ["tickets"],
            "auth_profile": "token",
            "credential": "secret",
            "reopen_policy": "allow_remote",
            "status_map": {"Done": "done", "To Do": "open"},
        },
    )
    service.validate_connector(SCOPE, "ops", "corr", "opt-val", connector.id)

    first = service.create_external_ticket(
        SCOPE, "ops", "corr", "opt-create", _external_ticket_payload(connector.id, "o1")
    )
    second_payload = _external_ticket_payload(connector.id, "o2")
    second_payload["department"] = "security"
    second = service.create_external_ticket(SCOPE, "ops", "corr", "opt-create-2", second_payload)
    listed = service.list_external_tickets(SCOPE, department="security", updated_after="2020-01-01T00:00:00Z")
    assert [item.id for item in listed[0]] == [second.id]

    try:
        service.create_external_ticket(
            SCOPE,
            "ops",
            "corr",
            "opt-create",
            _external_ticket_payload(connector.id, "different"),
        )
        raise AssertionError("expected idempotency conflict")
    except ConflictError as exc:
        assert "idempotency" in exc.message.lower() or "different" in exc.message.lower() or exc.code

    class FailingAdapter:
        vendor = "tracker"

        def create_remote(self, ticket, connector, mapping):
            from adapter_service.core import DispatchAck

            return DispatchAck(ok=False, error="remote down")

        def update_remote_status(self, ticket, connector, mapping, status):
            from adapter_service.core import DispatchAck

            return DispatchAck(ok=False, error="remote down")

    service.tracker_adapters["tracker"] = FailingAdapter()
    dead = service.dispatch_external_ticket(SCOPE, "ops", "corr", "opt-dead", first.id)
    assert dead.dispatch_status.value == "dead_lettered"

    service.tracker_adapters["tracker"] = LocalTrackerAdapter()
    recovered = service.retry_external_ticket_dispatch(
        SCOPE, "ops", "corr", "opt-retry", first.id, dead.version, reason="retry"
    )
    pushed = service.dispatch_external_ticket(SCOPE, "ops", "corr", "opt-redispatch", recovered.id)
    assert pushed.dispatch_status.value == "succeeded"

    done = service.push_external_ticket_status(
        SCOPE, "ops", "corr", "opt-push", pushed.id, pushed.version, "done"
    )
    assert done.status.value == "done"
    assert any(item["event_type"] == "ExternalTicketStatusPushed" for item in store.outbox())

    reopened = service.sync_external_status(
        SCOPE,
        "ops",
        "corr",
        "opt-reopen",
        done.id,
        "To Do",
        done.version,
        "2099-01-01T12:00:00Z",
        source="webhook",
    )
    assert reopened.status.value == "open"

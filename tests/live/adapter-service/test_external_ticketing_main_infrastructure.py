from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from adapter_service.api import build_app
from adapter_service.bootstrap import build_container


def _headers(correlation_id: str, idempotency_key: str | None = None) -> dict[str, str]:
    headers = {
        "X-Tenant-Id": "live-ticketing",
        "X-Workspace-Id": "astloom-main",
        "X-Actor-Id": "ticketing-live-test",
        "X-Correlation-Id": correlation_id,
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


@pytest.mark.live
def test_external_ticketing_uses_main_service_and_postgres():
    assert os.environ.get("ASTLOOM_ADAPTER_SERVICE_DATABASE_URL"), (
        "ASTLOOM_ADAPTER_SERVICE_DATABASE_URL must point to the main Astloom PostgreSQL database"
    )
    run_id = uuid4().hex
    project_id = f"ticketing-live-{run_id}"
    correlation_id = f"ticketing-live-{run_id}"
    base_path = f"/api/v1/projects/{project_id}"
    external_at = datetime.now(UTC).replace(microsecond=0)

    first_container = build_container()
    try:
        with TestClient(build_app(container=first_container)) as client:
            registered = client.post(
                f"{base_path}/connectors",
                headers=_headers(correlation_id, f"register-{run_id}"),
                json={
                    "vendor": "main-infrastructure-tracker",
                    "name": "Main Infrastructure Ticketing Live Test",
                    "capabilities": ["can_create_external_ticket", "can_update_external_ticket_status"],
                    "auth_profile": "local",
                    "trust_level": "local",
                    "credential": "local-live-test-credential",
                },
            )
            assert registered.status_code == 200, registered.text
            connector_id = registered.json()["connector"]["id"]
            validated = client.post(
                f"{base_path}/connectors/{connector_id}:validate",
                headers=_headers(correlation_id, f"validate-{run_id}"),
            )
            assert validated.status_code == 200, validated.text
            assert validated.json()["connector"]["status"] == "ready"

            create_payload = {
                "connector_id": connector_id,
                "title": "Verify main-infrastructure ExternalTicket lifecycle",
                "department": "platform-engineering",
                "description_summary": "Created by the canonical live test against the main PostgreSQL schema.",
                "priority": "high",
                "severity": "medium",
                "assignee_ref": "team:platform",
                "due_at": (external_at + timedelta(days=7)).isoformat(),
                "labels": ["live", "ticketing"],
                "evidence_refs": ["doc:external-ticketing-improvement-specification"],
                "extension": {"test_run_id": run_id},
            }
            create_headers = _headers(correlation_id, f"create-{run_id}")
            created = client.post(f"{base_path}/external-tickets", headers=create_headers, json=create_payload)
            repeated = client.post(f"{base_path}/external-tickets", headers=create_headers, json=create_payload)
            assert created.status_code == repeated.status_code == 200
            ticket = created.json()["ticket"]
            assert repeated.json()["ticket"]["id"] == ticket["id"]
            assert ticket["dispatch_status"] == "pending"
            second_payload = {**create_payload, "title": "Verify main-infrastructure pagination"}
            second_created = client.post(
                f"{base_path}/external-tickets",
                headers=_headers(correlation_id, f"create-second-{run_id}"),
                json=second_payload,
            )
            assert second_created.status_code == 200, second_created.text
            second_ticket_id = second_created.json()["ticket"]["id"]

            failed = client.post(
                f"{base_path}/external-tickets/{ticket['id']}:record-dispatch-result",
                headers=_headers(correlation_id, f"dispatch-failed-{run_id}"),
                json={
                    "expected_version": 1,
                    "dispatch_status": "failed",
                    "error": "Deterministic live-test dispatch failure",
                },
            )
            assert failed.status_code == 200, failed.text
            assert failed.json()["ticket"]["dispatch_status"] == "failed"

            first_retry = client.post(
                f"{base_path}/external-tickets/{ticket['id']}:retry-dispatch",
                headers=_headers(correlation_id, f"retry-before-sync-{run_id}"),
                json={"expected_version": 2, "reason": "Retry after recorded failure"},
            )
            assert first_retry.status_code == 200, first_retry.text
            assert first_retry.json()["ticket"]["version"] == 3

            synced = client.post(
                f"{base_path}/external-tickets/{ticket['id']}:sync-status",
                headers=_headers(correlation_id, f"sync-{run_id}"),
                json={
                    "status": "done",
                    "expected_version": 3,
                    "external_updated_at": external_at.isoformat(),
                    "source": "adapter",
                    "reason": "Main infrastructure live verification completed",
                },
            )
            assert synced.status_code == 200, synced.text
            assert synced.json()["ticket"]["version"] == 4
            assert synced.json()["ticket"]["dispatch_status"] == "succeeded"

            conflict = client.post(
                f"{base_path}/external-tickets/{ticket['id']}:sync-status",
                headers=_headers(correlation_id, f"conflict-{run_id}"),
                json={
                    "status": "in_progress",
                    "expected_version": 1,
                    "external_updated_at": (external_at + timedelta(seconds=1)).isoformat(),
                    "source": "adapter",
                },
            )
            assert conflict.status_code == 409
            assert conflict.json()["error"]["error_code"] == "version_conflict"

            hidden = client.get(
                f"/api/v1/projects/other-{project_id}/external-tickets/{ticket['id']}",
                headers=_headers(correlation_id),
            )
            assert hidden.status_code == 404
    finally:
        first_container.close()

    second_container = build_container()
    try:
        with TestClient(build_app(container=second_container)) as client:
            fetched = client.get(
                f"{base_path}/external-tickets/{ticket['id']}",
                headers=_headers(correlation_id),
            )
            assert fetched.status_code == 200, fetched.text
            persisted = fetched.json()["ticket"]
            assert persisted["status"] == "done"
            assert persisted["version"] == 4
            assert persisted["priority"] == "high"
            assert persisted["labels"] == ["live", "ticketing"]

            listed = client.get(
                f"{base_path}/external-tickets",
                headers=_headers(correlation_id),
                params={"connector_id": connector_id, "status": "done", "page_size": 1},
            )
            assert listed.status_code == 200, listed.text
            assert [item["id"] for item in listed.json()["items"]] == [ticket["id"]]

            page_one = client.get(
                f"{base_path}/external-tickets",
                headers=_headers(correlation_id),
                params={"connector_id": connector_id, "page_size": 1},
            )
            assert page_one.status_code == 200, page_one.text
            page_token = page_one.json()["next_page_token"]
            assert page_token
            page_two = client.get(
                f"{base_path}/external-tickets",
                headers=_headers(correlation_id),
                params={"connector_id": connector_id, "page_size": 1, "page_token": page_token},
            )
            assert page_two.status_code == 200, page_two.text
            assert {
                page_one.json()["items"][0]["id"],
                page_two.json()["items"][0]["id"],
            } == {ticket["id"], second_ticket_id}
            assert page_two.json()["next_page_token"] is None

            retried = client.post(
                f"{base_path}/external-tickets/{ticket['id']}:retry-dispatch",
                headers=_headers(correlation_id, f"retry-{run_id}"),
                json={"expected_version": 4, "reason": "Verify durable retry command"},
            )
            assert retried.status_code == 200, retried.text
            assert retried.json()["ticket"]["version"] == 5
            assert retried.json()["ticket"]["dispatch_attempts"] == 3

        events = [
            event
            for event in second_container.service.store.outbox()
            if event.get("correlation_id") == correlation_id
        ]
        event_types = {event["event_type"] for event in events}
        assert {
            "ExternalTicketCreated",
            "ExternalTicketDispatchRequested",
            "ExternalTicketDispatchFailed",
            "ExternalStatusSynced",
            "ExternalTicketDispatchSucceeded",
            "ExternalStatusRejected",
        } <= event_types
    finally:
        second_container.close()

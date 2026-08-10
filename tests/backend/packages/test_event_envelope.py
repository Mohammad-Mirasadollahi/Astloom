from __future__ import annotations

from contracts import (
    REQUIRED_ENVELOPE_FIELDS,
    make_event_envelope,
    validate_event_envelope,
)


def test_event_envelope_round_trip():
    payload = make_event_envelope(
        event_type="core_data.record_created",
        correlation_id="corr_1",
        tenant_id="t1",
        workspace_id="w1",
        project_id="p1",
        payload={"id": "rec_1"},
        producer="core-data-service",
    )
    assert validate_event_envelope(payload) == []
    assert payload["producer"] == "core-data-service"
    assert isinstance(payload["payload"], dict)


def test_producer_optional():
    payload = make_event_envelope(
        event_type="memory.item_upserted",
        correlation_id="corr_2",
        tenant_id="t1",
        workspace_id="w1",
        project_id="p1",
    )
    assert "producer" not in payload
    assert validate_event_envelope(payload) == []


def test_missing_required_fields():
    errors = validate_event_envelope({"event_type": "x"})
    for field in REQUIRED_ENVELOPE_FIELDS:
        if field == "event_type":
            continue
        assert f"missing {field}" in errors


def test_payload_must_be_object():
    envelope = make_event_envelope(
        event_type="docs.document_synced",
        correlation_id="corr_3",
        tenant_id="t1",
        workspace_id="w1",
        project_id="p1",
    )
    envelope["payload"] = "not-a-dict"
    assert "payload must be an object" in validate_event_envelope(envelope)


def test_empty_strings_rejected():
    envelope = make_event_envelope(
        event_type="x",
        correlation_id="corr_4",
        tenant_id="t1",
        workspace_id="w1",
        project_id="p1",
    )
    envelope["event_id"] = "  "
    assert "event_id must be a non-empty string" in validate_event_envelope(envelope)


def test_legacy_event_version_alias():
    errors = validate_event_envelope(
        {
            "event_id": "e1",
            "event_type": "core_data.record_created",
            "event_version": 1,
            "occurred_at": "2026-01-01T00:00:00Z",
            "correlation_id": "c1",
            "tenant_id": "t1",
            "workspace_id": "w1",
            "project_id": "p1",
            "payload": {},
        }
    )
    assert errors == []

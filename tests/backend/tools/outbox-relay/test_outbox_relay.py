from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "backend" / "packages"))
sys.path.insert(0, str(ROOT / "backend" / "services" / "memory-service" / "src"))
sys.path.insert(0, str(ROOT / "backend" / "services" / "audit-service" / "src"))
sys.path.insert(0, str(ROOT / "backend" / "services" / "adapter-service" / "src"))
sys.path.insert(0, str(ROOT / "backend" / "services" / "core-data-service" / "src"))

from adapter_service.core import AdapterService
from adapter_service.testing import InMemoryStore as AdapterStore
from audit_service.core import AuditService, Scope as AuditScope
from audit_service.testing import InMemoryStore as AuditStore
from core_data_service.core import CoreData, Kind, Scope as CoreScope
from core_data_service.testing import InMemoryStore as CoreStore
from memory_service.core import MemoryService, Scope as MemoryScope
from memory_service.testing import InMemoryStore as MemoryStore
from outbox_relay import (
    AuditMirrorHandler,
    BrokerForwardHandler,
    InMemoryOutboxSource,
    MemoryFromCoreDataHandler,
    OutboxRelay,
)


def _core_event_via_service() -> dict:
    store = CoreStore()
    service = CoreData(store)
    scope = CoreScope("t", "w", "p")
    service.create(
        Kind.TASK,
        scope,
        "actor-1",
        "corr-1",
        "idem-task-1",
        {
            "title": "Ship outbox",
            "assignee_type": "backend",
            "instructions": "Relay to memory and broker",
            "acceptance_criteria": ["done"],
        },
    )
    events = store.outbox()
    assert events
    return events[-1]


def test_outbox_relay_runs_all_handlers():
    event = _core_event_via_service()
    source = InMemoryOutboxSource("core-data", [event])
    memory = MemoryService(MemoryStore())
    audit = AuditService(AuditStore())
    adapter = AdapterService(AdapterStore())
    relay = OutboxRelay(
        [source],
        [
            MemoryFromCoreDataHandler(memory),
            AuditMirrorHandler(audit),
            BrokerForwardHandler(adapter),
        ],
    )
    result = relay.run_once()
    assert result.polled == 1
    assert result.published == 1
    assert not result.errors
    assert source.list_unpublished(10) == []

    mem_scope = MemoryScope("t", "w", "p")
    items = memory.store.list_memory(mem_scope)
    assert any("Ship outbox" in item.title for item in items)

    audit_scope = AuditScope("t", "w", "p")
    trail = audit.evidence_trail(audit_scope, event["payload"]["id"])
    assert trail

    from adapter_service.core import Scope as AdapterScope

    broker_events = adapter.store.list_events(AdapterScope("t", "w", "p"))
    assert broker_events
    assert broker_events[0].message["intent"] == "TASK_STARTED"


def test_second_run_is_noop():
    event = _core_event_via_service()
    source = InMemoryOutboxSource("core-data", [event])
    memory = MemoryService(MemoryStore())
    audit = AuditService(AuditStore())
    adapter = AdapterService(AdapterStore())
    relay = OutboxRelay(
        [source],
        [
            MemoryFromCoreDataHandler(memory),
            AuditMirrorHandler(audit),
            BrokerForwardHandler(adapter),
        ],
    )
    first = relay.run_once()
    second = relay.run_once()
    assert first.published == 1
    assert second.polled == 0
    assert second.published == 0


def test_outbox_source_specs_cover_both_ddl_families():
    from outbox_relay import OUTBOX_SOURCES

    shapes = {spec.name: spec for spec in OUTBOX_SOURCES}
    assert shapes["core-data"].shape == "event_id"
    assert shapes["audit"].shape == "seq"
    assert shapes["code-graph"].time_column == "created_at"
    assert len(OUTBOX_SOURCES) == 12


def test_seq_shaped_payload_is_relayed_to_audit():
    """Seq DDL stores only payload jsonb; relay must lift event_type from payload."""
    event = {
        "event_id": "evt_audit_1",
        "event_type": "principal.upserted",
        "tenant_id": "t",
        "workspace_id": "w",
        "project_id": "p",
        "actor_ref": "iam",
        "correlation_id": "corr-seq",
        "payload": {"id": "prin_1"},
        "occurred_at": "2026-01-01T00:00:00Z",
    }
    source = InMemoryOutboxSource("identity-access", [event])
    audit = AuditService(AuditStore())
    relay = OutboxRelay([source], [AuditMirrorHandler(audit)])
    result = relay.run_once()
    assert result.published == 1
    trail = audit.evidence_trail(AuditScope("t", "w", "p"), "prin_1")
    assert trail
    assert trail[0]["action"] == "outbox.identity-access.principal.upserted"

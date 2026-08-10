"""Factory for production handlers wired to in-process service stores."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SERVICES = ROOT / "backend" / "services"
PACKAGES = ROOT / "backend" / "packages"


def _ensure(path: Path) -> None:
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)


def build_default_handlers(
    *,
    database_url: str,
    config: Any,
    environ: dict[str, str] | None = None,
) -> list[Any]:
    env = environ if environ is not None else os.environ
    _ensure(PACKAGES)
    for name in ("memory-service", "audit-service", "adapter-service"):
        _ensure(SERVICES / name / "src")

    from adapter_service.core import AdapterService
    from adapter_service.postgres_store import PostgresStore as AdapterStore
    from adapter_service.testing import InMemoryStore as AdapterMemory
    from adapter_service.trackers import build_tracker_registry
    from audit_service.core import AuditService
    from audit_service.postgres_store import PostgresStore as AuditStore
    from audit_service.testing import InMemoryStore as AuditMemory
    from memory_service.core import MemoryService
    from memory_service.postgres_store import PostgresStore as MemoryStore
    from memory_service.testing import InMemoryStore as MemoryMemory

    from .handlers import (
        AuditMirrorHandler,
        BrokerForwardHandler,
        MemoryFromCoreDataHandler,
        TicketDispatchHandler,
    )

    use_memory = str(env.get("ASTLOOM_OUTBOX_HANDLER_STORE") or "").strip().lower() == "memory"
    if use_memory:
        memory = MemoryService(MemoryMemory())
        audit = AuditService(AuditMemory())
        adapter = AdapterService(AdapterMemory(), tracker_adapters=build_tracker_registry(env))
    else:
        memory = MemoryService(MemoryStore(database_url))
        audit = AuditService(AuditStore(database_url))
        adapter = AdapterService(AdapterStore(database_url), tracker_adapters=build_tracker_registry(env))

    handlers: list[Any] = []
    if config.enable_memory_handler:
        handlers.append(MemoryFromCoreDataHandler(memory))
    if config.enable_audit_handler:
        handlers.append(AuditMirrorHandler(audit))
    if config.enable_broker_handler:
        handlers.append(BrokerForwardHandler(adapter))
    if getattr(config, "enable_ticket_dispatch_handler", True):
        handlers.append(TicketDispatchHandler(adapter))
    return handlers

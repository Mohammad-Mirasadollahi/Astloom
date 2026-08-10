from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

OutboxShape = Literal["event_id", "seq"]
TimeColumn = Literal["occurred_at", "created_at"]


@dataclass(frozen=True)
class OutboxSourceSpec:
    name: str
    schema: str
    shape: OutboxShape
    time_column: TimeColumn = "occurred_at"


# Every service outbox that participates in the platform spine.
OUTBOX_SOURCES: tuple[OutboxSourceSpec, ...] = (
    OutboxSourceSpec("core-data", "core_data", "event_id"),
    OutboxSourceSpec("memory", "memory", "event_id"),
    OutboxSourceSpec("docs-sync", "docs_sync", "event_id"),
    OutboxSourceSpec("code-graph", "code_graph", "event_id", "created_at"),
    OutboxSourceSpec("rule-engine", "rule_engine", "event_id"),
    OutboxSourceSpec("adapter", "adapter", "event_id"),
    OutboxSourceSpec("audit", "audit", "seq"),
    OutboxSourceSpec("identity-access", "identity_access", "seq"),
    OutboxSourceSpec("orchestration", "orchestration", "seq"),
    OutboxSourceSpec("reporting", "reporting", "seq"),
    OutboxSourceSpec("project-profile", "project_profile", "seq"),
    OutboxSourceSpec("common-context", "common_context", "seq"),
)


@dataclass(frozen=True)
class RelayConfig:
    database_url: str
    batch_size: int = 100
    poll_interval_seconds: float = 2.0
    enabled_sources: tuple[str, ...] = field(
        default_factory=lambda: tuple(spec.name for spec in OUTBOX_SOURCES)
    )
    enable_memory_handler: bool = True
    enable_audit_handler: bool = True
    enable_broker_handler: bool = True
    enable_ticket_dispatch_handler: bool = True


def load_relay_config(environ: dict[str, str] | None = None) -> RelayConfig:
    env = environ if environ is not None else os.environ
    database_url = str(env.get("ASTLOOM_DATABASE_URL") or "").strip()
    if not database_url:
        raise ValueError("ASTLOOM_DATABASE_URL is required for the outbox relay")
    sources_raw = str(env.get("ASTLOOM_OUTBOX_SOURCES") or "").strip()
    if sources_raw:
        enabled = tuple(part.strip() for part in sources_raw.split(",") if part.strip())
    else:
        enabled = tuple(spec.name for spec in OUTBOX_SOURCES)
    return RelayConfig(
        database_url=database_url,
        batch_size=max(1, int(env.get("ASTLOOM_OUTBOX_BATCH_SIZE") or "100")),
        poll_interval_seconds=max(0.1, float(env.get("ASTLOOM_OUTBOX_POLL_INTERVAL") or "2")),
        enabled_sources=enabled,
        enable_memory_handler=_flag(env, "ASTLOOM_OUTBOX_MEMORY_HANDLER", True),
        enable_audit_handler=_flag(env, "ASTLOOM_OUTBOX_AUDIT_HANDLER", True),
        enable_broker_handler=_flag(env, "ASTLOOM_OUTBOX_BROKER_HANDLER", True),
        enable_ticket_dispatch_handler=_flag(env, "ASTLOOM_OUTBOX_TICKET_DISPATCH_HANDLER", True),
    )


def _flag(env: dict[str, str], key: str, default: bool) -> bool:
    raw = str(env.get(key) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}

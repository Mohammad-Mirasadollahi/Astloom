"""Per-store Postgres table registry for scoped export/import."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TableSpec:
    store_id: str
    schema: str
    table: str
    # Columns that need ::text on export and cast on import (pgvector).
    vector_columns: tuple[str, ...] = ()


# Order: parents / catalogs first, then analytical stores, then derivatives.
STORE_ORDER: tuple[str, ...] = (
    "project_profile",
    "identity_access",
    "common_context",
    "core_data",
    "memory",
    "code_graph",
    "docs_sync",
    "rule_engine",
    "adapter",
    "orchestration",
    "audit",
    "reporting",
    "local",
)

PG_TABLES: tuple[TableSpec, ...] = (
    TableSpec("project_profile", "project_profile", "documents"),
    TableSpec("identity_access", "identity_access", "documents"),
    TableSpec("common_context", "common_context", "documents"),
    TableSpec("core_data", "core_data", "records"),
    TableSpec("memory", "memory", "memory_items"),
    TableSpec("memory", "memory", "question_memory"),
    TableSpec("memory", "memory", "work_batches"),
    TableSpec("memory", "memory", "memory_embeddings", vector_columns=("embedding",)),
    TableSpec("memory", "memory", "embedding_id_map"),
    TableSpec("code_graph", "code_graph", "symbols"),
    TableSpec("code_graph", "code_graph", "edges"),
    TableSpec("code_graph", "code_graph", "symbol_embeddings", vector_columns=("embedding",)),
    TableSpec("code_graph", "code_graph", "embedding_id_map"),
    TableSpec("docs_sync", "docs_sync", "symbols"),
    TableSpec("docs_sync", "docs_sync", "documents"),
    TableSpec("docs_sync", "docs_sync", "anchors"),
    TableSpec("docs_sync", "docs_sync", "drift_findings"),
    TableSpec("docs_sync", "docs_sync", "drafts"),
    TableSpec("rule_engine", "rule_engine", "rules"),
    TableSpec("rule_engine", "rule_engine", "evaluations"),
    TableSpec("rule_engine", "rule_engine", "approvals"),
    TableSpec("rule_engine", "rule_engine", "routed_tasks"),
    TableSpec("rule_engine", "rule_engine", "anomalies"),
    TableSpec("rule_engine", "rule_engine", "feedback"),
    TableSpec("rule_engine", "rule_engine", "impact_maps"),
    TableSpec("adapter", "adapter", "connectors"),
    TableSpec("adapter", "adapter", "mappings"),
    TableSpec("adapter", "adapter", "subscriptions"),
    TableSpec("adapter", "adapter", "external_tickets"),
    TableSpec("adapter", "adapter", "department_tasks"),
    TableSpec("orchestration", "orchestration", "documents"),
    TableSpec("audit", "audit", "documents"),
    TableSpec("reporting", "reporting", "documents"),
)


def tables_for_store(store_id: str) -> list[TableSpec]:
    return [t for t in PG_TABLES if t.store_id == store_id]

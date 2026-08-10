-- Durable entity_ref → uint64 map for TurboVec IdMapIndex (GAP-T03 / ADR 08).
-- Preferred over bare hash; keeps reverse lookup and collision-safe allocation.

CREATE TABLE IF NOT EXISTS code_graph.embedding_id_map (
    entity_ref   text        PRIMARY KEY,
    uint64_id    bigint      NOT NULL UNIQUE,
    tenant_id    text        NOT NULL,
    workspace_id text        NOT NULL,
    project_id   text        NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS code_graph_embedding_id_map_scope_idx
    ON code_graph.embedding_id_map (tenant_id, workspace_id, project_id);

CREATE INDEX IF NOT EXISTS code_graph_embedding_id_map_uint64_idx
    ON code_graph.embedding_id_map (uint64_id);

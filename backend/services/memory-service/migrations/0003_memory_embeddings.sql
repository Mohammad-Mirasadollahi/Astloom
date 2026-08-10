-- GAP-T03: durable memory embeddings SoR (pgvector vector(1024)).
-- TurboVec is optional rebuildable replica only — never write SoR there.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS memory.memory_embeddings (
    memory_id text PRIMARY KEY REFERENCES memory.memory_items (id) ON DELETE CASCADE,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    model text NOT NULL,
    dims integer NOT NULL CHECK (dims > 0),
    embedding vector(1024) NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS memory_embeddings_scope_idx
    ON memory.memory_embeddings (tenant_id, workspace_id, project_id);

CREATE INDEX IF NOT EXISTS memory_embeddings_hnsw_idx
    ON memory.memory_embeddings
    USING hnsw (embedding vector_cosine_ops);

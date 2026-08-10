-- Semantic embedding index for Code-Knowledge Graph (pgvector).
-- Structural graph may live in Neo4j; embeddings remain in PostgreSQL.
-- Kind filter for Stage-1 hybrid RAG is added in 0004_symbol_embeddings_kind.sql.
-- NOTE: Production width is vector(1024) (BGE-large). Migration 0005 guards
-- legacy widths and requires an explicit backed-up operator migration.

CREATE TABLE IF NOT EXISTS code_graph.symbol_embeddings (
    symbol_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    model text NOT NULL,
    dims integer NOT NULL CHECK (dims > 0),
    embedding vector(1024) NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS code_graph_symbol_embeddings_scope_idx
    ON code_graph.symbol_embeddings (tenant_id, workspace_id, project_id);

-- Production dims match BGE-large (1024). HNSW needs rows; create after data lands in ops.
CREATE INDEX IF NOT EXISTS code_graph_symbol_embeddings_hnsw_idx
    ON code_graph.symbol_embeddings
    USING hnsw (embedding vector_cosine_ops);

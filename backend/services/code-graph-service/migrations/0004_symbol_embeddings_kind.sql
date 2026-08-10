-- Stage-1 RAG: kind column for SQL filter before ANN (exclude file/import/unresolved).

ALTER TABLE code_graph.symbol_embeddings
    ADD COLUMN IF NOT EXISTS kind text NOT NULL DEFAULT 'unknown';

CREATE INDEX IF NOT EXISTS code_graph_symbol_embeddings_scope_kind_idx
    ON code_graph.symbol_embeddings (tenant_id, workspace_id, project_id, kind);

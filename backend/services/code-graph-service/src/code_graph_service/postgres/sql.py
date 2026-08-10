"""PostgreSQL SQL strings for pgvector embeddings + outbox mirror.

Role: own query text for ``PostgresEmbeddingIndex`` / ``PostgresOutboxMirror``.
Source of truth: ``code_graph.symbol_embeddings`` and ``code_graph.outbox`` DDL/DML.
Allowed: parameterized statements; dims-templated DDL via helpers.
Forbidden: embedding business logic; opening connections here.
"""

from __future__ import annotations

EMBEDDING_MIGRATION_FILES = (
    "0003_symbol_embeddings.sql",
    "0004_symbol_embeddings_kind.sql",
    "0005_symbol_embeddings_dims_1024.sql",
    "0009_embedding_id_map.sql",
)

SELECT_EMBEDDING_COLUMN_TYPE = """
SELECT format_type(a.atttypid, a.atttypmod) AS typ
FROM pg_attribute a
JOIN pg_class c ON c.oid = a.attrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'code_graph'
  AND c.relname = 'symbol_embeddings'
  AND a.attname = 'embedding'
  AND a.attnum > 0
  AND NOT a.attisdropped
"""

CREATE_SCOPE_IDX = """
CREATE INDEX code_graph_symbol_embeddings_scope_idx
    ON code_graph.symbol_embeddings (tenant_id, workspace_id, project_id)
"""

CREATE_SCOPE_KIND_IDX = """
CREATE INDEX code_graph_symbol_embeddings_scope_kind_idx
    ON code_graph.symbol_embeddings (tenant_id, workspace_id, project_id, kind)
"""

CREATE_HNSW_IDX = """
CREATE INDEX code_graph_symbol_embeddings_hnsw_idx
    ON code_graph.symbol_embeddings
    USING hnsw (embedding vector_cosine_ops)
"""

UPSERT_EMBEDDING = """
INSERT INTO code_graph.symbol_embeddings (
    symbol_id, tenant_id, workspace_id, project_id, model, dims, kind, embedding, updated_at
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s::vector, now()
)
ON CONFLICT (symbol_id) DO UPDATE SET
    tenant_id = EXCLUDED.tenant_id,
    workspace_id = EXCLUDED.workspace_id,
    project_id = EXCLUDED.project_id,
    model = EXCLUDED.model,
    dims = EXCLUDED.dims,
    kind = EXCLUDED.kind,
    embedding = EXCLUDED.embedding,
    updated_at = now()
"""

DELETE_EMBEDDING = """
DELETE FROM code_graph.symbol_embeddings
WHERE symbol_id = %s
  AND tenant_id = %s
  AND workspace_id = %s
  AND project_id = %s
"""

DELETE_EMBEDDINGS = """
DELETE FROM code_graph.symbol_embeddings
WHERE symbol_id = ANY(%s)
  AND tenant_id = %s
  AND workspace_id = %s
  AND project_id = %s
"""

WIPE_EMBEDDINGS_SCOPE = """
DELETE FROM code_graph.symbol_embeddings
WHERE tenant_id = %s AND workspace_id = %s AND project_id = %s
"""

LIST_EMBEDDING_MODELS = """
SELECT symbol_id, model
FROM code_graph.symbol_embeddings
WHERE tenant_id = %s AND workspace_id = %s AND project_id = %s
"""

SEARCH_EMBEDDINGS = """
SELECT symbol_id,
       1 - (embedding <=> %s::vector) AS score
FROM code_graph.symbol_embeddings
WHERE tenant_id = %s
  AND workspace_id = %s
  AND project_id = %s
  AND kind = ANY(%s)
ORDER BY embedding <=> %s::vector
LIMIT %s
"""

APPEND_OUTBOX_EVENT = """
INSERT INTO code_graph.outbox (event_id, event_type, payload)
VALUES (%s, %s, %s)
ON CONFLICT (event_id) DO NOTHING
"""


def create_symbol_embeddings_table(dims: int) -> str:
    """DDL for ``symbol_embeddings`` at the configured vector width."""
    width = int(dims)
    if width < 1:
        raise ValueError("dims must be positive")
    return f"""
CREATE TABLE code_graph.symbol_embeddings (
    symbol_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    model text NOT NULL,
    dims integer NOT NULL CHECK (dims > 0),
    kind text NOT NULL DEFAULT 'unknown',
    embedding vector({width}) NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
)
"""


def expected_vector_type(dims: int) -> str:
    return f"vector({int(dims)})"

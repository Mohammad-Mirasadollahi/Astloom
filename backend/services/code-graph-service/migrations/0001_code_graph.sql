CREATE SCHEMA IF NOT EXISTS code_graph;

CREATE TABLE IF NOT EXISTS code_graph.symbols (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    project_group_id text,
    kind text NOT NULL,
    file_path text NOT NULL,
    name text NOT NULL,
    qualified_name text NOT NULL,
    signature text NOT NULL,
    body text NOT NULL,
    hash_value text NOT NULL,
    ai_documentation text NOT NULL,
    doc_status text NOT NULL,
    embedding jsonb NOT NULL,
    visibility text NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS code_graph_symbols_scope_name_idx
    ON code_graph.symbols (tenant_id, workspace_id, project_id, qualified_name);

CREATE TABLE IF NOT EXISTS code_graph.edges (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    project_group_id text,
    rel_type text NOT NULL,
    source_id text NOT NULL,
    target_id text NOT NULL,
    confidence text NOT NULL,
    metadata jsonb NOT NULL
);

CREATE INDEX IF NOT EXISTS code_graph_edges_scope_source_idx
    ON code_graph.edges (tenant_id, workspace_id, project_id, source_id);

CREATE TABLE IF NOT EXISTS code_graph.idempotency (
    scope_key text NOT NULL,
    idempotency_key text NOT NULL,
    resource_type text NOT NULL,
    resource_id text NOT NULL,
    PRIMARY KEY (scope_key, idempotency_key, resource_type)
);

CREATE TABLE IF NOT EXISTS code_graph.outbox (
    event_id text PRIMARY KEY,
    event_type text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

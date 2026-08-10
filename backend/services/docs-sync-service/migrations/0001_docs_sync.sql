CREATE SCHEMA IF NOT EXISTS docs_sync;

CREATE TABLE IF NOT EXISTS docs_sync.symbols (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    project_group_id text,
    actor_id text NOT NULL,
    correlation_id text NOT NULL,
    repo text NOT NULL,
    file_path text NOT NULL,
    symbol_path text NOT NULL,
    kind text NOT NULL,
    signature_hash text NOT NULL,
    body_hash text NOT NULL,
    doc_required boolean NOT NULL,
    tags jsonb NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS docs_sync_symbols_scope_created_idx
    ON docs_sync.symbols (tenant_id, workspace_id, project_id, created_at, id);

CREATE TABLE IF NOT EXISTS docs_sync.documents (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    project_group_id text,
    actor_id text NOT NULL,
    correlation_id text NOT NULL,
    path text NOT NULL,
    title text NOT NULL,
    owner text NOT NULL,
    state text NOT NULL,
    schema_version text NOT NULL,
    linked_symbols jsonb NOT NULL,
    decision_refs jsonb NOT NULL,
    frontmatter jsonb NOT NULL,
    body text NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS docs_sync_documents_scope_created_idx
    ON docs_sync.documents (tenant_id, workspace_id, project_id, created_at, id);

CREATE TABLE IF NOT EXISTS docs_sync.anchors (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    project_group_id text,
    doc_id text NOT NULL,
    symbol_id text NOT NULL,
    recorded_hash text NOT NULL,
    status text NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS docs_sync_anchors_scope_symbol_idx
    ON docs_sync.anchors (tenant_id, workspace_id, project_id, symbol_id, created_at, id);

CREATE TABLE IF NOT EXISTS docs_sync.drift_findings (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    project_group_id text,
    actor_id text NOT NULL,
    correlation_id text NOT NULL,
    symbol_id text NOT NULL,
    doc_id text,
    drift_type text NOT NULL,
    old_hash text,
    new_hash text NOT NULL,
    severity text NOT NULL,
    status text NOT NULL,
    issue_ref text NOT NULL,
    task_ref text,
    evidence_refs jsonb NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS docs_sync_findings_scope_created_idx
    ON docs_sync.drift_findings (tenant_id, workspace_id, project_id, created_at, id);

CREATE TABLE IF NOT EXISTS docs_sync.drafts (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    project_group_id text,
    actor_id text NOT NULL,
    correlation_id text NOT NULL,
    symbol_id text NOT NULL,
    finding_id text,
    title text NOT NULL,
    body text NOT NULL,
    state text NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS docs_sync.idempotency (
    scope_key text NOT NULL,
    command text NOT NULL,
    idempotency_key text NOT NULL,
    fingerprint text NOT NULL,
    record_id text NOT NULL,
    PRIMARY KEY (scope_key, command, idempotency_key)
);

CREATE TABLE IF NOT EXISTS docs_sync.outbox (
    event_id text PRIMARY KEY,
    event_type text NOT NULL,
    payload jsonb NOT NULL,
    occurred_at timestamptz NOT NULL
);

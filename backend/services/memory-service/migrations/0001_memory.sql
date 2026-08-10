CREATE SCHEMA IF NOT EXISTS memory;

CREATE TABLE IF NOT EXISTS memory.memory_items (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    project_group_id text,
    actor_id text NOT NULL,
    correlation_id text NOT NULL,
    kind text NOT NULL,
    state text NOT NULL,
    title text NOT NULL,
    body text NOT NULL,
    tags jsonb NOT NULL,
    evidence_refs jsonb NOT NULL,
    source_refs jsonb NOT NULL,
    confidence double precision NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS memory_items_scope_created_idx
    ON memory.memory_items (tenant_id, workspace_id, project_id, created_at, id);

CREATE TABLE IF NOT EXISTS memory.question_memory (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    project_group_id text,
    actor_id text NOT NULL,
    correlation_id text NOT NULL,
    normalized_question text NOT NULL,
    observations integer NOT NULL CHECK (observations > 0),
    evidence_refs jsonb NOT NULL,
    state text NOT NULL,
    answer text,
    version integer NOT NULL CHECK (version > 0),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    UNIQUE (tenant_id, workspace_id, project_id, normalized_question)
);

CREATE TABLE IF NOT EXISTS memory.work_batches (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    project_group_id text,
    actor_id text NOT NULL,
    correlation_id text NOT NULL,
    title text NOT NULL,
    item_refs jsonb NOT NULL,
    deferred_actions jsonb NOT NULL,
    state text NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS work_batches_scope_created_idx
    ON memory.work_batches (tenant_id, workspace_id, project_id, created_at, id);

CREATE TABLE IF NOT EXISTS memory.idempotency (
    scope_key text NOT NULL,
    command text NOT NULL,
    idempotency_key text NOT NULL,
    fingerprint text NOT NULL,
    record_id text NOT NULL,
    PRIMARY KEY (scope_key, command, idempotency_key)
);

CREATE TABLE IF NOT EXISTS memory.outbox (
    event_id text PRIMARY KEY,
    event_type text NOT NULL,
    payload jsonb NOT NULL,
    occurred_at timestamptz NOT NULL
);

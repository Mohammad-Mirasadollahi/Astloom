CREATE SCHEMA IF NOT EXISTS core_data;

CREATE TABLE IF NOT EXISTS core_data.records (
    id text PRIMARY KEY,
    kind text NOT NULL,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    actor_id text NOT NULL,
    correlation_id text NOT NULL,
    status text NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    data jsonb NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS core_data_records_scope_kind_created_idx
    ON core_data.records (tenant_id, workspace_id, project_id, kind, created_at, id);

CREATE TABLE IF NOT EXISTS core_data.idempotency (
    scope_key text NOT NULL,
    command text NOT NULL,
    idempotency_key text NOT NULL,
    fingerprint text NOT NULL,
    record_id text NOT NULL,
    PRIMARY KEY (scope_key, command, idempotency_key)
);

CREATE TABLE IF NOT EXISTS core_data.outbox (
    event_id text PRIMARY KEY,
    event_type text NOT NULL,
    payload jsonb NOT NULL,
    occurred_at timestamptz NOT NULL
);

-- identity-access-service persistence
CREATE SCHEMA IF NOT EXISTS identity_access;

CREATE TABLE IF NOT EXISTS identity_access.documents (
    id text PRIMARY KEY,
    kind text NOT NULL,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS identity_access_documents_scope_kind_idx
    ON identity_access.documents (tenant_id, workspace_id, project_id, kind, id);

CREATE TABLE IF NOT EXISTS identity_access.idempotency (
    scope_key text NOT NULL,
    resource text NOT NULL,
    idempotency_key text NOT NULL,
    resource_id text NOT NULL,
    PRIMARY KEY (scope_key, resource, idempotency_key)
);

CREATE TABLE IF NOT EXISTS identity_access.outbox (
    seq bigserial PRIMARY KEY,
    payload jsonb NOT NULL,
    occurred_at timestamptz NOT NULL DEFAULT now()
);

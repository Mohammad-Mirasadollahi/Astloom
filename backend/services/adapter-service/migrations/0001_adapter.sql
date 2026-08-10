CREATE SCHEMA IF NOT EXISTS adapter;

CREATE TABLE IF NOT EXISTS adapter.connectors (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    project_group_id text,
    actor_id text NOT NULL,
    correlation_id text NOT NULL,
    vendor text NOT NULL,
    name text NOT NULL,
    capabilities jsonb NOT NULL,
    auth_profile text NOT NULL,
    trust_level text NOT NULL,
    status text NOT NULL,
    credential_fingerprint text NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS adapter.mappings (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    project_group_id text,
    connector_id text NOT NULL,
    vendor_schema_version text NOT NULL,
    field_map jsonb NOT NULL,
    status text NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS adapter.subscriptions (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    project_group_id text,
    actor_id text NOT NULL,
    correlation_id text NOT NULL,
    channel text NOT NULL,
    subscriber_type text NOT NULL,
    endpoint text NOT NULL,
    filter_intents jsonb NOT NULL,
    filter_domains jsonb NOT NULL,
    status text NOT NULL,
    fail_mode text NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS adapter.broker_events (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    project_group_id text,
    channel text NOT NULL,
    message jsonb NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS adapter_broker_events_scope_channel_idx
    ON adapter.broker_events (tenant_id, workspace_id, project_id, channel, created_at, id);

CREATE TABLE IF NOT EXISTS adapter.deliveries (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    project_group_id text,
    event_id text NOT NULL,
    subscription_id text NOT NULL,
    status text NOT NULL,
    attempts integer NOT NULL,
    last_error text,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS adapter.dead_letters (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    project_group_id text,
    event_id text NOT NULL,
    subscription_id text NOT NULL,
    reason text NOT NULL,
    message jsonb NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS adapter.external_tickets (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    project_group_id text,
    actor_id text NOT NULL,
    correlation_id text NOT NULL,
    connector_id text NOT NULL,
    external_ref text NOT NULL,
    title text NOT NULL,
    status text NOT NULL,
    department text NOT NULL,
    source_event_id text,
    evidence_refs jsonb NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS adapter.department_tasks (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    project_group_id text,
    department text NOT NULL,
    title text NOT NULL,
    trigger_intent text NOT NULL,
    source_message_id text NOT NULL,
    approval_required boolean NOT NULL,
    status text NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS adapter.idempotency (
    scope_key text NOT NULL,
    command text NOT NULL,
    idempotency_key text NOT NULL,
    fingerprint text NOT NULL,
    record_id text NOT NULL,
    PRIMARY KEY (scope_key, command, idempotency_key)
);

CREATE TABLE IF NOT EXISTS adapter.outbox (
    event_id text PRIMARY KEY,
    event_type text NOT NULL,
    payload jsonb NOT NULL,
    occurred_at timestamptz NOT NULL
);

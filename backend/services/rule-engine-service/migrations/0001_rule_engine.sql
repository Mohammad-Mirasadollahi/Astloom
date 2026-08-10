CREATE SCHEMA IF NOT EXISTS rule_engine;

CREATE TABLE IF NOT EXISTS rule_engine.rules (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    project_group_id text,
    actor_id text NOT NULL,
    correlation_id text NOT NULL,
    title text NOT NULL,
    natural_language_rule text NOT NULL,
    severity text NOT NULL,
    owner text NOT NULL,
    evaluation_mode text NOT NULL,
    state text NOT NULL,
    domain text NOT NULL,
    examples jsonb NOT NULL,
    counterexamples jsonb NOT NULL,
    match_tags jsonb NOT NULL,
    required_approval_role text,
    precedence integer NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS rule_engine_rules_scope_created_idx
    ON rule_engine.rules (tenant_id, workspace_id, project_id, created_at, id);

CREATE TABLE IF NOT EXISTS rule_engine.evaluations (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    project_group_id text,
    actor_id text NOT NULL,
    correlation_id text NOT NULL,
    rule_id text NOT NULL,
    subject_ref text NOT NULL,
    verdict text NOT NULL,
    confidence double precision NOT NULL,
    rationale text NOT NULL,
    evidence_refs jsonb NOT NULL,
    used_llm boolean NOT NULL,
    state text NOT NULL,
    shadow boolean NOT NULL,
    risk_score double precision NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS rule_engine_evaluations_scope_created_idx
    ON rule_engine.evaluations (tenant_id, workspace_id, project_id, created_at, id);

CREATE TABLE IF NOT EXISTS rule_engine.approvals (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    project_group_id text,
    actor_id text NOT NULL,
    correlation_id text NOT NULL,
    evaluation_id text NOT NULL,
    rule_id text NOT NULL,
    approver text NOT NULL,
    status text NOT NULL,
    options jsonb NOT NULL,
    deadline timestamptz NOT NULL,
    decision_reason text,
    evidence_refs jsonb NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS rule_engine.routed_tasks (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    project_group_id text,
    actor_id text NOT NULL,
    correlation_id text NOT NULL,
    subject_ref text NOT NULL,
    title text NOT NULL,
    assignee_type text NOT NULL,
    reason text NOT NULL,
    evidence_refs jsonb NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS rule_engine.anomalies (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    project_group_id text,
    actor_id text NOT NULL,
    correlation_id text NOT NULL,
    subject_ref text NOT NULL,
    signal_type text NOT NULL,
    score double precision NOT NULL,
    rationale text NOT NULL,
    evidence_refs jsonb NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS rule_engine.feedback (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    project_group_id text,
    actor_id text NOT NULL,
    correlation_id text NOT NULL,
    evaluation_id text NOT NULL,
    label text NOT NULL,
    note text NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS rule_engine.impact_maps (
    id text PRIMARY KEY,
    tenant_id text NOT NULL,
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    project_group_id text,
    change_ref text NOT NULL,
    affected_entities jsonb NOT NULL,
    risk_level text NOT NULL,
    generated_task_refs jsonb NOT NULL,
    confidence double precision NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS rule_engine.idempotency (
    scope_key text NOT NULL,
    command text NOT NULL,
    idempotency_key text NOT NULL,
    fingerprint text NOT NULL,
    record_id text NOT NULL,
    PRIMARY KEY (scope_key, command, idempotency_key)
);

CREATE TABLE IF NOT EXISTS rule_engine.outbox (
    event_id text PRIMARY KEY,
    event_type text NOT NULL,
    payload jsonb NOT NULL,
    occurred_at timestamptz NOT NULL
);

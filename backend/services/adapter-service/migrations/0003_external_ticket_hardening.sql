ALTER TABLE adapter.external_tickets
    ADD COLUMN IF NOT EXISTS description_summary text,
    ADD COLUMN IF NOT EXISTS priority text,
    ADD COLUMN IF NOT EXISTS severity text,
    ADD COLUMN IF NOT EXISTS assignee_ref text,
    ADD COLUMN IF NOT EXISTS due_at timestamptz,
    ADD COLUMN IF NOT EXISTS labels jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS remote_url text,
    ADD COLUMN IF NOT EXISTS external_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS sync_source text,
    ADD COLUMN IF NOT EXISTS sync_reason text,
    ADD COLUMN IF NOT EXISTS last_sync_status text NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS last_sync_error text,
    ADD COLUMN IF NOT EXISTS dispatch_status text NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS dispatch_attempts integer NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS extension jsonb NOT NULL DEFAULT '{}'::jsonb;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'adapter_external_ticket_sync_status_check'
          AND connamespace = 'adapter'::regnamespace
    ) THEN
        ALTER TABLE adapter.external_tickets
            ADD CONSTRAINT adapter_external_ticket_sync_status_check
            CHECK (last_sync_status IN ('pending', 'succeeded', 'failed', 'dead_lettered'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'adapter_external_ticket_dispatch_status_check'
          AND connamespace = 'adapter'::regnamespace
    ) THEN
        ALTER TABLE adapter.external_tickets
            ADD CONSTRAINT adapter_external_ticket_dispatch_status_check
            CHECK (dispatch_status IN ('pending', 'succeeded', 'failed', 'dead_lettered'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'adapter_external_ticket_dispatch_attempts_check'
          AND connamespace = 'adapter'::regnamespace
    ) THEN
        ALTER TABLE adapter.external_tickets
            ADD CONSTRAINT adapter_external_ticket_dispatch_attempts_check
            CHECK (dispatch_attempts > 0);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'adapter_external_ticket_status_check'
          AND connamespace = 'adapter'::regnamespace
    ) THEN
        ALTER TABLE adapter.external_tickets
            ADD CONSTRAINT adapter_external_ticket_status_check
            CHECK (status IN ('open', 'in_progress', 'done', 'canceled'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS adapter_external_tickets_scope_updated_idx
    ON adapter.external_tickets (tenant_id, workspace_id, project_id, updated_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS adapter_external_tickets_scope_connector_status_idx
    ON adapter.external_tickets (tenant_id, workspace_id, project_id, connector_id, status);

CREATE INDEX IF NOT EXISTS adapter_external_tickets_scope_external_ref_idx
    ON adapter.external_tickets (tenant_id, workspace_id, project_id, external_ref);

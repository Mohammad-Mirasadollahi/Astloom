-- Retention controls for human-like remember / forget.
-- pinned: keep visible and boosted in default retrieval.
-- expires_at: optional working-memory TTL (lazy stale on access).

ALTER TABLE memory.memory_items
    ADD COLUMN IF NOT EXISTS pinned boolean NOT NULL DEFAULT false;

ALTER TABLE memory.memory_items
    ADD COLUMN IF NOT EXISTS expires_at timestamptz;

CREATE INDEX IF NOT EXISTS memory_items_scope_kind_state_idx
    ON memory.memory_items (tenant_id, workspace_id, project_id, kind, state);

CREATE INDEX IF NOT EXISTS memory_items_scope_pinned_idx
    ON memory.memory_items (tenant_id, workspace_id, project_id, pinned)
    WHERE pinned = true;

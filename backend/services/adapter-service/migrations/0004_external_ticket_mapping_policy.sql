-- Ticket status mapping and reopen policy on adapter.mappings
ALTER TABLE adapter.mappings
    ADD COLUMN IF NOT EXISTS status_map jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE adapter.mappings
    ADD COLUMN IF NOT EXISTS reopen_policy text NOT NULL DEFAULT 'allow_remote';
ALTER TABLE adapter.mappings
    ADD COLUMN IF NOT EXISTS unknown_status_policy text NOT NULL DEFAULT 'reject';
ALTER TABLE adapter.mappings
    ADD COLUMN IF NOT EXISTS fallback_status text NOT NULL DEFAULT 'open';
ALTER TABLE adapter.mappings
    ADD COLUMN IF NOT EXISTS mapping_version integer NOT NULL DEFAULT 1;

ALTER TABLE adapter.mappings
    DROP CONSTRAINT IF EXISTS adapter_mappings_reopen_policy_check;
ALTER TABLE adapter.mappings
    ADD CONSTRAINT adapter_mappings_reopen_policy_check
    CHECK (reopen_policy IN ('allow_remote', 'deny'));

ALTER TABLE adapter.mappings
    DROP CONSTRAINT IF EXISTS adapter_mappings_unknown_status_policy_check;
ALTER TABLE adapter.mappings
    ADD CONSTRAINT adapter_mappings_unknown_status_policy_check
    CHECK (unknown_status_policy IN ('reject', 'fallback'));

ALTER TABLE adapter.mappings
    DROP CONSTRAINT IF EXISTS adapter_mappings_fallback_status_check;
ALTER TABLE adapter.mappings
    ADD CONSTRAINT adapter_mappings_fallback_status_check
    CHECK (fallback_status IN ('open', 'in_progress', 'done', 'canceled'));

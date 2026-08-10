-- Outbox publication tracking for the Astloom outbox relay worker (seq + payload shape).
ALTER TABLE project_profile.outbox
    ADD COLUMN IF NOT EXISTS published_at timestamptz;

CREATE INDEX IF NOT EXISTS project_profile_outbox_unpublished_idx
    ON project_profile.outbox (occurred_at, seq)
    WHERE published_at IS NULL;

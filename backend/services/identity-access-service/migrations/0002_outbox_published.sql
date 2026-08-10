-- Outbox publication tracking for the Astloom outbox relay worker (seq + payload shape).
ALTER TABLE identity_access.outbox
    ADD COLUMN IF NOT EXISTS published_at timestamptz;

CREATE INDEX IF NOT EXISTS identity_access_outbox_unpublished_idx
    ON identity_access.outbox (occurred_at, seq)
    WHERE published_at IS NULL;

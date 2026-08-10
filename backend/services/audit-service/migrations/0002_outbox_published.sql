-- Outbox publication tracking for the Astloom outbox relay worker (seq + payload shape).
ALTER TABLE audit.outbox
    ADD COLUMN IF NOT EXISTS published_at timestamptz;

CREATE INDEX IF NOT EXISTS audit_outbox_unpublished_idx
    ON audit.outbox (occurred_at, seq)
    WHERE published_at IS NULL;

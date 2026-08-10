-- Outbox publication tracking for the Astloom outbox relay worker (seq + payload shape).
ALTER TABLE reporting.outbox
    ADD COLUMN IF NOT EXISTS published_at timestamptz;

CREATE INDEX IF NOT EXISTS reporting_outbox_unpublished_idx
    ON reporting.outbox (occurred_at, seq)
    WHERE published_at IS NULL;

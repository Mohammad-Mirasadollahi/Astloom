-- Outbox publication tracking for the Astloom outbox relay worker (seq + payload shape).
ALTER TABLE common_context.outbox
    ADD COLUMN IF NOT EXISTS published_at timestamptz;

CREATE INDEX IF NOT EXISTS common_context_outbox_unpublished_idx
    ON common_context.outbox (occurred_at, seq)
    WHERE published_at IS NULL;

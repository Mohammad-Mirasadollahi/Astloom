-- Outbox publication tracking for the Astloom outbox relay worker.
ALTER TABLE memory.outbox
    ADD COLUMN IF NOT EXISTS published_at timestamptz;

CREATE INDEX IF NOT EXISTS memory_outbox_unpublished_idx
    ON memory.outbox (occurred_at, event_id)
    WHERE published_at IS NULL;

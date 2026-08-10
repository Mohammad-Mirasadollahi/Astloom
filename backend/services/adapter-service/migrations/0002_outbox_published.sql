-- Outbox publication tracking for the Astloom outbox relay worker.
ALTER TABLE adapter.outbox
    ADD COLUMN IF NOT EXISTS published_at timestamptz;

CREATE INDEX IF NOT EXISTS adapter_outbox_unpublished_idx
    ON adapter.outbox (occurred_at, event_id)
    WHERE published_at IS NULL;

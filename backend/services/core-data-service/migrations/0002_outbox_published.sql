-- Outbox publication tracking for the Astloom outbox relay worker.
ALTER TABLE core_data.outbox
    ADD COLUMN IF NOT EXISTS published_at timestamptz;

CREATE INDEX IF NOT EXISTS core_data_outbox_unpublished_idx
    ON core_data.outbox (occurred_at, event_id)
    WHERE published_at IS NULL;

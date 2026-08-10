-- Outbox publication tracking for the Astloom outbox relay worker.
ALTER TABLE docs_sync.outbox
    ADD COLUMN IF NOT EXISTS published_at timestamptz;

CREATE INDEX IF NOT EXISTS docs_sync_outbox_unpublished_idx
    ON docs_sync.outbox (occurred_at, event_id)
    WHERE published_at IS NULL;

-- Outbox publication tracking for the Astloom outbox relay worker.
ALTER TABLE rule_engine.outbox
    ADD COLUMN IF NOT EXISTS published_at timestamptz;

CREATE INDEX IF NOT EXISTS rule_engine_outbox_unpublished_idx
    ON rule_engine.outbox (occurred_at, event_id)
    WHERE published_at IS NULL;

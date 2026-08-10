-- Outbox publication tracking for the Astloom outbox relay worker.
ALTER TABLE code_graph.outbox
    ADD COLUMN IF NOT EXISTS published_at timestamptz;

CREATE INDEX IF NOT EXISTS code_graph_outbox_unpublished_idx
    ON code_graph.outbox (created_at, event_id)
    WHERE published_at IS NULL;

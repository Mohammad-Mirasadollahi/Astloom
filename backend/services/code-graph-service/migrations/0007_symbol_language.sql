-- Persist source language on symbols (detected at ingest).
ALTER TABLE code_graph.symbols
    ADD COLUMN IF NOT EXISTS language text NOT NULL DEFAULT '';

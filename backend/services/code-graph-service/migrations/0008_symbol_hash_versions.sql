-- Persist content-hash algorithm identity on symbols (GAP-T01).
ALTER TABLE code_graph.symbols
    ADD COLUMN IF NOT EXISTS hash_version text NOT NULL DEFAULT '';
ALTER TABLE code_graph.symbols
    ADD COLUMN IF NOT EXISTS parser_version text NOT NULL DEFAULT '';
ALTER TABLE code_graph.symbols
    ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

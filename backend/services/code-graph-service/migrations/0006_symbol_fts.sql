-- Postgres full-text search for code_graph.symbols (BM25-ish via ts_rank_cd).
-- Applied by PostgresStore.ensure_schema / bootstrap when using postgres store.

ALTER TABLE code_graph.symbols
    ADD COLUMN IF NOT EXISTS search_document tsvector;

UPDATE code_graph.symbols
SET search_document =
    setweight(to_tsvector('english', coalesce(name, '')), 'A')
    || setweight(to_tsvector('english', coalesce(qualified_name, '')), 'A')
    || setweight(to_tsvector('english', coalesce(signature, '')), 'B')
    || setweight(to_tsvector('english', coalesce(file_path, '')), 'B')
    || setweight(to_tsvector('english', coalesce(ai_documentation, '')), 'C')
    || setweight(to_tsvector('english', left(coalesce(body, ''), 2000)), 'D')
WHERE search_document IS NULL;

CREATE INDEX IF NOT EXISTS code_graph_symbols_search_document_gin
    ON code_graph.symbols USING gin (search_document);

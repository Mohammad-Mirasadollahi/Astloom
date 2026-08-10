-- Guard the canonical BGE-large vector dimension without deleting indexed data.
-- A non-1024 table requires an explicit, backed-up operator migration.

DO $$
DECLARE
    typ text;
BEGIN
    SELECT format_type(a.atttypid, a.atttypmod)
      INTO typ
      FROM pg_attribute a
      JOIN pg_class c ON c.oid = a.attrelid
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'code_graph'
       AND c.relname = 'symbol_embeddings'
       AND a.attname = 'embedding'
       AND a.attnum > 0
       AND NOT a.attisdropped;

    IF typ IS NULL OR typ = 'vector(1024)' THEN
        RETURN;
    END IF;

    RAISE EXCEPTION
        'embedding schema dimension mismatch: database has %, expected vector(1024); run an explicit backed-up migration',
        typ;
END $$;

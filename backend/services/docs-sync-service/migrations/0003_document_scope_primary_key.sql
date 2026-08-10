DO $$
DECLARE
    primary_key_definition text;
    primary_key_name text;
BEGIN
    SELECT c.conname, pg_get_constraintdef(c.oid)
      INTO primary_key_name, primary_key_definition
      FROM pg_constraint AS c
     WHERE c.conrelid = 'docs_sync.documents'::regclass
       AND c.contype = 'p';

    IF primary_key_definition IS DISTINCT FROM
       'PRIMARY KEY (id, tenant_id, workspace_id, project_id)' THEN
        IF primary_key_name IS NOT NULL THEN
            EXECUTE format(
                'ALTER TABLE docs_sync.documents DROP CONSTRAINT %I',
                primary_key_name
            );
        END IF;
        ALTER TABLE docs_sync.documents
            ADD CONSTRAINT documents_pkey
            PRIMARY KEY (id, tenant_id, workspace_id, project_id);
    END IF;
END
$$;

-- Keep one current anchor per document-symbol pair inside a project scope.
WITH ranked AS (
    SELECT
        id,
        row_number() OVER (
            PARTITION BY tenant_id, workspace_id, project_id, doc_id, symbol_id
            ORDER BY updated_at DESC, id DESC
        ) AS duplicate_rank
    FROM docs_sync.anchors
)
DELETE FROM docs_sync.anchors AS anchor
USING ranked
WHERE anchor.id = ranked.id
  AND ranked.duplicate_rank > 1;

CREATE UNIQUE INDEX IF NOT EXISTS docs_sync_anchors_natural_key_idx
    ON docs_sync.anchors (
        tenant_id,
        workspace_id,
        project_id,
        doc_id,
        symbol_id
    );

"""Neo4j Cypher query strings for Code Graph CRUD."""

from __future__ import annotations

from .constants import REL

GET_SYMBOL = """
MATCH (n:CodeSymbol {id: $id})
WHERE n.tenant_id = $tenant_id
  AND n.workspace_id = $workspace_id
  AND n.project_id = $project_id
RETURN n
"""

PUT_SYMBOL = """
MERGE (n:CodeSymbol {id: $id})
SET n.tenant_id = $tenant_id,
    n.workspace_id = $workspace_id,
    n.project_id = $project_id,
    n.project_group_id = $project_group_id,
    n.kind = $kind,
    n.file_path = $file_path,
    n.name = $name,
    n.qualified_name = $qualified_name,
    n.signature = $signature,
    n.body = $body,
    n.hash_value = $hash_value,
    n.ai_documentation = $ai_documentation,
    n.doc_status = $doc_status,
    n.embedding = $embedding,
    n.visibility = $visibility,
    n.version = $version,
    n.created_at = $created_at,
    n.updated_at = $updated_at,
    n.language = $language,
    n.hash_version = $hash_version,
    n.parser_version = $parser_version,
    n.metadata_json = $metadata_json
"""

DELETE_SYMBOL = """
MATCH (n:CodeSymbol {id: $id})
WHERE n.tenant_id = $tenant_id
  AND n.workspace_id = $workspace_id
  AND n.project_id = $project_id
DETACH DELETE n
"""

DELETE_SYMBOLS = """
UNWIND $symbol_ids AS symbol_id
MATCH (n:CodeSymbol {id: symbol_id})
WHERE n.tenant_id = $tenant_id
  AND n.workspace_id = $workspace_id
  AND n.project_id = $project_id
DETACH DELETE n
"""

LIST_SYMBOLS = """
MATCH (n:CodeSymbol)
WHERE n.tenant_id = $tenant_id
  AND n.workspace_id = $workspace_id
  AND n.project_id = $project_id
  AND n.kind IS NOT NULL
  AND n.doc_status IS NOT NULL
WITH n
ORDER BY n.qualified_name, n.id
RETURN n {
  .id, .kind, .file_path, .name, .qualified_name, .signature,
  .body, .hash_value, .ai_documentation, .doc_status,
  .visibility, .version, .created_at, .updated_at, .language,
  .hash_version, .parser_version, .metadata_json,
  embedding: []
} AS n
"""

# Dead-code / reachability scans: omit bulky living-doc text (unused by scorers).
LIST_SYMBOLS_LEAN = """
MATCH (n:CodeSymbol)
WHERE n.tenant_id = $tenant_id
  AND n.workspace_id = $workspace_id
  AND n.project_id = $project_id
  AND n.kind IS NOT NULL
  AND n.doc_status IS NOT NULL
WITH n
ORDER BY n.qualified_name, n.id
RETURN n {
  .id, .kind, .file_path, .name, .qualified_name, .signature,
  .body, .hash_value, .doc_status,
  .visibility, .version, .created_at, .updated_at, .language,
  .hash_version, .parser_version, .metadata_json,
  ai_documentation: "",
  embedding: []
} AS n
"""

# Sync resolution / finalize indexes: no body, docs, or metadata blobs on the wire.
LIST_SYMBOLS_INDEX = """
MATCH (n:CodeSymbol)
WHERE n.tenant_id = $tenant_id
  AND n.workspace_id = $workspace_id
  AND n.project_id = $project_id
  AND n.kind IS NOT NULL
  AND n.doc_status IS NOT NULL
WITH n
ORDER BY n.qualified_name, n.id
RETURN n {
  .id, .kind, .file_path, .name, .qualified_name, .doc_status, .language,
  hash_value: coalesce(n.hash_value, ""),
  signature: "",
  body: "",
  ai_documentation: "",
  embedding: [],
  visibility: coalesce(n.visibility, ""),
  version: coalesce(n.version, 1),
  created_at: coalesce(n.created_at, ""),
  updated_at: coalesce(n.updated_at, ""),
  hash_version: "",
  parser_version: "",
  metadata_json: "{}"
} AS n
"""

# Client hash-skip: tiny rows only (no EXISTS correlated subquery).
LIST_CONTENT_HASH_ROWS = """
MATCH (n:CodeSymbol)
WHERE n.tenant_id = $tenant_id
  AND n.workspace_id = $workspace_id
  AND n.project_id = $project_id
  AND n.kind IN ['file', 'function', 'method', 'class', 'documentation']
RETURN n.kind AS kind,
       n.file_path AS path,
       coalesce(n.hash_value, '') AS hash,
       n.id AS id,
       coalesce(n.metadata_json, '{}') AS metadata_json
"""

LIST_SYMBOLS_FOR_FILE = """
MATCH (n:CodeSymbol)
WHERE n.tenant_id = $tenant_id
  AND n.workspace_id = $workspace_id
  AND n.project_id = $project_id
  AND n.file_path = $file_path
  AND n.kind IS NOT NULL
  AND n.doc_status IS NOT NULL
RETURN n
ORDER BY n.qualified_name, n.id
"""

GET_SYMBOL_BY_QUALIFIED_NAME = """
MATCH (n:CodeSymbol)
WHERE n.tenant_id = $tenant_id
  AND n.workspace_id = $workspace_id
  AND n.project_id = $project_id
  AND n.qualified_name = $qualified_name
RETURN n
LIMIT 1
"""

DELETE_FILE_EDGES = f"""
MATCH ()-[r:{REL}]->()
WHERE r.tenant_id = $tenant_id
  AND r.workspace_id = $workspace_id
  AND r.project_id = $project_id
  AND r.file_path = $file_path
DELETE r
"""

DELETE_EDGE = f"""
MATCH ()-[r:{REL} {{id: $id}}]->()
WHERE r.tenant_id = $tenant_id
  AND r.workspace_id = $workspace_id
  AND r.project_id = $project_id
DELETE r
"""

DELETE_EDGES = f"""
MATCH ()-[r:{REL}]->()
WHERE r.id IN $ids
  AND r.tenant_id = $tenant_id
  AND r.workspace_id = $workspace_id
  AND r.project_id = $project_id
DELETE r
"""

PUT_EDGE = f"""
MATCH (source:CodeSymbol {{id: $source_id}})
MATCH (target:CodeSymbol {{id: $target_id}})
MERGE (source)-[r:{REL} {{id: $id}}]->(target)
SET r.tenant_id = $tenant_id,
    r.workspace_id = $workspace_id,
    r.project_id = $project_id,
    r.project_group_id = $project_group_id,
    r.rel_type = $rel_type,
    r.confidence = coalesce($confidence, 'exact'),
    r.file_path = $file_path,
    r.metadata_json = $metadata_json
"""

PUT_EDGES = f"""
UNWIND $edges AS edge
MATCH (source:CodeSymbol {{id: edge.source_id}})
MATCH (target:CodeSymbol {{id: edge.target_id}})
MERGE (source)-[r:{REL} {{id: edge.id}}]->(target)
SET r.tenant_id = edge.tenant_id,
    r.workspace_id = edge.workspace_id,
    r.project_id = edge.project_id,
    r.project_group_id = edge.project_group_id,
    r.rel_type = edge.rel_type,
    r.confidence = coalesce(edge.confidence, 'exact'),
    r.file_path = edge.file_path,
    r.metadata_json = edge.metadata_json
"""

LIST_EDGES = f"""
MATCH (source:CodeSymbol)-[r:{REL}]->(target:CodeSymbol)
WHERE r.tenant_id = $tenant_id
  AND r.workspace_id = $workspace_id
  AND r.project_id = $project_id
  AND ($rel_type IS NULL OR r.rel_type = $rel_type)
  AND ($source_id IS NULL OR source.id = $source_id)
  AND ($target_id IS NULL OR target.id = $target_id)
  AND (
    $target_id_prefixes IS NULL
    OR size($target_id_prefixes) = 0
    OR any(p IN $target_id_prefixes WHERE target.id STARTS WITH p)
  )
RETURN r.id AS id,
       r.rel_type AS rel_type,
       coalesce(r.confidence, 'exact') AS confidence,
       r.metadata_json AS metadata_json,
       source.id AS source_id,
       target.id AS target_id
ORDER BY r.id
"""

BACKFILL_NULL_CONFIDENCE = f"""
MATCH ()-[r:{REL}]->()
WHERE r.confidence IS NULL
SET r.confidence = 'exact'
RETURN count(r) AS repaired
"""

# Required enums cannot be invented; detach-delete unusable orphans (Postgres NOT NULL equivalent).
PURGE_NULL_SYMBOL_ENUMS = """
MATCH (n:CodeSymbol)
WHERE n.kind IS NULL OR n.doc_status IS NULL
WITH collect(n) AS nodes
FOREACH (n IN nodes | DETACH DELETE n)
RETURN size(nodes) AS repaired
"""

BEGIN_IDEMPOTENCY = """
MATCH (n:CodeIdempotency {
    scope_key: $scope_key,
    idempotency_key: $idempotency_key,
    resource_type: $resource_type
})
RETURN n.resource_id AS resource_id
"""

COMPLETE_IDEMPOTENCY = """
MERGE (n:CodeIdempotency {
    scope_key: $scope_key,
    idempotency_key: $idempotency_key,
    resource_type: $resource_type
})
ON CREATE SET n.resource_id = $resource_id
RETURN n.resource_id AS resource_id
"""

APPEND_EVENT = """
CREATE (n:CodeOutboxEvent {
    event_id: $event_id,
    event_type: $event_type,
    payload_json: $payload_json,
    created_at: datetime()
})
"""

OUTBOX = """
MATCH (n:CodeOutboxEvent)
RETURN n.payload_json AS payload_json
ORDER BY n.created_at, n.event_id
"""

WIPE_SYMBOLS = """
MATCH (n:CodeSymbol)
WHERE n.tenant_id = $tenant_id
  AND n.workspace_id = $workspace_id
  AND n.project_id = $project_id
WITH collect(n) AS nodes
FOREACH (n IN nodes | DETACH DELETE n)
RETURN size(nodes) AS deleted
"""

WIPE_EDGES = f"""
MATCH ()-[r:{REL}]->()
WHERE r.tenant_id = $tenant_id
  AND r.workspace_id = $workspace_id
  AND r.project_id = $project_id
WITH collect(r) AS rels
FOREACH (r IN rels | DELETE r)
RETURN size(rels) AS deleted
"""

WIPE_IDEMPOTENCY = """
MATCH (n:CodeIdempotency {scope_key: $scope_key})
WITH collect(n) AS nodes
FOREACH (n IN nodes | DELETE n)
RETURN size(nodes) AS deleted
"""

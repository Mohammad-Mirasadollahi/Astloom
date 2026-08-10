# code-graph-service migrations

Apply `0001_code_graph.sql` to provision the `code_graph` PostgreSQL schema.

pgvector embeddings apply via `PostgresEmbeddingIndex.ensure_schema` (`0003`–`0005`, plus `0009_embedding_id_map.sql` for the TurboVec entity id map).

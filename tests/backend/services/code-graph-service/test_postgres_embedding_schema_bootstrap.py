"""PostgresEmbeddingIndex schema bootstrap (Neo4j-primary + pgvector side store)."""

from __future__ import annotations

from code_graph_service.postgres_side import PostgresEmbeddingIndex


def test_ensure_schema_creates_code_graph_schema_before_migrations(monkeypatch):
    executed: list[str] = []

    class _Cur:
        def execute(self, sql):
            executed.append(str(sql).strip().splitlines()[0])

        def fetchone(self):
            return {"typ": "vector(1024)"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class _Conn:
        def cursor(self):
            return _Cur()

    class _Pool:
        def get(self):
            return _Conn()

        def close_all(self):
            return None

    index = PostgresEmbeddingIndex.__new__(PostgresEmbeddingIndex)
    index._dims = 1024
    index._pool = _Pool()
    monkeypatch.setattr(
        "code_graph_service.postgres_side.pg_sql.EMBEDDING_MIGRATION_FILES",
        (),
    )
    index.ensure_schema()
    assert executed[0] == "CREATE SCHEMA IF NOT EXISTS code_graph"

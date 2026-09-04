"""Memory PostgresStore applies retention migrations (pinned / expires_at)."""

from __future__ import annotations

from pathlib import Path

from memory_service.postgres_store import MIGRATION_FILES, PostgresStore


def test_memory_item_migrations_include_retention():
    root = Path(__file__).resolve().parents[4] / "backend/services/memory-service/migrations"
    assert MIGRATION_FILES == (
        "0001_memory.sql",
        "0002_outbox_published.sql",
        "0005_memory_retention.sql",
    )
    sql = (root / "0005_memory_retention.sql").read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS pinned" in sql
    assert "expires_at" in sql


def test_ensure_schema_executes_retention_sql(monkeypatch):
    executed: list[str] = []

    class _Cur:
        def execute(self, sql):
            executed.append(str(sql))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class _Conn:
        def cursor(self):
            return _Cur()

    store = PostgresStore.__new__(PostgresStore)
    store._connection = _Conn()
    store.ensure_schema()
    assert any("ADD COLUMN IF NOT EXISTS pinned" in sql for sql in executed)
    assert any("CREATE SCHEMA IF NOT EXISTS memory" in sql for sql in executed)

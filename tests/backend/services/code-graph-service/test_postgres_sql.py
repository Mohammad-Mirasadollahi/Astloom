"""Unit tests for extracted Postgres SQL helpers."""

from __future__ import annotations

import pytest

from code_graph_service.postgres import sql as pg_sql


def test_create_symbol_embeddings_table_embeds_dims():
    ddl = pg_sql.create_symbol_embeddings_table(16)
    assert "vector(16)" in ddl
    assert "symbol_embeddings" in ddl
    assert pg_sql.expected_vector_type(16) == "vector(16)"


def test_create_symbol_embeddings_table_rejects_non_positive():
    with pytest.raises(ValueError):
        pg_sql.create_symbol_embeddings_table(0)


def test_core_dml_statements_are_non_empty():
    for name in (
        "UPSERT_EMBEDDING",
        "DELETE_EMBEDDING",
        "WIPE_EMBEDDINGS_SCOPE",
        "LIST_EMBEDDING_MODELS",
        "SEARCH_EMBEDDINGS",
        "APPEND_OUTBOX_EVENT",
        "SELECT_EMBEDDING_COLUMN_TYPE",
    ):
        text = getattr(pg_sql, name)
        assert isinstance(text, str) and text.strip()


def test_embedding_migration_files_include_id_map():
    assert "0009_embedding_id_map.sql" in pg_sql.EMBEDDING_MIGRATION_FILES
    from pathlib import Path

    migrations = Path(__file__).resolve().parents[4] / "backend/services/code-graph-service/migrations"
    sql = (migrations / "0009_embedding_id_map.sql").read_text(encoding="utf-8")
    assert "code_graph.embedding_id_map" in sql
    assert "uint64_id" in sql

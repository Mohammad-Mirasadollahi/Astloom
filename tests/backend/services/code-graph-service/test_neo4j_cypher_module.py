"""Neo4j CRUD Cypher strings live in a dedicated module."""

from __future__ import annotations

from code_graph_service.neo4j import cypher
from code_graph_service.neo4j.constants import REL


def test_cypher_module_exports_crud_queries():
    names = (
        "GET_SYMBOL",
        "PUT_SYMBOL",
        "DELETE_SYMBOL",
        "LIST_SYMBOLS",
        "LIST_SYMBOLS_FOR_FILE",
        "GET_SYMBOL_BY_QUALIFIED_NAME",
        "DELETE_FILE_EDGES",
        "DELETE_EDGE",
        "PUT_EDGE",
        "LIST_EDGES",
        "BEGIN_IDEMPOTENCY",
        "COMPLETE_IDEMPOTENCY",
        "APPEND_EVENT",
        "OUTBOX",
        "WIPE_SYMBOLS",
        "WIPE_EDGES",
        "WIPE_IDEMPOTENCY",
    )
    for name in names:
        value = getattr(cypher, name)
        assert isinstance(value, str)
        assert value.strip()


def test_edge_queries_use_shared_rel_constant():
    assert REL in cypher.PUT_EDGE
    assert REL in cypher.LIST_EDGES
    assert REL in cypher.DELETE_EDGE
    assert REL in cypher.DELETE_FILE_EDGES
    assert REL in cypher.WIPE_EDGES


def test_list_edges_coalesces_null_confidence():
    assert "coalesce(r.confidence, 'exact')" in cypher.LIST_EDGES
    assert "coalesce($confidence, 'exact')" in cypher.PUT_EDGE
    assert "BACKFILL_NULL_CONFIDENCE" in dir(cypher)
    assert REL in cypher.BACKFILL_NULL_CONFIDENCE


def test_purge_null_symbol_enums_and_list_filters():
    assert "PURGE_NULL_SYMBOL_ENUMS" in dir(cypher)
    assert "n.kind IS NULL OR n.doc_status IS NULL" in cypher.PURGE_NULL_SYMBOL_ENUMS
    assert "DETACH DELETE" in cypher.PURGE_NULL_SYMBOL_ENUMS
    assert "n.kind IS NOT NULL" in cypher.LIST_SYMBOLS
    assert "n.doc_status IS NOT NULL" in cypher.LIST_SYMBOLS
    assert "n.kind IS NOT NULL" in cypher.LIST_SYMBOLS_FOR_FILE
    assert "n.doc_status IS NOT NULL" in cypher.LIST_SYMBOLS_FOR_FILE


def test_list_edges_supports_optional_filters():
    assert "$rel_type IS NULL OR r.rel_type = $rel_type" in cypher.LIST_EDGES
    assert "$target_id IS NULL OR target.id = $target_id" in cypher.LIST_EDGES

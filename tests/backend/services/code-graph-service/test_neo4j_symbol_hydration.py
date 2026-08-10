"""Neo4j symbol hydration rejects/skips corrupt kind and doc_status."""

from __future__ import annotations

import pytest

from code_graph_service.core import Scope, ValidationError
from code_graph_service.neo4j.crud import Neo4jCrudMixin


SCOPE = Scope("t", "w", "p")


def _good_node(**overrides):
    node = {
        "id": "sym:good",
        "kind": "function",
        "file_path": "src/a.py",
        "name": "f",
        "qualified_name": "src.a.f",
        "signature": "f()",
        "body": "",
        "hash_value": "h",
        "ai_documentation": "",
        "doc_status": "unchanged",
        "embedding": [],
        "visibility": "public",
        "version": 1,
        "created_at": "t0",
        "updated_at": "t0",
    }
    node.update(overrides)
    return node


def test_symbol_from_node_rejects_null_kind():
    with pytest.raises(ValidationError, match="null/blank kind"):
        Neo4jCrudMixin._symbol_from_node(Neo4jCrudMixin(), _good_node(kind=None), SCOPE)


def test_symbol_from_node_rejects_invalid_kind():
    with pytest.raises(ValidationError, match="invalid kind"):
        Neo4jCrudMixin._symbol_from_node(Neo4jCrudMixin(), _good_node(kind="not-a-kind"), SCOPE)


def test_symbol_from_node_rejects_null_doc_status():
    with pytest.raises(ValidationError, match="null/blank doc_status"):
        Neo4jCrudMixin._symbol_from_node(Neo4jCrudMixin(), _good_node(doc_status=None), SCOPE)


def test_symbol_from_node_defaults_legacy_null_version():
    symbol = Neo4jCrudMixin._symbol_from_node(
        Neo4jCrudMixin(),
        _good_node(version=None),
        SCOPE,
    )

    assert symbol.version == 1


def test_symbols_from_rows_skips_corrupt_keeps_good():
    mixin = Neo4jCrudMixin()
    rows = [
        {"n": _good_node(id="sym:bad", kind=None)},
        {"n": _good_node(id="sym:ok")},
        {"n": _good_node(id="sym:bad2", doc_status=None)},
    ]
    out = mixin._symbols_from_rows(rows, SCOPE)
    assert [s.id for s in out] == ["sym:ok"]
    assert out[0].kind.value == "function"

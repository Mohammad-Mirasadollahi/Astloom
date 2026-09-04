"""Neo4j schema must index CODE_REL.id for bulk edge delete/MERGE."""

from __future__ import annotations

from code_graph_service.neo4j import cypher
from code_graph_service.neo4j.schema import Neo4jSchemaMixin


class _CaptureSession:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def run(self, statement: str, *args, **kwargs):  # noqa: ANN001, ANN003
        self.statements.append(statement)
        return None

    def __enter__(self) -> _CaptureSession:
        return self

    def __exit__(self, *args) -> None:  # noqa: ANN002
        return None


class _SchemaProbe(Neo4jSchemaMixin):
    def __init__(self) -> None:
        self._driver = type("D", (), {})()
        self._database = "neo4j"
        self._capabilities_cache = None
        self._gds_enabled = False
        self._gds_concurrency = 1
        self._session = _CaptureSession()
        self._driver.session = lambda database=None: self._session  # type: ignore[method-assign]


def test_ensure_schema_creates_code_rel_id_index():
    probe = _SchemaProbe()
    probe.ensure_schema()
    joined = "\n".join(probe._session.statements)
    assert "code_rel_id" in joined
    assert "FOR ()-[r:CODE_REL]-() ON (r.id)" in joined
    assert "code_rel_scope_type" in joined


def test_delete_edges_uses_id_in_list():
    assert "r.id IN $ids" in cypher.DELETE_EDGES
    assert "UNWIND $ids" not in cypher.DELETE_EDGES

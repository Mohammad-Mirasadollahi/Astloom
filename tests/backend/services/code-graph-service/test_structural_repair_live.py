"""Live Neo4j gate: hash-stable edgeless FILE rows must re-ingest after service restart.

Re-run:
  astloom service restart
  ASTLOOM_NEO4J_PASSWORD=astloom-local-dev-secret \\
    .venv/bin/python -m pytest \\
    tests/backend/services/code-graph-service/test_structural_repair_live.py -m live -v
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.domain.embeddings import LocalEmbeddingStub
from code_graph_service.domain.enums import RelType
from code_graph_service.domain.structural_integrity import file_needs_contains_repair
from code_graph_service.llm_wiring import HybridEmbeddings
from code_graph_service.neo4j_store import Neo4jStore

from live_helpers import NEO4J_BOLT_PORT, NEO4J_PASSWORD, NEO4J_USER, require_tcp, skip_on_live_connect_error

pytestmark = pytest.mark.live

SRC = """\
def helper():
    return 1

def main():
    return helper()
"""


def _unique_scope() -> Scope:
    return Scope("tenant-live", "ws-live", f"struct-repair-{uuid.uuid4().hex[:10]}")


def _neo4j_store() -> Neo4jStore:
    try:
        return Neo4jStore(
            uri=f"bolt://127.0.0.1:{NEO4J_BOLT_PORT}",
            user=NEO4J_USER,
            password=NEO4J_PASSWORD,
            ensure_schema=True,
            gds_enabled=True,
            gds_concurrency=4,
        )
    except Exception as exc:  # noqa: BLE001
        skip_on_live_connect_error(exc)
        raise  # pragma: no cover


def _service(store: Neo4jStore) -> CodeGraphService:
    return CodeGraphService(
        store,
        embeddings=HybridEmbeddings(stub=LocalEmbeddingStub(dims=1024), dims=1024, local=None),
    )


@pytest.fixture
def live_store():
    require_tcp("127.0.0.1", NEO4J_BOLT_PORT)
    assert NEO4J_BOLT_PORT not in {7474, 7687}
    store = _neo4j_store()
    yield store
    try:
        store.close()
    except Exception:  # noqa: BLE001
        pass


def test_live_hash_stable_edgeless_file_repairs_on_reingest(live_store):
    """Wipe CONTAINS on Neo4j, re-ingest same bytes → edges restored (post-restart code)."""
    scope = _unique_scope()
    svc = _service(live_store)
    try:
        svc.ingest_file(
            scope,
            "live",
            "c1",
            "k1",
            {"file_path": "src/mod.py", "source": SRC, "language": "python"},
        )
        file_id = f"file:{scope.project_id}:src/mod.py"
        assert live_store.list_edges(scope, rel_type=RelType.CONTAINS.value, source_id=file_id)

        for edge in list(live_store.list_edges(scope, rel_type=RelType.CONTAINS.value)):
            live_store.delete_edge(scope, edge.id)
        for edge in list(live_store.list_edges(scope, rel_type=RelType.CALLS.value)):
            live_store.delete_edge(scope, edge.id)

        assert file_needs_contains_repair(
            live_store, scope, file_id=file_id, file_path="src/mod.py"
        )
        assert not live_store.list_edges(
            scope, rel_type=RelType.CONTAINS.value, source_id=file_id
        )

        result = svc.ingest_file(
            scope,
            "live",
            "c2",
            "k2",
            {"file_path": "src/mod.py", "source": SRC, "language": "python"},
        )
        assert result.edges_written > 0
        assert live_store.list_edges(scope, rel_type=RelType.CONTAINS.value, source_id=file_id)

        helper = next(s for s in live_store.list_symbols(scope) if s.name == "helper")
        callers = live_store.list_edges(
            scope, rel_type=RelType.CALLS.value, target_id=helper.id
        )
        assert callers, "same-file CALLS to helper must return after repair"
    finally:
        live_store.wipe_scope(scope)


def test_live_sync_repo_repairs_edgeless_hash_stable_tree(live_store, tmp_path: Path):
    """sync_repo must enqueue hash-stable files that lost CONTAINS."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text(SRC, encoding="utf-8")
    scope = _unique_scope()
    svc = _service(live_store)
    try:
        first = svc.sync_repo(
            scope,
            "live",
            "corr-1",
            "key-1",
            {"root_path": str(tmp_path), "include_outcomes": True},
        )
        assert first.files_ingested >= 1
        file_id = f"file:{scope.project_id}:src/a.py"
        assert live_store.list_edges(scope, rel_type=RelType.CONTAINS.value, source_id=file_id)

        for edge in list(live_store.list_edges(scope, rel_type=RelType.CONTAINS.value)):
            live_store.delete_edge(scope, edge.id)

        again = svc.sync_repo(
            scope,
            "live",
            "corr-2",
            "key-2",
            {"root_path": str(tmp_path), "include_outcomes": True},
        )
        assert again.mode != "noop"
        assert again.files_ingested >= 1
        assert live_store.list_edges(scope, rel_type=RelType.CONTAINS.value, source_id=file_id)
    finally:
        live_store.wipe_scope(scope)


def test_live_architecture_knowledge_gaps_use_structural_isolation(live_store):
    """After restart, knowledge_gaps must use structural degree==0 (not CONTAINS-only noise)."""
    scope = _unique_scope()
    svc = _service(live_store)
    src = """\
def orphan():
    return 0

def leaf():
    return hub()

def hub():
    return leaf()
"""
    try:
        svc.ingest_file(
            scope,
            "live",
            "c1",
            "k1",
            {"file_path": "src/graph.py", "source": src, "language": "python"},
        )
        overview = svc.architecture_overview(scope, top_n=10)
        gaps = overview["knowledge_gaps"]
        isolated = {row["qualified_name"]: row for row in gaps["isolated_nodes"]}
        # orphan has CONTAINS only → structural degree 0 → listed
        orphan_hits = [qn for qn in isolated if qn.endswith(".orphan")]
        assert orphan_hits, f"expected orphan in isolated, got {list(isolated)[:10]}"
        assert isolated[orphan_hits[0]]["degree"] == 0
        # leaf/hub call each other → not isolated
        assert not any(qn.endswith(".leaf") for qn in isolated)
        assert not any(qn.endswith(".hub") for qn in isolated)
        for row in gaps["untested_hotspots"]:
            qn = row.get("qualified_name") or ""
            assert not qn.endswith(".__init__")
            assert not (row.get("file_path") or "").endswith("/testing.py")
    finally:
        live_store.wipe_scope(scope)

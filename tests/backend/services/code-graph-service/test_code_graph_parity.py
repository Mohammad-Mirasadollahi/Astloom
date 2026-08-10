"""Unit and live tests for Postgres ↔ Neo4j structural parity."""

from __future__ import annotations

import os
import uuid

import pytest

from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.domain.parity import compare_stores, ingest_both_and_compare
from code_graph_service.neo4j_store import Neo4jStore
from code_graph_service.postgres_store import PostgresStore
from code_graph_service.testing import InMemoryStore

PYTHON_SOURCE = """\
def check_password(password):
    return len(password) > 8

def login(user, password):
    return check_password(password)
"""

POSTGRES_PORT = int(os.environ.get("ASTLOOM_POSTGRES_PORT", "32232"))
NEO4J_BOLT_PORT = int(os.environ.get("ASTLOOM_NEO4J_BOLT_PORT", "32287"))
POSTGRES_PASSWORD = os.environ.get("ASTLOOM_POSTGRES_PASSWORD", "astloom-local-dev-secret")
NEO4J_PASSWORD = os.environ.get("ASTLOOM_NEO4J_PASSWORD", "astloom-local-dev-secret")
NEO4J_USER = os.environ.get("ASTLOOM_NEO4J_USER", "neo4j")


def test_inmemory_parity_after_identical_ingest():
    left = InMemoryStore()
    right = InMemoryStore()
    scope = Scope("t", "w", "parity-mem")
    report = ingest_both_and_compare(
        CodeGraphService(left),
        CodeGraphService(right),
        scope,
        agent_id="agent",
        correlation_id="corr",
        idempotency_key="parity-mem",
        payload={"file_path": "src/auth.py", "source": PYTHON_SOURCE, "language": "python"},
    )
    assert report.equal, report.to_dict()
    assert report.left_symbol_count >= 3
    assert report.left_edge_count >= 1


def test_compare_stores_detects_missing_symbol():
    left = InMemoryStore()
    right = InMemoryStore()
    scope = Scope("t", "w", "parity-diff")
    CodeGraphService(left).ingest_file(
        scope,
        "agent",
        "c",
        "only-left",
        {"file_path": "src/auth.py", "source": PYTHON_SOURCE, "language": "python"},
    )
    report = compare_stores(left, right, scope)
    assert not report.equal
    assert report.missing_symbol_ids_on_right


def _require_tcp(host: str, port: int) -> None:
    import socket

    sock = socket.socket()
    sock.settimeout(2)
    try:
        sock.connect((host, port))
    except OSError as exc:
        pytest.skip(f"service not reachable at {host}:{port}: {exc}")
    finally:
        sock.close()


def test_postgres_neo4j_parity_live():
    _require_tcp("127.0.0.1", POSTGRES_PORT)
    _require_tcp("127.0.0.1", NEO4J_BOLT_PORT)
    project_id = f"parity-{uuid.uuid4().hex[:8]}"
    scope = Scope("tenant-parity", "ws-parity", project_id)
    pg = PostgresStore(
        f"postgresql://astloom:{POSTGRES_PASSWORD}@127.0.0.1:{POSTGRES_PORT}/astloom"
    )
    nj = Neo4jStore(
        uri=f"bolt://127.0.0.1:{NEO4J_BOLT_PORT}",
        user=NEO4J_USER,
        password=NEO4J_PASSWORD,
        ensure_schema=True,
    )
    try:
        report = ingest_both_and_compare(
            CodeGraphService(pg),
            CodeGraphService(nj),
            scope,
            agent_id="agent",
            correlation_id="corr-parity",
            idempotency_key=f"parity-{project_id}",
            payload={"file_path": "src/auth.py", "source": PYTHON_SOURCE, "language": "python"},
        )
        assert report.equal, report.to_dict()
        login_id = f"sym:{project_id}:src.auth.login"
        left_n = CodeGraphService(pg).structural_query(scope, login_id, "CALLS")
        right_n = CodeGraphService(nj).structural_query(scope, login_id, "CALLS")
        left_targets = {(e["source_id"], e["target_id"], e["rel_type"]) for e in left_n["edges"]}
        right_targets = {(e["source_id"], e["target_id"], e["rel_type"]) for e in right_n["edges"]}
        assert left_targets == right_targets
        assert any(e["rel_type"] == "CALLS" for e in left_n["edges"])
    finally:
        pg.close()
        nj.close()

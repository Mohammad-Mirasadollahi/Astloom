from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from starlette.requests import Request

from code_graph_service.api import _is_loopback_request, app
from code_graph_service.bootstrap import Settings, build_store
from code_graph_service.core import (
    CallConfidence,
    CodeGraphService,
    DocStatus,
    GraphEdge,
    GraphSymbol,
    LocalEmbeddingStub,
    NotFoundError,
    Scope,
    SymbolKind,
    ValidationError,
    assert_language_supported,
    assert_required_languages_supported,
    digest,
    language_matrix,
    normalize_source,
    required_languages,
    resolve_call_target,
    supported_languages,
)
from code_graph_service.neo4j_store import Neo4jStore
from code_graph_service.testing import InMemoryStore


SCOPE = Scope("t", "w", "p")

AUTH_SOURCE_V1 = '''\
def check_password(password):
    return len(password) > 8

def login(user, password):
    return check_password(password)
'''

AUTH_SOURCE_V2 = '''\
def check_password(password):
    return len(password) > 8

def login(user, password):
    return check_password(password) and user is not None
'''

HELPER_SOURCE = '''\
def helper(value):
    return value
'''

CONSUMER_SOURCE = '''\
from src.helpers import helper as help_fn

def run(value):
    return help_fn(value)
'''


class _FakeNode(dict):
    """Dict-backed stand-in for a Neo4j node map."""

    pass


@dataclass
class _FakeRecord:
    data: dict[str, Any]

    def __getitem__(self, key: str) -> Any:
        return self.data[key]


@dataclass
class _FakeResult:
    rows: list[_FakeRecord]

    def single(self) -> _FakeRecord | None:
        return self.rows[0] if self.rows else None

    def __iter__(self):
        return iter(self.rows)


@dataclass
class _FakeSession:
    store: "_FakeNeo4jDriver"

    def __enter__(self) -> "_FakeSession":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def run(self, query: str, **params: Any) -> _FakeResult:
        q = " ".join(query.split())
        if q.startswith("CREATE CONSTRAINT") or q.startswith("CREATE INDEX") or q.startswith("CREATE FULLTEXT"):
            return _FakeResult([])
        if "apoc.version()" in q:
            return _FakeResult([_FakeRecord({"version": "fake-apoc"})])
        if "gds.version()" in q:
            return _FakeResult([_FakeRecord({"version": "fake-gds"})])
        if "SHOW FULLTEXT INDEXES" in q:
            return _FakeResult([_FakeRecord({"c": 1})])
        if "MERGE (n:CodeSymbol {id: $id})" in q:
            node = {
                "id": params["id"],
                "tenant_id": params["tenant_id"],
                "workspace_id": params["workspace_id"],
                "project_id": params["project_id"],
                "project_group_id": params.get("project_group_id"),
                "kind": params["kind"],
                "file_path": params["file_path"],
                "name": params["name"],
                "qualified_name": params["qualified_name"],
                "signature": params["signature"],
                "body": params["body"],
                "hash_value": params["hash_value"],
                "ai_documentation": params["ai_documentation"],
                "doc_status": params["doc_status"],
                "embedding": list(params.get("embedding") or []),
                "visibility": params["visibility"],
                "version": params["version"],
                "created_at": params["created_at"],
                "updated_at": params["updated_at"],
            }
            self.store.symbols[params["id"]] = node
            return _FakeResult([])
        if "MATCH (n:CodeSymbol {id: $id})" in q:
            node = self.store.symbols.get(params["id"])
            if node is None:
                return _FakeResult([])
            if (
                node["tenant_id"] != params["tenant_id"]
                or node["workspace_id"] != params["workspace_id"]
                or node["project_id"] != params["project_id"]
            ):
                return _FakeResult([])
            return _FakeResult([_FakeRecord({"n": _FakeNode(node)})])
        if "AND n.qualified_name = $qualified_name" in q:
            for node in self.store.symbols.values():
                if (
                    node["tenant_id"] == params["tenant_id"]
                    and node["workspace_id"] == params["workspace_id"]
                    and node["project_id"] == params["project_id"]
                    and node["qualified_name"] == params["qualified_name"]
                ):
                    return _FakeResult([_FakeRecord({"n": _FakeNode(node)})])
            return _FakeResult([])
        if "MATCH (n:CodeSymbol)" in q and "ORDER BY n.qualified_name" in q:
            rows = [
                _FakeRecord({"n": _FakeNode(node)})
                for node in sorted(
                    self.store.symbols.values(),
                    key=lambda item: (item["qualified_name"], item["id"]),
                )
                if node["tenant_id"] == params["tenant_id"]
                and node["workspace_id"] == params["workspace_id"]
                and node["project_id"] == params["project_id"]
                and node.get("kind") is not None
                and node.get("doc_status") is not None
            ]
            if "n.file_path = $file_path" in q:
                rows = [
                    row
                    for row in rows
                    if row.data["n"].get("file_path") == params["file_path"]
                ]
            return _FakeResult(rows)
        if "DELETE r" in q and "r.file_path = $file_path" in q:
            drop = [
                edge_id
                for edge_id, edge in self.store.edges.items()
                if edge["tenant_id"] == params["tenant_id"]
                and edge["workspace_id"] == params["workspace_id"]
                and edge["project_id"] == params["project_id"]
                and edge["file_path"] == params["file_path"]
            ]
            for edge_id in drop:
                del self.store.edges[edge_id]
            return _FakeResult([])
        if "DELETE r" in q and "id: $id" in q.replace(" ", ""):
            self.store.edges.pop(params["id"], None)
            return _FakeResult([])
        if "DELETE r" in q and "{id: $id}" in q:
            self.store.edges.pop(params["id"], None)
            return _FakeResult([])
        if q.startswith("UNWIND $symbol_ids AS symbol_id"):
            for symbol_id in params["symbol_ids"]:
                self.store.symbols.pop(symbol_id, None)
                self.store.edges = {
                    edge_id: edge
                    for edge_id, edge in self.store.edges.items()
                    if edge["source_id"] != symbol_id
                    and edge["target_id"] != symbol_id
                }
            return _FakeResult([])
        if q.startswith("UNWIND $edges AS edge"):
            for edge in params["edges"]:
                self.store.edges[edge["id"]] = dict(edge)
            return _FakeResult([])
        if "MERGE (source)-[r:CODE_REL {id: $id}]->(target)" in q or "MERGE (source)-[r:CODE_REL" in q:
            conf = params.get("confidence")
            self.store.edges[params["id"]] = {
                "id": params["id"],
                "source_id": params["source_id"],
                "target_id": params["target_id"],
                "tenant_id": params["tenant_id"],
                "workspace_id": params["workspace_id"],
                "project_id": params["project_id"],
                "project_group_id": params.get("project_group_id"),
                "rel_type": params["rel_type"],
                "confidence": conf if conf is not None else "exact",
                "file_path": params["file_path"],
                "metadata_json": params["metadata_json"],
            }
            return _FakeResult([])
        if "MATCH (source:CodeSymbol)-[r:CODE_REL]->(target:CodeSymbol)" in q:
            rows = [
                _FakeRecord(
                    {
                        "id": edge["id"],
                        "rel_type": edge["rel_type"],
                        "confidence": edge["confidence"] if edge["confidence"] is not None else "exact",
                        "metadata_json": edge["metadata_json"],
                        "source_id": edge["source_id"],
                        "target_id": edge["target_id"],
                    }
                )
                for edge in sorted(self.store.edges.values(), key=lambda item: item["id"])
                if edge["tenant_id"] == params["tenant_id"]
                and edge["workspace_id"] == params["workspace_id"]
                and edge["project_id"] == params["project_id"]
                and (params.get("rel_type") is None or edge["rel_type"] == params.get("rel_type"))
                and (params.get("source_id") is None or edge["source_id"] == params.get("source_id"))
                and (params.get("target_id") is None or edge["target_id"] == params.get("target_id"))
            ]
            return _FakeResult(rows)
        if "MATCH (n:CodeIdempotency" in q and "RETURN n.resource_id" in q and "MERGE" not in q:
            key = (params["scope_key"], params["idempotency_key"], params["resource_type"])
            if key not in self.store.idempotency:
                return _FakeResult([])
            return _FakeResult([_FakeRecord({"resource_id": self.store.idempotency[key]})])
        if "MERGE (n:CodeIdempotency" in q:
            key = (params["scope_key"], params["idempotency_key"], params["resource_type"])
            if key not in self.store.idempotency:
                self.store.idempotency[key] = params["resource_id"]
            return _FakeResult([_FakeRecord({"resource_id": self.store.idempotency[key]})])
        if "CREATE (n:CodeOutboxEvent" in q:
            self.store.outbox.append(
                {
                    "event_id": params["event_id"],
                    "event_type": params["event_type"],
                    "payload_json": params["payload_json"],
                }
            )
            return _FakeResult([])
        if "MATCH (n:CodeOutboxEvent)" in q:
            return _FakeResult(
                [_FakeRecord({"payload_json": item["payload_json"]}) for item in self.store.outbox]
            )
        if "r.confidence IS NULL" in q and "SET r.confidence" in q:
            repaired = 0
            for edge in self.store.edges.values():
                if edge.get("confidence") is None:
                    edge["confidence"] = "exact"
                    repaired += 1
            return _FakeResult([_FakeRecord({"repaired": repaired})])
        if "n.kind IS NULL OR n.doc_status IS NULL" in q and "DETACH DELETE" in q:
            drop = [
                sid
                for sid, node in self.store.symbols.items()
                if node.get("kind") is None or node.get("doc_status") is None
            ]
            for sid in drop:
                del self.store.symbols[sid]
            return _FakeResult([_FakeRecord({"repaired": len(drop)})])
        raise AssertionError(f"unexpected cypher in fake neo4j driver: {q}")


@dataclass
class _FakeNeo4jDriver:
    symbols: dict[str, dict[str, Any]] = field(default_factory=dict)
    edges: dict[str, dict[str, Any]] = field(default_factory=dict)
    idempotency: dict[tuple[str, str, str], str] = field(default_factory=dict)
    outbox: list[dict[str, Any]] = field(default_factory=list)

    def session(self, database: str = "neo4j") -> _FakeSession:
        return _FakeSession(self)

    def close(self) -> None:
        return None


def test_hash_change_documents_only_changed_symbols():
    store = InMemoryStore()
    service = CodeGraphService(store)

    first = service.ingest_file(
        SCOPE,
        "agent",
        "corr-1",
        "ingest-1",
        {"file_path": "src/auth.py", "source": AUTH_SOURCE_V1, "language": "python"},
    )
    assert first.symbols_indexed >= 3
    assert first.symbols_changed >= 2
    assert first.symbols_documented == first.symbols_changed
    assert store.outbox()[0]["event_type"] == "FileIngested"

    login_id = f"sym:{SCOPE.project_id}:src.auth.login"
    login_before = service.get_symbol(SCOPE, login_id)
    check_id = f"sym:{SCOPE.project_id}:src.auth.check_password"
    check_before = service.get_symbol(SCOPE, check_id)

    second = service.ingest_file(
        SCOPE,
        "agent",
        "corr-2",
        "ingest-2",
        {"file_path": "src/auth.py", "source": AUTH_SOURCE_V2, "language": "python"},
    )
    assert login_id in second.changed_symbol_ids
    assert check_id not in second.changed_symbol_ids
    assert second.symbols_documented == len(second.changed_symbol_ids)

    login_after = service.get_symbol(SCOPE, login_id)
    check_after = service.get_symbol(SCOPE, check_id)
    assert login_after.hash_value != login_before.hash_value
    assert check_after.hash_value == check_before.hash_value
    assert login_after.doc_status.value == "generated"
    assert "login" in login_after.ai_documentation

    documented = service.structural_query(SCOPE, check_id, "DOCUMENTED_BY")
    assert any(edge["rel_type"] == "DOCUMENTED_BY" for edge in documented["edges"])


def test_structural_and_semantic_queries():
    store = InMemoryStore()
    service = CodeGraphService(store)
    service.ingest_file(
        SCOPE,
        "agent",
        "corr",
        "ingest-struct",
        {"file_path": "src/auth.py", "source": AUTH_SOURCE_V1, "language": "python"},
    )
    login_id = f"sym:{SCOPE.project_id}:src.auth.login"
    neighbors = service.structural_query(SCOPE, login_id, "CALLS")
    assert neighbors["symbol"]["qualified_name"] == "src.auth.login"
    assert any(edge["rel_type"] == "CALLS" for edge in neighbors["edges"])
    assert any(edge["confidence"] == "exact" for edge in neighbors["edges"])

    hits = service.semantic_search(SCOPE, "login password authentication", top_k=3)
    assert hits
    assert any("login" in hit["symbol"]["qualified_name"] for hit in hits)


def test_generation_context_avoids_full_repo_and_validates_refs():
    store = InMemoryStore()
    service = CodeGraphService(store)
    service.ingest_file(
        SCOPE,
        "agent",
        "corr",
        "ingest-ctx",
        {"file_path": "src/auth.py", "source": AUTH_SOURCE_V1, "language": "python"},
    )
    login_id = f"sym:{SCOPE.project_id}:src.auth.login"
    context = service.build_generation_context(SCOPE, login_id)
    assert context["uses_full_repository"] is False
    assert "graph context" in context["prompt_context"].lower()
    assert context["symbol_count"] >= 1
    escalation = context["source_read_escalation"]
    assert escalation["profile_id"] == "default"
    assert "escalate_to_source" in escalation
    assert escalation["freshness_status"] in {"CURRENT", "STALE"}

    ok = service.validate_generated_code(
        SCOPE,
        "def wrap(user, password):\n    return login(user, password)\n",
    )
    assert ok["accepted"] is True
    assert "login" in ok["checked_call_refs"]

    bad = service.validate_generated_code(
        SCOPE,
        "def wrap(user):\n    return totally_unknown_helper(user)\n",
    )
    assert bad["accepted"] is False
    assert "totally_unknown_helper" in bad["unknown_symbols"]


def test_normalization_and_api_routes():
    left = normalize_source("def login():\n    return True  # note\n")
    right = normalize_source("def login():\n\n    return    True\n")
    assert left == right
    assert digest(left) == digest(right)

    routes = {route.path for route in app(CodeGraphService(InMemoryStore())).routes}
    assert "/api/v1/projects/{project_id}/graph/ingest-file" in routes
    assert "/api/v1/projects/{project_id}/graph/search:semantic" in routes
    assert "/api/v1/projects/{project_id}/graph/generation-context" in routes
    assert "/api/v1/projects/{project_id}/graph/generated-code:validate" in routes
    assert "/api/v1/projects/{project_id}/graph/symbols/{symbol_id}/neighbors" in routes
    assert "/api/v1/projects/{project_id}/graph/symbols/{symbol_id}/callers" in routes
    assert "/api/v1/projects/{project_id}/graph/symbols/{symbol_id}/impact" in routes
    assert "/api/v1/projects/{project_id}/graph/symbols/{symbol_id}/community" in routes
    assert "/api/v1/projects/{project_id}/graph/symbols/{symbol_id}/call-path" in routes
    assert "/api/v1/llm/providers" in routes
    assert "/api/v1/llm/config" in routes
    assert "/api/v1/llm/complete" in routes


def test_llm_sessions_route_is_loopback_only():
    assert _is_loopback_request(Request({"type": "http", "client": ("127.0.0.1", 50000)}))
    assert _is_loopback_request(Request({"type": "http", "client": ("::1", 50000)}))
    assert not _is_loopback_request(Request({"type": "http", "client": ("192.0.2.1", 50000)}))
    assert not _is_loopback_request(Request({"type": "http", "client": ("localhost", 50000)}))


def test_language_matrix_python_required_and_multi_lang_supported():
    matrix = language_matrix()
    assert matrix["python"]["status"] == "supported"
    assert matrix["python"]["required"] is True
    assert matrix["python"]["parser"] == "stdlib_ast"
    for language in ("typescript", "javascript", "go", "rust", "java"):
        assert matrix[language]["status"] == "supported"
        assert matrix[language]["parser"] == "tree_sitter"
        assert matrix[language]["required"] is False
    assert "python" in supported_languages()
    assert set(supported_languages()) >= {"python", "typescript", "javascript", "go", "rust", "java"}
    assert "python" in required_languages()
    assert_required_languages_supported()
    assert assert_language_supported("Python") == "python"
    assert assert_language_supported("rust") == "rust"
    assert assert_language_supported("java") == "java"
    try:
        assert_language_supported("cobol")
        raise AssertionError("unknown language should raise")
    except ValidationError as exc:
        assert "unsupported language" in exc.message
    assert matrix["java"]["extensions"] == (".java",)

def test_import_alias_probable_calls_and_file_imports():
    store = InMemoryStore()
    service = CodeGraphService(store)
    service.ingest_file(
        SCOPE,
        "agent",
        "corr-h",
        "ingest-helper",
        {"file_path": "src/helpers.py", "source": HELPER_SOURCE, "language": "python"},
    )
    service.ingest_file(
        SCOPE,
        "agent",
        "corr-c",
        "ingest-consumer",
        {"file_path": "src/consumer.py", "source": CONSUMER_SOURCE, "language": "python"},
    )
    run_id = f"sym:{SCOPE.project_id}:src.consumer.run"
    neighbors = service.structural_query(SCOPE, run_id, "CALLS")
    helper_id = f"sym:{SCOPE.project_id}:src.helpers.helper"
    assert any(
        edge["target_id"] == helper_id and edge["confidence"] in {"probable", "exact"}
        for edge in neighbors["edges"]
    )

    file_id = f"file:{SCOPE.project_id}:src/consumer.py"
    imports = service.structural_query(SCOPE, file_id, "IMPORTS")
    assert any(edge["rel_type"] == "IMPORTS" for edge in imports["edges"])


def test_embedding_stub_ready_and_resolve_ambiguous():
    stub = LocalEmbeddingStub(dims=8)
    ready = stub.embed("login password")
    assert ready.status == "ready"
    assert ready.dims == 8
    assert len(ready.vector) == 8
    assert stub.embed("").status == "empty"

    by_qualified = {"mod.a": "id-a", "mod.b": "id-b", "other.a": "id-other"}
    short_names = {"a": ["id-a", "id-other"], "b": ["id-b"]}
    targets, confidence = resolve_call_target(
        "a",
        by_qualified=by_qualified,
        short_names=short_names,
        import_aliases={},
        module_prefix="mod",
    )
    assert confidence == CallConfidence.EXACT
    assert targets == ["id-a"]

    targets, confidence = resolve_call_target(
        "a",
        by_qualified=by_qualified,
        short_names=short_names,
        import_aliases={},
        module_prefix="unrelated",
    )
    assert confidence == CallConfidence.AMBIGUOUS
    assert set(targets) == {"id-a", "id-other"}


def test_file_ingest_batches_symbol_embeddings():
    class RecordingEmbeddings(LocalEmbeddingStub):
        def __init__(self) -> None:
            super().__init__(dims=8)
            self.batch_calls: list[list[str]] = []
            self.single_calls: list[str] = []

        def embed(self, text: str, *, is_query: bool = False):
            self.single_calls.append(text)
            return super().embed(text, is_query=is_query)

        def embed_many(self, texts: list[str], *, is_query: bool = False):
            self.batch_calls.append(list(texts))
            return [
                LocalEmbeddingStub.embed(self, text, is_query=is_query)
                for text in texts
            ]

    embeddings = RecordingEmbeddings()
    store = InMemoryStore()
    service = CodeGraphService(store, embeddings=embeddings)
    source = "def first():\n    return 1\n\ndef second():\n    return first()\n"

    result = service.ingest_file(
        SCOPE,
        "agent",
        "corr-batch",
        "ingest-batch",
        {
            "file_path": "src/batch.py",
            "source": source,
            "language": "python",
            "reuse_unchanged_embeddings": True,
        },
    )

    assert result.symbols_indexed == 3
    assert len(embeddings.batch_calls) == 1
    assert len(embeddings.batch_calls[0]) == 4
    assert embeddings.single_calls == ["src/batch.py"]

    file_symbol = store.get_symbol(f"file:{SCOPE.project_id}:src/batch.py", SCOPE)
    file_symbol.hash_version = "legacy"
    store.put_symbol(file_symbol)
    service.ingest_file(
        SCOPE,
        "agent",
        "corr-batch-version",
        "ingest-batch-version",
        {
            "file_path": "src/batch.py",
            "source": source,
            "language": "python",
            "reuse_unchanged_embeddings": True,
        },
    )

    assert len(embeddings.batch_calls) == 1
    assert embeddings.single_calls == ["src/batch.py"]


def test_bulk_file_ingest_writes_edges_in_one_store_batch():
    class RecordingStore(InMemoryStore):
        def __init__(self) -> None:
            super().__init__()
            self.edge_batches: list[list[GraphEdge]] = []

        def put_edges(self, edges: list[GraphEdge]) -> None:
            self.edge_batches.append(list(edges))
            super().put_edges(edges)

    store = RecordingStore()
    service = CodeGraphService(store)

    result = service.ingest_file(
        SCOPE,
        "agent",
        "corr-edge-batch",
        "ingest-edge-batch",
        {
            "file_path": "src/edge_batch.py",
            "source": "def first():\n    return 1\n\ndef second():\n    return first()\n",
            "language": "python",
            "defer_cross_file_pass": True,
        },
    )

    assert result.edges_written >= 3
    assert len(store.edge_batches) == 1
    assert len(store.edge_batches[0]) == result.edges_written
    assert len(store.list_edges(SCOPE)) == result.edges_written


def test_neo4j_store_round_trip_with_fake_driver():
    driver = _FakeNeo4jDriver()
    store = Neo4jStore(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="test",
        driver=driver,
        ensure_schema=True,
    )
    symbol = GraphSymbol(
        id="sym:p:mod.fn",
        scope=SCOPE,
        kind=SymbolKind.FUNCTION,
        file_path="mod.py",
        name="fn",
        qualified_name="mod.fn",
        signature="def fn()",
        body="return 1",
        hash_value="abc",
        ai_documentation="doc",
        doc_status=DocStatus.GENERATED,
        embedding=[0.1, 0.2],
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    store.put_symbol(symbol)
    loaded = store.get_symbol(symbol.id, SCOPE)
    assert loaded.qualified_name == "mod.fn"
    assert loaded.embedding == [0.1, 0.2]

    edge = GraphEdge(
        id="edge-1",
        scope=SCOPE,
        rel_type="CALLS",
        source_id=symbol.id,
        target_id=symbol.id,
        confidence=CallConfidence.EXACT,
        metadata={"file_path": "mod.py"},
    )
    store.put_edge(edge)
    edges = store.list_edges(SCOPE)
    assert len(edges) == 1
    assert edges[0].rel_type == "CALLS"

    store.append_event({"event_id": "e1", "event_type": "FileIngested", "payload": {}})
    assert store.outbox()[0]["event_type"] == "FileIngested"

    assert store.begin_idempotency(SCOPE, "k1", "ingest") is None
    store.complete_idempotency(SCOPE, "k1", "ingest", "res-1")
    assert store.begin_idempotency(SCOPE, "k1", "ingest") == "res-1"
    store.delete_symbols([symbol.id], SCOPE)
    with pytest.raises(NotFoundError):
        store.get_symbol(symbol.id, SCOPE)


def test_neo4j_store_closes_owned_driver_when_schema_setup_fails(monkeypatch):
    class FailingDriver:
        def __init__(self) -> None:
            self.closed = False

        def session(self, database: str = "neo4j"):
            raise RuntimeError(f"schema unavailable for {database}")

        def close(self) -> None:
            self.closed = True

    driver = FailingDriver()
    monkeypatch.setattr("neo4j.GraphDatabase.driver", lambda *_args, **_kwargs: driver)

    with pytest.raises(RuntimeError, match="schema unavailable"):
        Neo4jStore(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="test",
            ensure_schema=True,
        )

    assert driver.closed is True


def test_neo4j_backed_python_ingest():
    store = Neo4jStore(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="test",
        driver=_FakeNeo4jDriver(),
        ensure_schema=True,
    )
    service = CodeGraphService(store)
    result = service.ingest_file(
        SCOPE,
        "agent",
        "corr-neo",
        "ingest-neo",
        {"file_path": "src/auth.py", "source": AUTH_SOURCE_V1, "language": "python"},
    )
    assert result.symbols_indexed >= 3
    login_id = f"sym:{SCOPE.project_id}:src.auth.login"
    neighbors = service.structural_query(SCOPE, login_id, "CALLS")
    assert any(edge["rel_type"] == "CALLS" for edge in neighbors["edges"])


def test_bootstrap_selects_neo4j_store(monkeypatch):
    def factory(**kwargs):
        return Neo4jStore(**kwargs, driver=_FakeNeo4jDriver())

    monkeypatch.setattr("code_graph_service.bootstrap.Neo4jStore", factory)
    settings = Settings(
        store_backend="neo4j",
        database_url="",
        neo4j_uri="bolt://127.0.0.1:32287",
        neo4j_user="neo4j",
        neo4j_password="secret",
        neo4j_database="neo4j",
    )
    store = build_store(settings)
    assert isinstance(store, Neo4jStore)
    store.close()


def test_bootstrap_default_store_is_neo4j(monkeypatch):
    monkeypatch.delenv("ASTLOOM_CODE_GRAPH_STORE", raising=False)
    monkeypatch.setenv("ASTLOOM_NEO4J_PASSWORD", "secret")
    monkeypatch.delenv("ASTLOOM_NEO4J_URI", raising=False)
    settings = Settings.from_environment()
    assert settings.store_backend == "neo4j"
    assert settings.neo4j_uri == "bolt://127.0.0.1:32287"
    assert settings.neo4j_gds_enabled is True
    assert settings.neo4j_gds_concurrency == 4


def test_settings_falls_back_to_shared_database_url(monkeypatch):
    monkeypatch.setenv("ASTLOOM_NEO4J_PASSWORD", "secret")
    monkeypatch.delenv("ASTLOOM_CODE_GRAPH_DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "ASTLOOM_DATABASE_URL",
        "postgresql://astloom:secret@127.0.0.1:32232/astloom",
    )
    settings = Settings.from_environment()
    assert settings.database_url.startswith("postgresql://astloom:secret@")


def test_gds_env_option_and_concurrency_cap(monkeypatch):
    monkeypatch.setenv("ASTLOOM_NEO4J_PASSWORD", "secret")
    monkeypatch.setenv("ASTLOOM_NEO4J_GDS_ENABLED", "false")
    monkeypatch.setenv("ASTLOOM_NEO4J_GDS_CONCURRENCY", "16")
    settings = Settings.from_environment()
    assert settings.neo4j_gds_enabled is False
    assert settings.neo4j_gds_concurrency == 4  # Community hard cap

    store = Neo4jStore(
        uri="bolt://127.0.0.1:1",
        user="neo4j",
        password="x",
        driver=_FakeNeo4jDriver(),
        ensure_schema=False,
        gds_enabled=False,
        gds_concurrency=16,
    )
    caps = store.capabilities()
    assert caps["gds_enabled"] is False
    assert caps["gds"] is False
    assert caps["gds_concurrency"] == 4
    store.close()

"""Live gate: RPM-session parallel ingest against Compose Neo4j.

Verifies auto file workers track RPM, LockedStore safety, and RpmSessionGate
start/end accounting while writing a real graph store.

Re-run:
  .venv/bin/python -m pytest \\
    tests/backend/services/code-graph-service/test_rpm_session_parallel_sync_live.py -m live -v
"""

from __future__ import annotations

import os
import resource
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.request import Request, urlopen

import pytest

from astloom_cli.docs_link_sync import sync_human_docs
from code_graph_service.bootstrap import Settings, build_service
from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.domain.embeddings import LocalEmbeddingStub
from code_graph_service.domain.enums import SymbolKind
from code_graph_service.application.ingest.parallel_files import run_parallel_file_jobs
from code_graph_service.llm_wiring import LlmBackedDocGenerator
from code_graph_service.locked_store import LockedStore, sync_max_file_workers
from code_graph_service.neo4j_store import Neo4jStore
from code_graph_service.postgres_store import PostgresStore
from docs_sync_service import DocsSyncService, PostgresStore as DocsPostgresStore
from docs_sync_service.core import Scope as DocsScope
from llm_gateway import LiteLlmGateway, LlmGatewaySettings

from live_helpers import (
    NEO4J_BOLT_PORT,
    NEO4J_PASSWORD,
    NEO4J_USER,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    require_tcp,
    skip_on_live_connect_error,
)

pytestmark = pytest.mark.live


def _settings_rpm(rpm: int) -> LlmGatewaySettings:
    return LlmGatewaySettings(
        enabled=True,
        api_base="http://127.0.0.1:32400",
        api_base_override="",
        api_base_is_auto=True,
        api_key="",
        default_model="fake/model",
        timeout_seconds=30.0,
        num_retries=0,
        rpm=rpm,
        host="127.0.0.1",
        port=32400,
        drop_params=True,
        reasoning_enabled=False,
        reasoning_effort="",
        debug=False,
    )


def _write_tree(root: Path, n_files: int) -> None:
    src = root / "src"
    src.mkdir(parents=True)
    for i in range(n_files):
        (src / f"mod_{i}.py").write_text(
            f"def fn_{i}(x):\n    return x + {i}\n",
            encoding="utf-8",
        )


@pytest.fixture
def local_litellm(monkeypatch):
    request_state = {"active": 0, "peak": 0, "released": False, "release_at": 4}
    request_condition = threading.Condition()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            with request_condition:
                request_state["active"] += 1
                request_state["peak"] = max(request_state["peak"], request_state["active"])
                if request_state["active"] >= request_state["release_at"]:
                    request_state["released"] = True
                    request_condition.notify_all()
                else:
                    request_condition.wait_for(lambda: request_state["released"], timeout=10.0)
            time.sleep(0.6)
            with request_condition:
                request_state["active"] -= 1
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    class NetworkLiteLlm:
        drop_params = False

        @staticmethod
        def completion(**kwargs):
            request = Request(
                f"{kwargs['api_base']}/complete",
                data=b"{}",
                method="POST",
            )
            with urlopen(request, timeout=10.0):
                pass
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="live-doc"))],
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
                model=kwargs["model"],
                id=uuid.uuid4().hex,
            )

    monkeypatch.setitem(sys.modules, "litellm", NetworkLiteLlm())
    yield SimpleNamespace(base_url=base_url, request_state=request_state)
    server.shutdown()
    server.server_close()
    thread.join(timeout=2.0)


def _docs_postgres_url() -> str:
    return (
        f"postgresql://astloom:{POSTGRES_PASSWORD}"
        f"@127.0.0.1:{POSTGRES_PORT}/astloom"
    )


def _purge_docs_scope(store: DocsPostgresStore, scope: DocsScope) -> None:
    scope_params = (scope.tenant_id, scope.workspace_id, scope.project_id)
    with store._connection.cursor() as cursor:
        for table in (
            "anchors",
            "drift_findings",
            "drafts",
            "symbols",
            "documents",
        ):
            cursor.execute(
                f"DELETE FROM docs_sync.{table} "
                "WHERE tenant_id=%s AND workspace_id=%s AND project_id=%s",
                scope_params,
            )
        cursor.execute(
            "DELETE FROM docs_sync.idempotency WHERE scope_key=%s",
            ("|".join((*scope_params, scope.project_group_id or "")),),
        )
        cursor.execute(
            "DELETE FROM docs_sync.outbox "
            "WHERE payload->>'tenant_id'=%s "
            "AND payload->>'workspace_id'=%s "
            "AND payload->>'project_id'=%s",
            scope_params,
        )


class _SlowEmbedding:
    def __init__(self, delay_seconds: float = 0.04) -> None:
        self._base = LocalEmbeddingStub(dims=16)
        self.model = self._base.model
        self.delay_seconds = delay_seconds
        self.active = 0
        self.peak = 0
        self._lock = threading.Lock()

    def embed(self, text: str, *, is_query: bool = False):
        with self._lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            time.sleep(self.delay_seconds)
            return self._base.embed(text, is_query=is_query)
        finally:
            with self._lock:
                self.active -= 1


class _ProbedDocsPostgresStore(DocsPostgresStore):
    def __init__(self, database_url: str, delay_seconds: float = 0.08) -> None:
        self.delay_seconds = delay_seconds
        self.active_writes = 0
        self.peak_writes = 0
        self._probe_lock = threading.Lock()
        super().__init__(database_url)

    def put_document(self, document):
        with self._probe_lock:
            self.active_writes += 1
            self.peak_writes = max(self.peak_writes, self.active_writes)
        try:
            time.sleep(self.delay_seconds)
            return super().put_document(document)
        finally:
            with self._probe_lock:
                self.active_writes -= 1


@pytest.fixture
def neo4j_service(monkeypatch, tmp_path: Path, local_litellm):
    require_tcp("127.0.0.1", NEO4J_BOLT_PORT)
    rpm = 4
    monkeypatch.setenv("ASTLOOM_LITELLM_RPM", str(rpm))
    monkeypatch.delenv("ASTLOOM_SYNC_MAX_FILE_WORKERS", raising=False)
    monkeypatch.delenv("ASTLOOM_SYNC_CPU_PERCENT", raising=False)
    monkeypatch.setenv("ASTLOOM_LITELLM_DOCS_ENABLED", "true")
    monkeypatch.setenv("ASTLOOM_LITELLM_MODEL_DOCS", "fake/model")
    monkeypatch.setenv("ASTLOOM_LITELLM_DEFAULT_MODEL", "fake/model")

    try:
        store = Neo4jStore(
            uri=f"bolt://127.0.0.1:{NEO4J_BOLT_PORT}",
            user=NEO4J_USER,
            password=NEO4J_PASSWORD,
            ensure_schema=True,
        )
    except Exception as exc:  # noqa: BLE001
        skip_on_live_connect_error(exc)

    settings = _settings_rpm(rpm)
    settings = LlmGatewaySettings(**{**settings.__dict__, "api_base": local_litellm.base_url})
    gateway = LiteLlmGateway(settings=settings)
    service = CodeGraphService(
        LockedStore(store, lock_reads=False, max_concurrent=4),
        docs=LlmBackedDocGenerator(gateway, settings=gateway.settings),
        embeddings=LocalEmbeddingStub(dims=16),
        llm=gateway,
    )
    scope = Scope("tenant-rpm-live", "ws-rpm-live", f"proj-{uuid.uuid4().hex[:10]}")
    tree = tmp_path / "repo"
    _write_tree(tree, n_files=4)
    yield service, scope, tree, gateway, rpm
    try:
        service.purge_scope(scope)
    except Exception:  # noqa: BLE001
        pass
    finally:
        store.close()


@pytest.fixture
def postgres_service(monkeypatch, tmp_path: Path, local_litellm):
    require_tcp("127.0.0.1", POSTGRES_PORT)
    rpm = 4
    monkeypatch.setenv("ASTLOOM_LITELLM_RPM", str(rpm))
    monkeypatch.delenv("ASTLOOM_SYNC_MAX_FILE_WORKERS", raising=False)
    monkeypatch.delenv("ASTLOOM_SYNC_CPU_PERCENT", raising=False)
    monkeypatch.setenv("ASTLOOM_LITELLM_DOCS_ENABLED", "true")
    monkeypatch.setenv("ASTLOOM_LITELLM_MODEL_DOCS", "fake/model")
    monkeypatch.setenv("ASTLOOM_LITELLM_DEFAULT_MODEL", "fake/model")
    url = (
        f"postgresql://astloom:{POSTGRES_PASSWORD}@127.0.0.1:{POSTGRES_PORT}/astloom"
    )
    try:
        store = PostgresStore(url, ensure_schema=True)
    except Exception as exc:  # noqa: BLE001
        skip_on_live_connect_error(exc)
    settings = _settings_rpm(rpm)
    settings = LlmGatewaySettings(**{**settings.__dict__, "api_base": local_litellm.base_url})
    gateway = LiteLlmGateway(settings=settings)
    service = CodeGraphService(
        LockedStore(store, lock_reads=False, max_concurrent=4),
        docs=LlmBackedDocGenerator(gateway, settings=gateway.settings),
        embeddings=LocalEmbeddingStub(dims=16),
        llm=gateway,
    )
    scope = Scope("tenant-rpm-pg-live", "ws-rpm-pg-live", f"proj-{uuid.uuid4().hex[:10]}")
    tree = tmp_path / "repo"
    _write_tree(tree, n_files=4)
    yield service, scope, tree, gateway, rpm
    try:
        service.purge_scope(scope)
    except Exception:  # noqa: BLE001
        pass
    finally:
        store.close()


def test_auto_workers_follow_live_rpm(monkeypatch):
    monkeypatch.delenv("ASTLOOM_SYNC_MAX_FILE_WORKERS", raising=False)
    monkeypatch.delenv("ASTLOOM_SYNC_CPU_PERCENT", raising=False)
    monkeypatch.setenv("ASTLOOM_LITELLM_RPM", "2")
    monkeypatch.setattr("code_graph_service.locked_store.os.cpu_count", lambda: 16)
    assert sync_max_file_workers() == 2


@pytest.mark.timeout(180)
def test_docs_postgres_isolates_same_id_across_parallel_project_writes():
    require_tcp("127.0.0.1", POSTGRES_PORT)
    store = DocsPostgresStore(_docs_postgres_url())
    service = DocsSyncService(store)
    suffix = uuid.uuid4().hex[:10]
    scopes = (
        DocsScope("tenant-doc-scope-live", "ws-doc-scope-live", f"project-a-{suffix}"),
        DocsScope("tenant-doc-scope-live", "ws-doc-scope-live", f"project-b-{suffix}"),
    )
    shared_doc_id = f"shared-live-doc-{suffix}"

    def _index(scope: DocsScope) -> None:
        service.index_document(
            scope,
            "live-agent",
            f"corr-{scope.project_id}",
            f"idem-{scope.project_id}",
            {
                "path": "docs/shared.md",
                "frontmatter": {
                    "doc_id": shared_doc_id,
                    "title": f"Shared doc for {scope.project_id}",
                    "owner": "platform",
                    "status": "active",
                    "schema_version": "1.0",
                    "linked_symbols": [],
                    "decision_refs": [],
                },
                "body": f"# {scope.project_id}\n",
            },
        )

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(_index, scopes))
        for scope in scopes:
            document = store.get_document(shared_doc_id, scope)
            assert document.scope == scope
            assert len(store.list_documents(scope)) == 1
    finally:
        for scope in scopes:
            _purge_docs_scope(store, scope)
        store.close()


@pytest.mark.parametrize("workers", (1, 2, 4))
@pytest.mark.timeout(240)
def test_live_code_and_docs_file_parallelism_matrix(
    neo4j_service,
    monkeypatch,
    tmp_path: Path,
    workers: int,
):
    service, _fixture_scope, _fixture_tree, _gateway, _rpm = neo4j_service
    monkeypatch.setenv("ASTLOOM_SYNC_MAX_FILE_WORKERS", str(workers))
    monkeypatch.setenv("ASTLOOM_SYNC_DOCS_EVIDENCE", "0")
    monkeypatch.setenv("ASTLOOM_SYNC_DOCS_EVIDENCE_APPLY", "0")
    scope = Scope(
        "tenant-file-matrix-live",
        "ws-file-matrix-live",
        f"proj-w{workers}-{uuid.uuid4().hex[:8]}",
    )
    docs_scope = DocsScope(scope.tenant_id, scope.workspace_id, scope.project_id)
    tree = tmp_path / f"matrix-w{workers}"
    _write_tree(tree, n_files=6)
    docs_dir = tree / "docs"
    docs_dir.mkdir()
    for index in range(6):
        (docs_dir / f"doc_{index}.md").write_text(
            "\n".join(
                [
                    "---",
                    f"doc_id: {scope.project_id}-doc-{index}",
                    f"title: Live matrix doc {index}",
                    "owner: platform",
                    "status: active",
                    'schema_version: "1.0"',
                    "linked_symbols: []",
                    "decision_refs: []",
                    "---",
                    "",
                    f"# Live matrix doc {index}",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    embedding_probe = _SlowEmbedding()
    service.embeddings = embedding_probe
    code_events: list[dict] = []
    docs_events: list[dict] = []
    docs_store = _ProbedDocsPostgresStore(_docs_postgres_url())
    monkeypatch.setattr(
        "astloom_cli.docs_link_sync._docs_sync_service",
        lambda: DocsSyncService(docs_store),
    )

    try:
        code_started = time.perf_counter()
        code_result = service.ingest_repo(
            scope,
            "live-agent",
            f"corr-code-w{workers}",
            f"idem-code-w{workers}-{uuid.uuid4().hex}",
            {
                "root_path": str(tree),
                "include_extensions": [".py"],
                "max_files": 6,
                "include_outcomes": True,
                "on_progress": code_events.append,
            },
        )
        code_seconds = time.perf_counter() - code_started
        docs_started = time.perf_counter()
        docs_result = sync_human_docs(
            graph_service=service,
            graph_scope=scope,
            root_path=tree,
            filters={
                "docs_enabled": True,
                "doc_match_globs": ["**/*.md"],
                "doc_exclude_dirs": [],
                "doc_exclude_globs": [],
                "doc_paths": [],
                "max_files": 20,
            },
            actor="live-agent",
            correlation_id=f"corr-docs-w{workers}",
            repo_name="parallel-live-fixture",
            on_progress=docs_events.append,
        )
        docs_seconds = time.perf_counter() - docs_started
        code_peak = max(int(event.get("files_in_flight") or 0) for event in code_events)
        docs_peak = max(int(event.get("files_in_flight") or 0) for event in docs_events)

        assert code_result.files_ingested == 6
        assert code_result.files_failed == 0
        assert code_peak == workers
        assert embedding_probe.peak == workers
        assert docs_result.docs_indexed == 6
        assert docs_result.errors == []
        assert docs_peak == workers
        assert docs_store.peak_writes == workers
        assert len(docs_store.list_documents(docs_scope)) == 6
        print(
            f"parallel matrix workers={workers} "
            f"code={code_seconds:.2f}s code_peak={code_peak} "
            f"docs={docs_seconds:.2f}s docs_peak={docs_peak}"
        )
    finally:
        _purge_docs_scope(docs_store, docs_scope)
        docs_store.close()
        service.purge_scope(scope)


@pytest.mark.parametrize("workers", (1, 2, 4))
@pytest.mark.timeout(180)
def test_live_llm_rpm_sessions_follow_parallel_worker_level(
    neo4j_service,
    local_litellm,
    workers: int,
):
    service, scope, tree, gateway, rpm = neo4j_service
    local_litellm.request_state["release_at"] = workers
    results = []
    result_lock = threading.Lock()
    peak_rpm_inflight = 0
    stop = threading.Event()

    def _watch() -> None:
        nonlocal peak_rpm_inflight
        while not stop.is_set():
            peak_rpm_inflight = max(
                peak_rpm_inflight,
                int(gateway.rpm_sessions_snapshot().get("inflight_count") or 0),
            )
            time.sleep(0.005)

    def _ingest(index: int, path: Path) -> None:
        result = service.ingest_file(
            scope,
            "live-agent",
            f"corr-llm-w{workers}",
            f"idem-llm-w{workers}-{index}-{uuid.uuid4().hex}",
            {
                "file_path": f"src/{path.name}",
                "source": path.read_text(encoding="utf-8"),
                "language": "python",
            },
        )
        with result_lock:
            results.append(result)

    watcher = threading.Thread(target=_watch, daemon=True)
    watcher.start()
    started = time.perf_counter()
    try:
        run_parallel_file_jobs(
            workers=workers,
            items=sorted((tree / "src").glob("*.py")),
            fn=_ingest,
        )
    finally:
        stop.set()
        watcher.join(timeout=2.0)
    elapsed = time.perf_counter() - started
    snapshot = gateway.rpm_sessions_snapshot()

    assert len(results) == 4
    assert all(result.symbols_documented == 1 for result in results)
    assert local_litellm.request_state["peak"] == workers
    assert peak_rpm_inflight == workers
    assert snapshot["rpm"] == rpm
    assert snapshot["starts_in_window"] == 4
    assert snapshot["inflight_count"] == 0
    assert len(snapshot["history"]) == 4
    assert {entry["status"] for entry in snapshot["history"]} == {"ok"}
    print(
        f"llm matrix workers={workers} wall={elapsed:.2f}s "
        f"http_peak={local_litellm.request_state['peak']} "
        f"rpm_peak={peak_rpm_inflight}"
    )


@pytest.mark.timeout(180)
def test_parallel_ingest_uses_heuristic_docs_against_neo4j(neo4j_service, monkeypatch):
    service, scope, tree, gateway, rpm = neo4j_service
    monkeypatch.delenv("ASTLOOM_SYNC_CPU_PERCENT", raising=False)
    monkeypatch.delenv("ASTLOOM_SYNC_MAX_FILE_WORKERS", raising=False)
    monkeypatch.setattr("code_graph_service.locked_store.os.cpu_count", lambda: 8)
    workers = sync_max_file_workers()
    assert workers == min(8, rpm)

    peak_inflight = {"n": 0}
    violations = {"n": 0}
    stop = threading.Event()

    def _watch() -> None:
        while not stop.is_set():
            snap = gateway.rpm_sessions_snapshot()
            inflight = int(snap.get("inflight_count") or 0)
            starts = int(snap.get("starts_in_window") or 0)
            peak_inflight["n"] = max(peak_inflight["n"], inflight)
            if inflight > rpm or starts > rpm:
                violations["n"] += 1
            time.sleep(0.02)

    watcher = threading.Thread(target=_watch, daemon=True)
    watcher.start()
    try:
        result = service.ingest_repo(
            scope,
            "live-agent",
            f"corr-rpm-{uuid.uuid4().hex[:8]}",
            f"idem-rpm-{uuid.uuid4().hex}",
            {
                "root_path": str(tree),
                "include_extensions": [".py"],
                "max_files": 20,
                "include_outcomes": True,
            },
        )
    finally:
        stop.set()
        watcher.join(timeout=2.0)

    assert result.files_discovered == 4
    assert result.files_failed == 0
    assert result.files_ingested + result.files_skipped == 4
    assert result.symbols_indexed >= 4
    assert violations["n"] == 0

    snap = gateway.rpm_sessions_snapshot()
    assert snap["inflight_count"] == 0
    assert snap["rpm"] == rpm
    assert snap["history"] == []
    assert peak_inflight["n"] == 0

    symbols = service.store.list_symbols(scope)
    files = [s for s in symbols if s.kind == SymbolKind.FILE]
    assert len(files) >= 4


@pytest.mark.timeout(180)
def test_parallel_ingest_uses_heuristic_docs_against_postgres(postgres_service, monkeypatch):
    test_parallel_ingest_uses_heuristic_docs_against_neo4j(postgres_service, monkeypatch)


@pytest.mark.timeout(180)
def test_cli_progress_reports_heuristic_docs_without_rpm_sessions(
    neo4j_service,
    monkeypatch,
    capsys,
    tmp_path: Path,
):
    from astloom_cli.commands.sync import _sync_one_root

    service, scope, tree, _gateway, _rpm = neo4j_service
    (tree / "astloom.sync.yaml").write_text(
        "code:\n  exclude: []\ndocs:\n  match: []\n  exclude: []\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "astloom_cli.sync_progress.tracker.progress_path",
        lambda root=None: tmp_path / "sync-progress.json",
    )
    args = SimpleNamespace(
        exclude_dir=[],
        include_path=[],
        include_ext=[],
        progress_interval=0.05,
        max_files=5,
    )

    _sync_one_root(svc=service, scope=scope, root_path=tree, args=args)

    output = capsys.readouterr().out
    assert "parallel 4 active / 4 workers" in output
    assert "rpm inflight 0/4  starts 0/4" in output
    assert "RPM final    inflight 0/4  starts 0/4  history 0" in output


@pytest.mark.timeout(300)
def test_production_build_uses_heuristic_docs_without_rpm_sessions(
    monkeypatch,
    tmp_path: Path,
    local_litellm,
):
    require_tcp("127.0.0.1", NEO4J_BOLT_PORT)
    monkeypatch.setenv("ASTLOOM_LITELLM_ENABLED", "true")
    monkeypatch.setenv("ASTLOOM_LITELLM_DOCS_ENABLED", "true")
    monkeypatch.setenv("ASTLOOM_LITELLM_DEFAULT_MODEL", "fake/model")
    monkeypatch.setenv("ASTLOOM_LITELLM_MODEL_DOCS", "fake/model")
    monkeypatch.setenv("ASTLOOM_LITELLM_API_BASE", local_litellm.base_url)
    monkeypatch.setenv("ASTLOOM_LITELLM_RPM", "5")
    monkeypatch.setenv("ASTLOOM_EMBEDDING_PROVIDER", "local_bge")
    monkeypatch.setenv("ASTLOOM_EMBEDDING_LOCAL_ENABLED", "true")
    monkeypatch.setenv("ASTLOOM_EMBEDDING_CACHE_DIR", "/opt/astloom-models")
    monkeypatch.setenv("ASTLOOM_EMBEDDING_DEVICE", "cpu")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    monkeypatch.delenv("ASTLOOM_SYNC_CPU_PERCENT", raising=False)
    monkeypatch.delenv("ASTLOOM_SYNC_MAX_FILE_WORKERS", raising=False)
    # Empty database_url: production neo4j-only path (no pgvector). Local BGE is
    # offline/empty-cache here — HybridEmbeddings must soft-fail to stub.
    settings = Settings(
        store_backend="neo4j",
        database_url="",
        neo4j_uri=f"bolt://127.0.0.1:{NEO4J_BOLT_PORT}",
        neo4j_user=NEO4J_USER,
        neo4j_password=NEO4J_PASSWORD,
        neo4j_database="neo4j",
    )
    service = build_service(settings)
    scope = Scope("tenant-rpm-production", "ws-rpm-production", f"proj-{uuid.uuid4().hex[:10]}")
    tree = tmp_path / "production-repo"
    _write_tree(tree, n_files=5)
    peak_inflight = 0
    stop = threading.Event()

    def watch_sessions() -> None:
        nonlocal peak_inflight
        while not stop.is_set():
            peak_inflight = max(
                peak_inflight,
                int(service.llm_sessions_snapshot().get("inflight_count") or 0),
            )
            time.sleep(0.01)

    watcher = threading.Thread(target=watch_sessions, daemon=True)
    watcher.start()
    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    try:
        try:
            result = service.ingest_repo(
                scope,
                "live-agent",
                f"corr-production-{uuid.uuid4().hex[:8]}",
                f"idem-production-{uuid.uuid4().hex}",
                {
                    "root_path": str(tree),
                    "include_extensions": [".py"],
                    "max_files": 5,
                    "include_outcomes": True,
                },
            )
        finally:
            stop.set()
            watcher.join(timeout=2.0)
        wall_seconds = time.perf_counter() - wall_start
        cpu_seconds = time.process_time() - cpu_start
        assert result.files_discovered == 5
        assert result.files_ingested == 5
        assert result.files_failed == 0
        assert local_litellm.request_state["peak"] == 0
        assert peak_inflight == 0
        assert service.llm_sessions_snapshot()["history"] == []
        print(
            f"resource metrics: wall={wall_seconds:.2f}s cpu={cpu_seconds:.2f}s "
            f"cpu/wall={cpu_seconds / max(wall_seconds, 0.001):.2f} "
            f"rss_kib={resource.getrusage(resource.RUSAGE_SELF).ru_maxrss} "
            f"http_peak={local_litellm.request_state['peak']} rpm_peak={peak_inflight}"
        )
    finally:
        try:
            service.purge_scope(scope)
        finally:
            service.store.close()

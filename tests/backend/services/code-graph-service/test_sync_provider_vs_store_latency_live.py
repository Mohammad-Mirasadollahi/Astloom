"""Live latency seam: stub/heuristic ingest vs OpenRouter Provider path.

Evidence-oriented gate for slow-sync diagnosis. Stub path must stay fast on
real Neo4j (store not the bottleneck). Optional Provider comparison when
``ASTLOOM_DIAG_PROVIDER_LIVE=1`` (burns remote RPM; off by default).

Re-run:
  .venv/bin/python -m pytest \\
    tests/backend/services/code-graph-service/test_sync_provider_vs_store_latency_live.py -m live -v
  ASTLOOM_DIAG_PROVIDER_LIVE=1 .venv/bin/python -m pytest \\
    tests/backend/services/code-graph-service/test_sync_provider_vs_store_latency_live.py -m live -v
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import pytest

from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.domain.embeddings import LocalEmbeddingStub
from code_graph_service.llm_wiring import HeuristicDocGenerator, HybridEmbeddings, LlmBackedDocGenerator
from code_graph_service.locked_store import LockedStore
from code_graph_service.neo4j_store import Neo4jStore
from llm_gateway import LiteLlmGateway, LlmGatewaySettings

from live_helpers import NEO4J_BOLT_PORT, NEO4J_PASSWORD, NEO4J_USER, require_tcp, skip_on_live_connect_error

pytestmark = pytest.mark.live


def _write_tree(root: Path, n_files: int) -> None:
    src = root / "src"
    src.mkdir(parents=True)
    for i in range(n_files):
        (src / f"mod_{i}.py").write_text(
            f"def fn_{i}(x):\n    \"\"\"diag symbol {i}\"\"\"\n    return x + {i}\n",
            encoding="utf-8",
        )


def _neo4j_service(*, docs, embeddings, llm=None) -> tuple[CodeGraphService, Neo4jStore]:
    require_tcp("127.0.0.1", NEO4J_BOLT_PORT)
    try:
        store = Neo4jStore(
            uri=f"bolt://127.0.0.1:{NEO4J_BOLT_PORT}",
            user=NEO4J_USER,
            password=NEO4J_PASSWORD,
            ensure_schema=True,
        )
    except Exception as exc:  # noqa: BLE001
        skip_on_live_connect_error(exc)
    service = CodeGraphService(
        LockedStore(store, lock_reads=False, max_concurrent=8),
        docs=docs,
        embeddings=embeddings,
        llm=llm,
    )
    return service, store


def _ingest(service: CodeGraphService, scope: Scope, tree: Path) -> tuple[float, int]:
    t0 = time.perf_counter()
    result = service.ingest_repo(
        scope,
        "latency-live",
        f"corr-{scope.project_id}",
        f"idem-{uuid.uuid4().hex}",
        {
            "root_path": str(tree),
            "include_extensions": [".py"],
            "max_files": 50,
            "include_outcomes": True,
        },
    )
    sec = time.perf_counter() - t0
    ingested = int(getattr(result, "files_ingested", 0) or 0)
    failed = int(getattr(result, "files_failed", 0) or 0)
    assert failed == 0, f"ingest failures: {failed}"
    assert ingested > 0
    return sec, ingested


@pytest.mark.timeout(120)
def test_store_path_ingest_rate_without_provider(tmp_path: Path, monkeypatch):
    """Neo4j + heuristic docs must sustain >> 1 file/s on a tiny tree."""
    monkeypatch.setenv("ASTLOOM_SYNC_MAX_FILE_WORKERS", "8")
    monkeypatch.delenv("ASTLOOM_SYNC_CPU_PERCENT", raising=False)
    monkeypatch.setenv("ASTLOOM_LITELLM_ENABLED", "false")
    n_files = 20
    tree = tmp_path / "stub-repo"
    _write_tree(tree, n_files)
    service, store = _neo4j_service(
        docs=HeuristicDocGenerator(),
        embeddings=LocalEmbeddingStub(dims=16),
        llm=None,
    )
    scope = Scope("tenant-latency-live", "ws-latency-live", f"stub-{uuid.uuid4().hex[:10]}")
    try:
        sec, ingested = _ingest(service, scope, tree)
        rate = ingested / sec if sec else 0.0
        # Evidence bar from 2026-09-03 diag: 50 files @ ~4.6/s on this host.
        assert rate >= 1.0, f"store-path too slow: {rate:.3f} files/s over {sec:.2f}s ({ingested} files)"
    finally:
        try:
            service.purge_scope(scope)
        finally:
            store.close()


@pytest.mark.timeout(300)
def test_provider_path_slower_than_store_when_enabled(tmp_path: Path, monkeypatch):
    """When explicitly enabled, OpenRouter docs path must be materially slower than stub."""
    if os.environ.get("ASTLOOM_DIAG_PROVIDER_LIVE", "").strip() not in {"1", "true", "yes"}:
        pytest.skip("set ASTLOOM_DIAG_PROVIDER_LIVE=1 to burn remote Provider RPM")

    monkeypatch.setenv("ASTLOOM_SYNC_MAX_FILE_WORKERS", "8")
    monkeypatch.delenv("ASTLOOM_SYNC_CPU_PERCENT", raising=False)
    n_files = 5
    settings = LlmGatewaySettings.from_environment()
    if not settings.enabled or not (settings.default_model or "").strip():
        pytest.skip("LiteLLM not configured")

    gw = LiteLlmGateway(settings)
    stub_tree = tmp_path / "stub"
    prov_tree = tmp_path / "prov"
    _write_tree(stub_tree, n_files)
    _write_tree(prov_tree, n_files)

    stub_svc, store = _neo4j_service(
        docs=HeuristicDocGenerator(),
        embeddings=LocalEmbeddingStub(dims=16),
        llm=None,
    )
    scope_stub = Scope("tenant-latency-live", "ws-latency-live", f"s-{uuid.uuid4().hex[:8]}")
    try:
        stub_sec, stub_n = _ingest(stub_svc, scope_stub, stub_tree)
        stub_rate = stub_n / stub_sec if stub_sec else 0.0
    finally:
        try:
            stub_svc.purge_scope(scope_stub)
        except Exception:  # noqa: BLE001
            pass

    prov_svc = CodeGraphService(
        LockedStore(store, lock_reads=False, max_concurrent=8),
        docs=LlmBackedDocGenerator(gw, settings=settings),
        embeddings=HybridEmbeddings(
            gateway=gw,
            stub=LocalEmbeddingStub(dims=16),
            dims=16,
            settings=settings,
            local=None,
        ),
        llm=gw,
    )
    scope_prov = Scope("tenant-latency-live", "ws-latency-live", f"p-{uuid.uuid4().hex[:8]}")
    try:
        prov_sec, prov_n = _ingest(prov_svc, scope_prov, prov_tree)
        prov_rate = prov_n / prov_sec if prov_sec else 0.0
        # Provider must be at least 3× slower than stub on same host/tree size.
        assert stub_rate > 0 and prov_rate > 0
        assert stub_rate / prov_rate >= 3.0, (
            f"expected Provider bottleneck: stub={stub_rate:.3f}/s prov={prov_rate:.3f}/s "
            f"({stub_sec:.1f}s vs {prov_sec:.1f}s)"
        )
    finally:
        try:
            prov_svc.purge_scope(scope_prov)
        finally:
            store.close()

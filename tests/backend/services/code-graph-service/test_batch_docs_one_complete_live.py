"""Live evidence: batched docs on OpenRouter path (remote docs + remote embeds)."""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

import pytest

from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.llm_wiring import LlmBackedDocGenerator, build_embeddings
from code_graph_service.locked_store import LockedStore
from code_graph_service.neo4j_store import Neo4jStore
from llm_gateway import LiteLlmGateway, LlmGatewaySettings

from live_helpers import NEO4J_BOLT_PORT, NEO4J_PASSWORD, NEO4J_USER, require_tcp, skip_on_live_connect_error

pytestmark = pytest.mark.live

_DIAG = Path("/opt/Astloom/.astloom/diag-slow-sync-2026-09-03")


def _require_openrouter_mode(monkeypatch: pytest.MonkeyPatch) -> LlmGatewaySettings:
    """Force the operator path: OpenRouter docs + LiteLLM embeds (no local BGE)."""
    monkeypatch.setenv("ASTLOOM_LITELLM_DOCS_ENABLED", "true")
    monkeypatch.setenv("ASTLOOM_LITELLM_EMBEDDINGS_ENABLED", "true")
    monkeypatch.setenv("ASTLOOM_EMBEDDING_PROVIDER", "litellm")
    monkeypatch.setenv("ASTLOOM_EMBEDDING_LOCAL_ENABLED", "false")
    settings = LlmGatewaySettings.from_environment()
    if not settings.enabled or not (settings.default_model or "").strip():
        pytest.skip("LiteLLM / OpenRouter not configured")
    if not str(os.environ.get("ASTLOOM_LITELLM_MODEL_EMBED", "") or "").strip():
        pytest.skip("ASTLOOM_LITELLM_MODEL_EMBED required for OpenRouter embed path")
    return settings


@pytest.mark.timeout(420)
def test_batch_docs_openrouter_one_complete_per_multi_symbol_file(tmp_path: Path, monkeypatch):
    """N symbols → 1 docs complete; embeds go through OpenRouter/LiteLLM (not local)."""
    if os.environ.get("ASTLOOM_DIAG_PROVIDER_LIVE", "").strip() not in {"1", "true", "yes"}:
        pytest.skip("set ASTLOOM_DIAG_PROVIDER_LIVE=1 to burn remote OpenRouter RPM")

    settings = _require_openrouter_mode(monkeypatch)
    monkeypatch.setenv("ASTLOOM_SYNC_MAX_FILE_WORKERS", "1")

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

    gw = LiteLlmGateway(settings)
    counters = {"complete": 0, "embed_many": 0, "embed": 0}
    real_complete = gw.complete
    real_embed_many = gw.embed_many
    real_embed = gw.embed

    def counting_complete(request):  # noqa: ANN001
        counters["complete"] += 1
        return real_complete(request)

    def counting_embed_many(texts, **kwargs):  # noqa: ANN001
        counters["embed_many"] += 1
        return real_embed_many(texts, **kwargs)

    def counting_embed(text, **kwargs):  # noqa: ANN001
        counters["embed"] += 1
        return real_embed(text, **kwargs)

    gw.complete = counting_complete  # type: ignore[method-assign]
    gw.embed_many = counting_embed_many  # type: ignore[method-assign]
    gw.embed = counting_embed  # type: ignore[method-assign]

    embeddings = build_embeddings(gw, settings=settings, environ=dict(os.environ))
    assert embeddings.local is None, "OpenRouter mode must not attach local BGE"

    n_symbols = 5
    body = "\n\n".join(f"def fn_{i}(x):\n    return x + {i}\n" for i in range(n_symbols))
    tree = tmp_path / "batch-docs-or"
    (tree / "src").mkdir(parents=True)
    (tree / "src" / "multi.py").write_text(body, encoding="utf-8")

    service = CodeGraphService(
        LockedStore(store, lock_reads=False, max_concurrent=4),
        docs=LlmBackedDocGenerator(gw, settings=settings),
        embeddings=embeddings,
        llm=gw,
    )
    scope = Scope("tenant-batch-or", "ws-batch-or", f"b-{uuid.uuid4().hex[:10]}")
    t0 = time.perf_counter()
    try:
        result = service.ingest_repo(
            scope,
            "batch-docs-openrouter",
            f"corr-{scope.project_id}",
            f"idem-{uuid.uuid4().hex}",
            {
                "root_path": str(tree),
                "include_extensions": [".py"],
                "max_files": 10,
                "include_outcomes": True,
            },
        )
        sec = time.perf_counter() - t0
        ingested = int(getattr(result, "files_ingested", 0) or 0)
        assert ingested == 1
        assert counters["complete"] == 1, (
            f"expected 1 batched docs complete for {n_symbols} symbols, "
            f"got {counters['complete']} in {sec:.2f}s"
        )
        remote_embed_calls = counters["embed_many"] + counters["embed"]
        assert remote_embed_calls >= 1, "expected at least one OpenRouter/LiteLLM embed call"
        assert str(getattr(embeddings, "_backend", "")).startswith("litellm"), (
            f"embed backend was {embeddings._backend!r}, want litellm"
        )
        evidence = {
            "mode": "openrouter_docs_and_embeds",
            "symbols": n_symbols,
            "docs_complete_calls": counters["complete"],
            "embed_many_calls": counters["embed_many"],
            "embed_calls": counters["embed"],
            "embed_backend": embeddings.backend_name,
            "wall_sec": round(sec, 3),
            "files_ingested": ingested,
            "files_per_sec": round(ingested / sec, 3) if sec else 0.0,
        }
        _DIAG.mkdir(parents=True, exist_ok=True)
        (_DIAG / "batch-docs-openrouter-live.json").write_text(
            json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
        )
    finally:
        try:
            service.purge_scope(scope)
        finally:
            store.close()


@pytest.mark.timeout(600)
def test_batch_docs_openrouter_multi_file_throughput(tmp_path: Path, monkeypatch):
    """5 files × 4 symbols on OpenRouter: docs completes == files (not symbols)."""
    if os.environ.get("ASTLOOM_DIAG_PROVIDER_LIVE", "").strip() not in {"1", "true", "yes"}:
        pytest.skip("set ASTLOOM_DIAG_PROVIDER_LIVE=1 to burn remote OpenRouter RPM")

    settings = _require_openrouter_mode(monkeypatch)
    monkeypatch.setenv("ASTLOOM_SYNC_MAX_FILE_WORKERS", "4")

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

    gw = LiteLlmGateway(settings)
    counters = {"complete": 0, "embed_many": 0, "embed": 0}
    real_complete = gw.complete
    real_embed_many = gw.embed_many
    real_embed = gw.embed

    def counting_complete(request):  # noqa: ANN001
        counters["complete"] += 1
        return real_complete(request)

    def counting_embed_many(texts, **kwargs):  # noqa: ANN001
        counters["embed_many"] += 1
        return real_embed_many(texts, **kwargs)

    def counting_embed(text, **kwargs):  # noqa: ANN001
        counters["embed"] += 1
        return real_embed(text, **kwargs)

    gw.complete = counting_complete  # type: ignore[method-assign]
    gw.embed_many = counting_embed_many  # type: ignore[method-assign]
    gw.embed = counting_embed  # type: ignore[method-assign]

    n_files, n_syms = 5, 4
    tree = tmp_path / "batch-speed-or"
    (tree / "src").mkdir(parents=True)
    for i in range(n_files):
        body = "\n\n".join(f"def f_{i}_{j}(x):\n    return x + {j}\n" for j in range(n_syms))
        (tree / "src" / f"m{i}.py").write_text(body, encoding="utf-8")

    embeddings = build_embeddings(gw, settings=settings, environ=dict(os.environ))
    assert embeddings.local is None
    service = CodeGraphService(
        LockedStore(store, lock_reads=False, max_concurrent=8),
        docs=LlmBackedDocGenerator(gw, settings=settings),
        embeddings=embeddings,
        llm=gw,
    )
    scope = Scope("tenant-batch-or", "ws-batch-or", f"s-{uuid.uuid4().hex[:10]}")
    t0 = time.perf_counter()
    try:
        result = service.ingest_repo(
            scope,
            "batch-speed-openrouter",
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
        assert ingested == n_files
        assert counters["complete"] == n_files, (
            f"expected {n_files} batched docs completes, got {counters['complete']}"
        )
        assert counters["embed_many"] + counters["embed"] >= 1
        assert str(getattr(embeddings, "_backend", "")).startswith("litellm")
        evidence = {
            "mode": "openrouter_docs_and_embeds",
            "files": ingested,
            "symbols_per_file": n_syms,
            "symbol_total": n_files * n_syms,
            "docs_complete_calls": counters["complete"],
            "pre_fix_would_be_completes": n_files * n_syms,
            "embed_many_calls": counters["embed_many"],
            "embed_calls": counters["embed"],
            "embed_backend": embeddings.backend_name,
            "wall_sec": round(sec, 3),
            "files_per_sec": round(ingested / sec, 3) if sec else 0.0,
            "docs_reduction_vs_per_symbol": round((n_files * n_syms) / max(1, counters["complete"]), 2),
        }
        _DIAG.mkdir(parents=True, exist_ok=True)
        (_DIAG / "batch-docs-openrouter-speed.json").write_text(
            json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
        )
    finally:
        try:
            service.purge_scope(scope)
        finally:
            store.close()

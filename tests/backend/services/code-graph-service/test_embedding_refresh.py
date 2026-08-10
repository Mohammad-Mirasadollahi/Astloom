"""GAP-T03: code-graph embedding refresh under refresh-policy.json."""

from __future__ import annotations

from pathlib import Path
import threading
import time
from types import SimpleNamespace

from code_graph_service.core import CodeGraphService, LocalEmbeddingStub, Scope
from code_graph_service.domain.rag import SEARCHABLE_SYMBOL_KINDS
from code_graph_service.postgres_side import InMemoryEmbeddingIndex
from code_graph_service.testing import InMemoryStore

SCOPE = Scope("t", "w", "p")
POLICY = (
    Path(__file__).resolve().parents[4]
    / "backend"
    / "configs"
    / "embeddings"
    / "refresh-policy.json"
)

SOURCE = """\
def helper():
    return 1

def run():
    return helper()
"""


def _ingest(service: CodeGraphService, key: str = "k1") -> None:
    service.ingest_file(
        SCOPE,
        "agent",
        "corr",
        key,
        {"file_path": "src/mod.py", "source": SOURCE, "language": "python"},
    )


def test_refresh_embeddings_indexes_missing_rows():
    store = InMemoryStore()
    index = InMemoryEmbeddingIndex()
    service = CodeGraphService(
        store,
        embeddings=LocalEmbeddingStub(dims=16, model="local-hash-v1"),
        embedding_index=index,
    )
    _ingest(service)
    assert index.list_symbol_models(SCOPE)  # ingest already indexed
    index.wipe_scope(SCOPE)
    events: list[dict] = []
    report = service.refresh_embeddings(
        SCOPE, policy_path=POLICY, on_progress=events.append
    )
    assert report.state == "complete"
    assert report.scanned >= 2
    assert report.refreshed >= 1
    assert index.list_symbol_models(SCOPE)
    assert report.policy_id == "default-embedding-refresh"
    assert events
    assert events[0]["phase"] == "embeddings"
    assert events[0]["status"] == "started"
    assert events[-1]["status"] == "finished"
    assert events[-1]["done"] == report.refreshed


def test_refresh_embeddings_skips_when_model_unchanged():
    store = InMemoryStore()
    index = InMemoryEmbeddingIndex()
    stub = LocalEmbeddingStub(dims=16, model="local-hash-v1")
    service = CodeGraphService(store, embeddings=stub, embedding_index=index)
    _ingest(service)
    second = service.refresh_embeddings(SCOPE, policy_path=POLICY)
    assert second.state == "complete"
    assert second.skipped >= 1
    assert second.refreshed == 0


def test_refresh_embeddings_force_and_model_mismatch():
    store = InMemoryStore()
    index = InMemoryEmbeddingIndex()
    service = CodeGraphService(
        store,
        embeddings=LocalEmbeddingStub(dims=16, model="model-a"),
        embedding_index=index,
    )
    _ingest(service)
    service.embeddings = LocalEmbeddingStub(dims=16, model="model-b")
    report = service.refresh_embeddings(SCOPE, policy_path=POLICY)
    assert report.state == "complete"
    assert report.refreshed >= 1
    assert report.reasons.get("configured_model_mismatch", 0) >= 1
    forced = service.refresh_embeddings(SCOPE, force=True, policy_path=POLICY)
    assert forced.state == "complete"
    assert forced.refreshed >= 1
    assert forced.reasons.get("operator_force_refresh", 0) >= 1


def test_refresh_embeddings_dry_run_does_not_write():
    store = InMemoryStore()
    index = InMemoryEmbeddingIndex()
    service = CodeGraphService(
        store,
        embeddings=LocalEmbeddingStub(dims=16, model="local-hash-v1"),
        embedding_index=index,
    )
    _ingest(service)
    index.wipe_scope(SCOPE)
    report = service.refresh_embeddings(SCOPE, dry_run=True, policy_path=POLICY)
    assert report.state == "complete"
    assert report.dry_run is True
    assert report.refreshed >= 1
    assert index.list_symbol_models(SCOPE) == {}


def test_refresh_embeddings_rejects_incomplete_tenant_scope():
    store = InMemoryStore()
    index = InMemoryEmbeddingIndex()
    service = CodeGraphService(
        store,
        embeddings=LocalEmbeddingStub(dims=16, model="local-hash-v1"),
        embedding_index=index,
    )
    bad = SimpleNamespace(tenant_id="", workspace_id="w", project_id="p")
    report = service.refresh_embeddings(bad, policy_path=POLICY)
    assert report.state == "failed"
    assert report.error
    assert "tenant_id" in report.error


def test_noop_repo_ingest_backfills_missing_embeddings(tmp_path):
    source = tmp_path / "mod.py"
    source.write_text(SOURCE, encoding="utf-8")
    index = InMemoryEmbeddingIndex()
    service = CodeGraphService(
        InMemoryStore(),
        embeddings=LocalEmbeddingStub(dims=16, model="local-hash-v1"),
        embedding_index=index,
    )
    first = service.ingest_repo(
        SCOPE,
        "agent",
        "corr-1",
        "repo-1",
        {"root_path": str(tmp_path)},
    )
    assert first.embedding_refresh["state"] == "complete"
    index.wipe_scope(SCOPE)

    second = service.ingest_repo(
        SCOPE,
        "agent",
        "corr-2",
        "repo-2",
        {"root_path": str(tmp_path)},
    )

    assert second.files_ingested == 0
    assert second.embedding_refresh["state"] == "complete"
    # Noop drains a capped backlog (default max_pending=256), not unbounded.
    assert second.embedding_refresh["refreshed"] >= 1
    assert index.list_symbol_models(SCOPE)


def test_incremental_ingest_refresh_only_touched_file(tmp_path, monkeypatch):
    """Regression: small sync must not re-embed the whole project backlog."""
    monkeypatch.delenv("ASTLOOM_EMBEDDING_REFRESH_FULL", raising=False)
    (tmp_path / "a.py").write_text(
        "def a():\n    return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "b.py").write_text(
        "def b():\n    return 2\n",
        encoding="utf-8",
    )
    index = InMemoryEmbeddingIndex()
    service = CodeGraphService(
        InMemoryStore(),
        embeddings=LocalEmbeddingStub(dims=16, model="local-hash-v1"),
        embedding_index=index,
    )
    service.ingest_repo(
        SCOPE,
        "agent",
        "corr-1",
        "repo-1",
        {"root_path": str(tmp_path)},
    )
    index.wipe_scope(SCOPE)
    # Touch only a.py
    (tmp_path / "a.py").write_text(
        "def a():\n    return 11\n",
        encoding="utf-8",
    )
    second = service.ingest_repo(
        SCOPE,
        "agent",
        "corr-2",
        "repo-2",
        {"root_path": str(tmp_path)},
    )
    assert second.files_ingested >= 1
    assert second.embedding_refresh["state"] == "complete"
    models = index.list_symbol_models(SCOPE)
    assert models
    # b.py symbols remain without embeddings after wipe+a-only refresh
    b_syms = service.store.list_symbols_for_file(SCOPE, "b.py")
    b_ids = {s.id for s in b_syms}
    assert b_ids
    assert not (b_ids & set(models))


def test_refresh_embeddings_respects_max_pending():
    store = InMemoryStore()
    index = InMemoryEmbeddingIndex()
    service = CodeGraphService(
        store,
        embeddings=LocalEmbeddingStub(dims=16, model="local-hash-v1"),
        embedding_index=index,
    )
    _ingest(service)
    index.wipe_scope(SCOPE)
    report = service.refresh_embeddings(SCOPE, max_pending=1, policy_path=POLICY)
    assert report.state == "complete"
    assert report.refreshed == 1
    assert report.reasons.get("deferred_over_max_pending", 0) >= 1


def test_full_embedding_refresh_mode_heals_untouched_files(tmp_path, monkeypatch):
    """sync heal: incremental file pass + full-project embedding refresh."""
    monkeypatch.delenv("ASTLOOM_EMBEDDING_REFRESH_FULL", raising=False)
    (tmp_path / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("def b():\n    return 2\n", encoding="utf-8")
    index = InMemoryEmbeddingIndex()
    service = CodeGraphService(
        InMemoryStore(),
        embeddings=LocalEmbeddingStub(dims=16, model="local-hash-v1"),
        embedding_index=index,
    )
    service.ingest_repo(
        SCOPE,
        "agent",
        "corr-1",
        "repo-1",
        {"root_path": str(tmp_path)},
    )
    index.wipe_scope(SCOPE)
    (tmp_path / "a.py").write_text("def a():\n    return 11\n", encoding="utf-8")
    healed = service.ingest_repo(
        SCOPE,
        "agent",
        "corr-2",
        "repo-2",
        {
            "root_path": str(tmp_path),
            "embedding_refresh_mode": "full",
        },
    )
    assert healed.embedding_refresh["state"] == "complete"
    models = set(index.list_symbol_models(SCOPE))
    b_searchable = {
        s.id
        for s in service.store.list_symbols_for_file(SCOPE, "b.py")
        if str(getattr(s, "kind", "") or "") in SEARCHABLE_SYMBOL_KINDS
    }
    assert b_searchable
    assert b_searchable <= models


def test_refresh_embeddings_after_ingest_mode_full_ignores_file_scope(monkeypatch):
    monkeypatch.delenv("ASTLOOM_EMBEDDING_REFRESH_FULL", raising=False)
    calls: list[dict] = []

    class _Probe(CodeGraphService):
        def refresh_embeddings(self, scope, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(kwargs)
            return SimpleNamespace(
                public=lambda: {"state": "complete", "refreshed": 0},
            )

    svc = _Probe(
        InMemoryStore(),
        embeddings=LocalEmbeddingStub(dims=16, model="local-hash-v1"),
        embedding_index=InMemoryEmbeddingIndex(),
    )
    svc.refresh_embeddings_after_ingest(
        SCOPE,
        file_paths=["only/a.py"],
        mode="full",
        policy_path=POLICY,
    )
    assert len(calls) == 1
    assert calls[0].get("file_paths") is None
    assert calls[0].get("max_pending") is None


def test_sync_repo_forwards_embedding_refresh_mode_full(tmp_path, monkeypatch):
    """CLI heal → payload embedding_refresh_mode=full reaches after-ingest helper."""
    monkeypatch.delenv("ASTLOOM_EMBEDDING_REFRESH_FULL", raising=False)
    (tmp_path / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    modes: list[str] = []

    class _Probe(CodeGraphService):
        def refresh_embeddings_after_ingest(self, scope, **kwargs):  # type: ignore[no-untyped-def]
            modes.append(str(kwargs.get("mode") or "touched"))
            return SimpleNamespace(public=lambda: {"state": "complete", "refreshed": 0})

    svc = _Probe(
        InMemoryStore(),
        embeddings=LocalEmbeddingStub(dims=16, model="local-hash-v1"),
        embedding_index=InMemoryEmbeddingIndex(),
    )
    svc.sync_repo(
        SCOPE,
        "agent",
        "corr-heal",
        "sync-heal-1",
        {
            "root_path": str(tmp_path),
            "embedding_refresh_mode": "full",
            "include_outcomes": False,
        },
    )
    assert modes == ["full"]


def test_pending_ingest_normalizes_paths_for_embedding_refresh(tmp_path, monkeypatch):
    """Regression: absolute/./ pending paths must map to ingest relative paths."""
    monkeypatch.delenv("ASTLOOM_EMBEDDING_REFRESH_FULL", raising=False)
    mod = tmp_path / "pkg" / "mod.py"
    mod.parent.mkdir()
    mod.write_text("def f():\n    return 1\n", encoding="utf-8")
    seen_paths: list[list[str] | None] = []

    class _Probe(CodeGraphService):
        def refresh_embeddings_after_ingest(self, scope, **kwargs):  # type: ignore[no-untyped-def]
            seen_paths.append(kwargs.get("file_paths"))
            return SimpleNamespace(public=lambda: {"state": "complete", "refreshed": 0})

    svc = _Probe(
        InMemoryStore(),
        embeddings=LocalEmbeddingStub(dims=16, model="local-hash-v1"),
        embedding_index=InMemoryEmbeddingIndex(),
    )
    abs_pending = str(mod.resolve())
    svc._ingest_pending_paths(
        SCOPE,
        "agent",
        "corr-pending",
        "pending-1",
        root=tmp_path,
        pending_paths=[abs_pending, "./pkg/mod.py"],
        include_outcomes=False,
        embedding_refresh_mode="touched",
    )
    assert len(seen_paths) == 1
    assert seen_paths[0] == ["pkg/mod.py"]


def test_pending_absolute_path_heals_embeddings_for_touched_file(tmp_path, monkeypatch):
    monkeypatch.delenv("ASTLOOM_EMBEDDING_REFRESH_FULL", raising=False)
    mod = tmp_path / "mod.py"
    mod.write_text("def f():\n    return 1\n", encoding="utf-8")
    index = InMemoryEmbeddingIndex()
    svc = CodeGraphService(
        InMemoryStore(),
        embeddings=LocalEmbeddingStub(dims=16, model="local-hash-v1"),
        embedding_index=index,
    )
    svc.ingest_file(
        SCOPE,
        "agent",
        "corr",
        "seed",
        {"file_path": "mod.py", "source": mod.read_text(encoding="utf-8"), "language": "python"},
    )
    index.wipe_scope(SCOPE)
    assert not index.list_symbol_models(SCOPE)
    result = svc._ingest_pending_paths(
        SCOPE,
        "agent",
        "corr-2",
        "pending-2",
        root=tmp_path,
        pending_paths=[str(mod.resolve())],
        include_outcomes=False,
        embedding_refresh_mode="touched",
    )
    assert result.embedding_refresh.get("state") == "complete"
    assert index.list_symbol_models(SCOPE)


def test_refresh_embeddings_uses_batch_api():
    class BatchStub(LocalEmbeddingStub):
        calls = 0

        def embed_many(self, texts, *, is_query=False):
            self.calls += 1
            return super().embed_many(texts, is_query=is_query)

    index = InMemoryEmbeddingIndex()
    stub = BatchStub(dims=16)
    service = CodeGraphService(InMemoryStore(), embeddings=stub, embedding_index=index)
    _ingest(service)
    index.wipe_scope(SCOPE)
    calls_before_refresh = stub.calls
    report = service.refresh_embeddings(SCOPE, policy_path=POLICY)
    assert report.state == "complete"
    assert report.refreshed >= 2
    assert stub.calls == calls_before_refresh + 1


def test_refresh_embeddings_runs_large_batches_with_bounded_parallelism(
    monkeypatch,
):
    monkeypatch.setenv("ASTLOOM_EMBEDDING_REFRESH_WORKERS", "3")
    class SlowBatchStub(LocalEmbeddingStub):
        def __init__(self) -> None:
            super().__init__(dims=16)
            self.active = 0
            self.peak = 0
            self.lock = threading.Lock()

        def embed_many(self, texts, *, is_query=False):
            with self.lock:
                self.active += 1
                self.peak = max(self.peak, self.active)
            try:
                time.sleep(0.02)
                return super().embed_many(texts, is_query=is_query)
            finally:
                with self.lock:
                    self.active -= 1

    source = "\n\n".join(
        f"def function_{index}():\n    return {index}" for index in range(270)
    )
    index = InMemoryEmbeddingIndex()
    stub = SlowBatchStub()
    service = CodeGraphService(
        InMemoryStore(),
        embeddings=stub,
        embedding_index=index,
    )
    service.ingest_file(
        SCOPE,
        "agent",
        "corr-large-batch",
        "large-batch",
        {"file_path": "src/large_batch.py", "source": source, "language": "python"},
    )
    index.wipe_scope(SCOPE)
    stub.peak = 0

    report = service.refresh_embeddings(SCOPE, policy_path=POLICY)

    assert report.state == "complete"
    assert report.refreshed >= 540
    assert stub.peak >= 2
    assert stub.peak <= 3


def test_refresh_embeddings_reports_unavailable_index():
    service = CodeGraphService(
        InMemoryStore(),
        embeddings=LocalEmbeddingStub(dims=16, model="local-hash-v1"),
        embedding_index=None,
    )
    report = service.refresh_embeddings(SCOPE, policy_path=POLICY)
    assert report.state == "complete"
    assert report.scanned == 0
    assert report.reasons.get("embedding_index_unavailable") == 1
    assert report.error and "embedding_index_unavailable" in report.error

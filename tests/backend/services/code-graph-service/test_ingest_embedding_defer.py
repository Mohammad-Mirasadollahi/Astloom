"""Ingest keeps graph structure when hosted embeddings fail; retry + self-heal."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from code_graph_service.application.support import EMBEDDING_HEAL_PENDING
from code_graph_service.core import CodeGraphService, LocalEmbeddingStub, Scope
from code_graph_service.postgres_side import InMemoryEmbeddingIndex
from code_graph_service.testing import InMemoryStore

SCOPE = Scope("t", "w", "p-embed-defer")
POLICY = (
    Path(__file__).resolve().parents[4]
    / "backend"
    / "configs"
    / "embeddings"
    / "refresh-policy.json"
)


class _BoomEmbed:
    model = "boom"

    def embed(self, text, *, is_query=False):
        raise RuntimeError(
            "LiteLLM embedding batch failed: litellm.APIError: "
            "OpenrouterException - [Errno -3] Temporary failure in name resolution"
        )

    def embed_many(self, texts, *, is_query=False):
        raise RuntimeError("LiteLLM embedding batch failed: embedding call timed out after 60.0s")


def test_ingest_keeps_symbols_when_embedding_fails(monkeypatch):
    monkeypatch.setattr(
        "code_graph_service.llm_wiring._embed_retry_sleep_seconds", lambda _attempt: 0
    )
    store = InMemoryStore()
    service = CodeGraphService(store)
    service.embeddings = _BoomEmbed()
    result = service.ingest_file(
        SCOPE,
        "agent",
        str(uuid4()),
        "embed-defer-1",
        {
            "file_path": "src/auth.py",
            "language": "python",
            "source": "def hash_password(value: str) -> str:\n    return value\n",
        },
    )
    assert result.file_id
    file_symbol = store.get_symbol(result.file_id, SCOPE)
    assert file_symbol is not None
    assert file_symbol.body
    assert file_symbol.embedding == []
    assert (file_symbol.metadata or {}).get(EMBEDDING_HEAL_PENDING) is True
    login = store.get_symbol(f"sym:{SCOPE.project_id}:src.auth.hash_password", SCOPE)
    assert login is not None
    assert "return value" in (login.body or "")
    assert login.embedding == []


def test_ingest_retries_transient_embed_then_succeeds(monkeypatch):
    monkeypatch.setattr(
        "code_graph_service.llm_wiring._embed_retry_sleep_seconds", lambda _attempt: 0
    )
    store = InMemoryStore()
    stub = LocalEmbeddingStub(dims=8)
    calls = {"n": 0}

    class _Flaky:
        model = "flaky"

        def embed(self, text, *, is_query=False):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("[Errno -3] Temporary failure in name resolution")
            return stub.embed(text)

        def embed_many(self, texts, *, is_query=False):
            return [stub.embed(text) for text in texts]

    service = CodeGraphService(store)
    service.embeddings = _Flaky()
    service.ingest_file(
        SCOPE,
        "agent",
        str(uuid4()),
        "embed-retry-1",
        {
            "file_path": "src/auth.py",
            "language": "python",
            "source": "def hash_password(value: str) -> str:\n    return value\n",
        },
    )
    login = store.get_symbol(f"sym:{SCOPE.project_id}:src.auth.hash_password", SCOPE)
    assert login is not None
    assert login.embedding
    assert calls["n"] >= 2


def test_after_ingest_self_heals_pending_file_outside_touched_paths(monkeypatch):
    monkeypatch.setattr(
        "code_graph_service.llm_wiring._embed_retry_sleep_seconds", lambda _attempt: 0
    )
    store = InMemoryStore()
    index = InMemoryEmbeddingIndex()
    service = CodeGraphService(
        store,
        embeddings=_BoomEmbed(),
        embedding_index=index,
    )
    service.ingest_file(
        SCOPE,
        "agent",
        str(uuid4()),
        "embed-heal-1",
        {
            "file_path": "src/auth.py",
            "language": "python",
            "source": "def hash_password(value: str) -> str:\n    return value\n",
        },
    )
    file_id = f"file:{SCOPE.project_id}:src/auth.py"
    assert (store.get_symbol(file_id, SCOPE).metadata or {}).get(EMBEDDING_HEAL_PENDING)

    service.embeddings = LocalEmbeddingStub(dims=16, model="local-hash-v1")
    report = service.refresh_embeddings_after_ingest(
        SCOPE,
        file_paths=["unrelated.py"],
        mode="touched",
        policy_path=POLICY,
    )
    assert report.state == "complete"
    assert report.refreshed >= 1
    assert index.list_symbol_models(SCOPE)
    assert not (store.get_symbol(file_id, SCOPE).metadata or {}).get(EMBEDDING_HEAL_PENDING)

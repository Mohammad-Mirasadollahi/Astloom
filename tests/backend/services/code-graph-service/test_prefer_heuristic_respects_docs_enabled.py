"""Parallel sync must not silently skip living LLM docs when docs are enabled."""

from __future__ import annotations

from pathlib import Path

from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.testing import InMemoryStore


class _RecordingDocs:
    def __init__(self) -> None:
        self.calls = 0
        self.batch_calls = 0
        self.batch_sizes: list[int] = []

    def generate(self, symbol, neighbors):  # noqa: ANN001
        self.calls += 1
        return f"llm-doc-for-{symbol.name}"

    def generate_many(self, items):  # noqa: ANN001
        self.batch_calls += 1
        self.batch_sizes.append(len(items))
        return [self.generate(symbol, neighbors) for symbol, neighbors in items]


def test_defer_cross_file_uses_llm_when_docs_enabled(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTLOOM_LITELLM_DOCS_ENABLED", "true")
    source = tmp_path / "mod.py"
    source.write_text("def alpha():\n    return 1\n", encoding="utf-8")
    docs = _RecordingDocs()
    svc = CodeGraphService(InMemoryStore(), docs=docs)
    scope = Scope("t", "w", "docs-on")
    svc.ingest_file(
        scope,
        "tester",
        "c1",
        "k1",
        {
            "file_path": "mod.py",
            "source": source.read_text(encoding="utf-8"),
            "language": "python",
            "defer_cross_file_pass": True,
        },
    )
    assert docs.batch_calls == 1
    assert docs.calls >= 1


def test_ingest_batches_docs_for_multiple_symbols(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTLOOM_LITELLM_DOCS_ENABLED", "true")
    source = tmp_path / "mod.py"
    source.write_text(
        "def alpha():\n    return 1\n\ndef beta():\n    return 2\n",
        encoding="utf-8",
    )
    docs = _RecordingDocs()
    svc = CodeGraphService(InMemoryStore(), docs=docs)
    scope = Scope("t", "w", "docs-batch")
    svc.ingest_file(
        scope,
        "tester",
        "c1",
        "k1",
        {
            "file_path": "mod.py",
            "source": source.read_text(encoding="utf-8"),
            "language": "python",
        },
    )
    assert docs.batch_calls == 1
    assert docs.batch_sizes == [2]
    assert docs.calls == 2


def test_defer_cross_file_uses_heuristic_when_docs_disabled(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASTLOOM_LITELLM_DOCS_ENABLED", "false")
    source = tmp_path / "mod.py"
    source.write_text("def alpha():\n    return 1\n", encoding="utf-8")
    docs = _RecordingDocs()
    svc = CodeGraphService(InMemoryStore(), docs=docs)
    scope = Scope("t", "w", "docs-off")
    svc.ingest_file(
        scope,
        "tester",
        "c1",
        "k1",
        {
            "file_path": "mod.py",
            "source": source.read_text(encoding="utf-8"),
            "language": "python",
            "defer_cross_file_pass": True,
        },
    )
    assert docs.calls == 0

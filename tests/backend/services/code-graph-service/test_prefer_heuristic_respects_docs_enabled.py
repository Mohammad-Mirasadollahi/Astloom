"""Parallel sync must not silently skip living LLM docs when docs are enabled."""

from __future__ import annotations

from pathlib import Path

from code_graph_service.core import CodeGraphService, Scope
from code_graph_service.testing import InMemoryStore


class _RecordingDocs:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, symbol, neighbors):  # noqa: ANN001
        self.calls += 1
        return f"llm-doc-for-{symbol.name}"


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
    assert docs.calls >= 1


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
